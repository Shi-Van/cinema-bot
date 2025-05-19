import logging
from datetime import datetime
from typing import AsyncGenerator, Dict, List, Tuple

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..config import settings
from .models import Base, SearchHistory, User

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.engine = create_async_engine(
            settings.DATABASE_URL,
            echo=settings.DB_ECHO
        )
        self.async_session = async_sessionmaker(
            self.engine, 
            class_=AsyncSession, 
            expire_on_commit=False
        )

    async def init(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        async with self.async_session() as session:
            yield session

    async def get_or_create_user(self, telegram_id: int, username: str | None = None) -> User:
        async with self.async_session() as session:
            user = await session.scalar(
                select(User)
                .where(User.telegram_id == telegram_id)
            )
            
            if not user:
                user = User(
                    telegram_id=telegram_id,
                    username=username
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)
                logger.info(f"Создан новый пользователь: {telegram_id}")
            
            return user

    async def get_user_by_telegram_id(self, telegram_id: int) -> User | None:
        async with self.async_session() as session:
            return await session.scalar(
                select(User)
                .where(User.telegram_id == telegram_id)
            )

    async def add_search_history(self, user_id: int, query: str, movie_id: str, 
                               movie_title: str, movie_url: str | None = None, 
                               movie_rating: float | None = None) -> SearchHistory:
        async with self.async_session() as session:
            history_entry = SearchHistory(
                user_id=user_id,
                query=query[:255],
                movie_id=movie_id[:255],
                movie_title=movie_title[:255],
                movie_url=movie_url[:512] if movie_url else None,
                movie_rating=movie_rating,
                timestamp=datetime.utcnow()
            )
            
            session.add(history_entry)
            await session.commit()
            await session.refresh(history_entry)
            
            return history_entry

    async def get_user_stats(self, user_id: int, page: int = 1, per_page: int = 5) -> Tuple[List[Dict], int]:
        async with self.async_session() as session:
            subquery = (
                select(
                    SearchHistory.movie_id,
                    SearchHistory.movie_title,
                    SearchHistory.movie_url,
                    func.avg(SearchHistory.movie_rating).label('avg_rating'),
                    func.count().label('search_count')
                )
                .where(SearchHistory.user_id == user_id)
                .group_by(SearchHistory.movie_id, SearchHistory.movie_title, SearchHistory.movie_url)
                .subquery()
            )
            
            total_count = await session.scalar(
                select(func.count())
                .select_from(subquery)
            )
            
            logger.debug(f"Всего уникальных фильмов для пользователя {user_id}: {total_count}")
            
            total_pages = max(1, (total_count + per_page - 1) // per_page)
            logger.debug(f"Всего страниц статистики: {total_pages}, текущая страница: {page}")
            
            offset = (page - 1) * per_page
            stats = await session.execute(
                select(subquery)
                .order_by(desc('search_count'))
                .offset(offset)
                .limit(per_page)
            )
            
            stats_list = [
                {
                    'movie_id': row.movie_id,
                    'movie_title': row.movie_title,
                    'movie_url': row.movie_url,
                    'avg_rating': round(float(row.avg_rating), 1) if row.avg_rating else None,
                    'search_count': row.search_count
                }
                for row in stats
            ]
            
            logger.debug(f"Получено записей статистики для страницы {page}: {len(stats_list)}")
            
            return stats_list, total_pages

    async def get_user_history(self, user_id: int, page: int = 1, per_page: int = 5) -> Tuple[List[SearchHistory], int]:
        async with self.async_session() as session:

            total_count = await session.scalar(
                select(func.count())
                .select_from(SearchHistory)
                .where(SearchHistory.user_id == user_id)
            )
            
            logger.debug(f"Всего записей для пользователя {user_id}: {total_count}")
            
            total_pages = max(1, (total_count + per_page - 1) // per_page)
            logger.debug(f"Всего страниц: {total_pages}, текущая страница: {page}")
            
            offset = (page - 1) * per_page
            history = await session.scalars(
                select(SearchHistory)
                .where(SearchHistory.user_id == user_id)
                .order_by(SearchHistory.id.desc())
                .offset(offset)
                .limit(per_page)
            )
            
            history_list = list(history)
            logger.debug(f"Получено записей для страницы {page}: {len(history_list)}")
            
            return history_list, total_pages 