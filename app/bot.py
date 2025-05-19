import logging
from typing import List, Optional

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (Message, InlineKeyboardMarkup, CallbackQuery, User as TelegramUser)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .config import settings
from .db.database import Database
from .db.models import SearchHistory, User
from .kinopoisk_api import KinopoiskAPI, MovieInfo
from .utils.text_loader import get_text

logger = logging.getLogger(__name__)

class CinemaBot:
    def __init__(self):
        self.bot = Bot(token=settings.BOT_TOKEN)
        self.dp = Dispatcher()
        self.db = Database()
        self.kinopoisk = KinopoiskAPI()
        
        self.dp.message.register(self.cmd_start, Command(commands=["start"]))
        self.dp.message.register(self.cmd_help, Command(commands=["help"]))
        self.dp.message.register(self.cmd_history, Command(commands=["history"]))
        self.dp.message.register(self.cmd_stats, Command(commands=["stats"]))
        self.dp.message.register(self.handle_search)
        self.dp.callback_query.register(self.handle_pagination, F.data.startswith("pagination_"))
        self.dp.callback_query.register(self.handle_movie_select, F.data.startswith("movie_"))

    async def _get_or_create_user(self, telegram_user: Optional[TelegramUser]) -> User:
        if not telegram_user:
            raise ValueError("Telegram user is None")
        user = await self.db.get_or_create_user(
            telegram_id=telegram_user.id,
            username=telegram_user.username
        )
        if not user:
            raise ValueError("Не удалось создать пользователя")
        return user

    async def cmd_start(self, message: Message) -> None:
        if not message.from_user:
            await message.answer("Ошибка: не удалось определить пользователя")
            return
        await self._get_or_create_user(message.from_user)
        await message.answer(get_text("start"))

    async def cmd_help(self, message: Message) -> None:
        await message.answer(get_text("help"))

    async def cmd_history(self, message: Message) -> None:
        if not message.from_user:
            await message.answer("Ошибка: не удалось определить пользователя")
            return
        user = await self._get_or_create_user(message.from_user)
        await self._show_paginated_content(message, "history", user.id)

    async def cmd_stats(self, message: Message) -> None:
        if not message.from_user:
            await message.answer("Ошибка: не удалось определить пользователя")
            return
        user = await self._get_or_create_user(message.from_user)
        await self._show_paginated_content(message, "stats", user.id)

    async def handle_search(self, message: Message) -> None:
        if not message.from_user:
            await message.answer("Ошибка: не удалось определить пользователя")
            return
        await self._get_or_create_user(message.from_user)
        
        movies: List[MovieInfo] = await self.kinopoisk.search_movie(message.text)
        
        if not movies:
            await message.answer("По вашему запросу ничего не найдено 😔")
            return
            
        builder = InlineKeyboardBuilder()
        for movie in movies[:5]:
            button_text = f"{movie.title}"
            if movie.year:
                button_text += f" ({movie.year})"
            if movie.rating:
                button_text += f" 🤩{movie.rating}"
            if movie.type == "tv-series":
                button_text += " 📺"
            
            builder.button(
                text=button_text,
                callback_data=f"movie_{movie.id}"
            )
        builder.adjust(1)
        
        await message.answer(
            "Выберите фильм из списка:",
            reply_markup=builder.as_markup()
        )

    async def handle_movie_select(self, callback: CallbackQuery) -> None:
        try:
            if not callback.message or not isinstance(callback.message, Message):
                await callback.answer("Сообщение не найдено", show_alert=True)
                return

            if not callback.data:
                await callback.answer("Некорректные данные кнопки", show_alert=True)
                return
            movie_id = int(callback.data.split("_")[1])
            
            movie: Optional[MovieInfo] = await self.kinopoisk.get_movie_details(movie_id)
            if not movie:
                await callback.answer("Не удалось получить информацию о фильме", show_alert=True)
                return
                
            user = await self.db.get_user_by_telegram_id(callback.from_user.id)
            if not user:
                await callback.answer("Пользователь не найден", show_alert=True)
                return
            
            query_text = callback.message.text if callback.message.text is not None else "Поиск"
            first_line = query_text.split("\n")[0] if query_text else "Поиск"
            await self.db.add_search_history(
                user_id=user.id,
                query=first_line,
                movie_id=str(movie.id),
                movie_title=movie.title,
                movie_url=f"https://www.sspoisk.ru/film/{movie.id}/",
                movie_rating=movie.rating
            )
            
            message = f"🎬 {movie.title}"
            if movie.original_title:
                message += f"\n📝 {movie.original_title}"
            if movie.type == "tv-series":
                message += "\n📺 Сериал"
            if movie.year:
                message += f"\n📅 {movie.year}"
            if movie.movie_length:
                message += f"\n⏱ {movie.movie_length} мин."
            if movie.age_rating:
                message += f"\n🔞 {movie.age_rating}+"
            if movie.rating:
                message += f"\n🤩 Рейтинг КП: {movie.rating}"
                if movie.votes["kp"]:
                    message += f" ({movie.votes['kp']:,} пользователей оценили)"
            if movie.genres:
                message += f"\n🎭 Жанры: {', '.join(movie.genres)}"
            if movie.countries:
                message += f"\n🌍 Страны: {', '.join(movie.countries)}"
            if movie.short_description:
                message += f"\n\n📖 <blockquote>{movie.short_description}</blockquote>"
            elif movie.description:
                message += f"\n\n📖 <blockquote>{movie.description}</blockquote>"
            
            if movie.external_id["imdb"]:
                message += f"\n\n🎯 IMDB: https://www.imdb.com/title/{movie.external_id['imdb']}/"
            message += f"\n🎯 Кинопоиск: https://www.kinopoisk.ru/film/{movie.id}/"
            
            builder = InlineKeyboardBuilder()
            builder.button(
                text="🎬 Посмотреть",
                url=f"https://www.sspoisk.ru/film/{movie.id}/"
            )
            
            if movie.poster_url:
                try:
                    await callback.message.answer_photo(
                        photo=movie.poster_url,
                        caption=message,
                        reply_markup=builder.as_markup(),
                        parse_mode="HTML"
                    )
                    await callback.message.delete()
                except Exception as e:
                    logger.error(f"Ошибка при отправке постера: {e}")
                    await callback.message.edit_text(
                        message,
                        reply_markup=builder.as_markup(),
                        disable_web_page_preview=False,
                        parse_mode="HTML"
                    )
            else:
                await callback.message.edit_text(
                    message,
                    reply_markup=builder.as_markup(),
                    disable_web_page_preview=False,
                    parse_mode="HTML"
                )
            
            await callback.answer()
            
        except Exception as e:
            logger.error(f"Ошибка при обработке выбора фильма: {e}")
            await callback.answer("Произошла ошибка при получении информации о фильме", show_alert=True)

    def _get_history_keyboard(self, current_page: int, total_pages: int) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        
        if current_page > 1:
            builder.button(text="◀️ Назад", callback_data=f"history_prev_{current_page}")
        if current_page < total_pages:
            builder.button(text="Вперед ▶️", callback_data=f"history_next_{current_page}")
            
        return builder.as_markup()

    def _format_history_message(self, history: list[SearchHistory], current_page: int, total_pages: int) -> str:
        if not history:
            return "История поиска пуста"
            
        message = f"📝 История поиска (страница {current_page} из {total_pages}):\n\n"
        for item in history:
            message += f"🔍 {item.query}\n"
            message += f"🎬 {item.movie_title}"
            if item.movie_rating:
                message += f" (🤩 {item.movie_rating})"
            message += "\n"
            if item.movie_url:
                message += f"🔗 {item.movie_url}\n"
            message += f"📅 {item.timestamp.strftime('%d.%m.%Y %H:%M')}\n\n"
            
        return message

    async def _show_paginated_content(self, message: Message, content_type: str, user_id: int) -> None:
        page = 1
        if content_type == "history":
            content, total_pages = await self.db.get_user_history(user_id, page=page)
            text = self._format_history_message(content, page, total_pages)
        elif content_type == "stats":  # stats
            content, total_pages = await self.db.get_user_stats(user_id, page=page)
            text = self._format_stats_message(content, page, total_pages)
        else:
            logger.error("Неверный тип контента")
            return
            
        keyboard = self._get_pagination_keyboard(content_type, page, total_pages)
        await message.answer(text, reply_markup=keyboard, disable_web_page_preview=True)

    def _get_pagination_keyboard(self, content_type: str, current_page: int, total_pages: int) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        
        if current_page > 1:
            builder.button(text="◀️ Назад", callback_data=f"pagination_{content_type}_prev_{current_page}")
        if current_page < total_pages:
            builder.button(text="Вперед ▶️", callback_data=f"pagination_{content_type}_next_{current_page}")
            
        return builder.as_markup()

    def _format_stats_message(self, stats: list[dict], current_page: int, total_pages: int) -> str:
        if not stats:
            return "Статистика поиска пуста"
            
        message = f"📊 Статистика поиска (страница {current_page} из {total_pages}):\n\n"
        
        for item in stats:
            message += f"🎬 {item['movie_title']}\n"
            message += f"🔢 Количество поисков: {item['search_count']}\n"
            if item['avg_rating']:
                message += f"🤩 Рейтинг: {item['avg_rating']}\n"
            if item['movie_url']:
                message += f"Просмотреть: {item['movie_url']}\n"
            message += "\n"
            
        return message

    async def handle_pagination(self, callback: CallbackQuery) -> None:
        try:
            if not callback.message or not isinstance(callback.message, Message):
                await callback.answer("Сообщение не найдено", show_alert=True)
                return

            callback_data = callback.data or ""
            parts = callback_data.split("_")
            if len(parts) != 4:
                logger.error("Ошибка данных пагинации")
                return
            _, content_type, action, current_page_str = parts
            try:
                current_page = int(current_page_str)
            except ValueError:
                logger.error("Ошибка номера страницы")
                return
            
            user = await self.db.get_user_by_telegram_id(callback.from_user.id)
            if not user:
                await callback.answer("Пользователь не найден", show_alert=True)
                return
            
            new_page = current_page + 1 if action == "next" else current_page - 1
            
            if content_type == "history":
                content, total_pages = await self.db.get_user_history(user.id, page=new_page)
                text = self._format_history_message(content, new_page, total_pages)
            elif content_type == "stats":
                content, total_pages = await self.db.get_user_stats(user.id, page=new_page)
                text = self._format_stats_message(content, new_page, total_pages)
            else:
                logger.error("Неверный тип контента")
                await callback.answer("Ошибка при получении контента", show_alert=True)
                return
            
            if not content and total_pages > 0:
                await callback.answer("Ошибка при получении контента", show_alert=True)
                return
                
            keyboard = self._get_pagination_keyboard(content_type, new_page, total_pages)
            
            await callback.message.edit_text(
                text, 
                reply_markup=keyboard,
                disable_web_page_preview=True
            )
            await callback.answer()
            
        except Exception as e:
            logger.error(f"Ошибка при обработке пагинации {content_type}: {e}")
            await callback.answer("Произошла ошибка при обновлении контента", show_alert=True)

    async def start(self) -> None:
        await self.db.init()
        await self.dp.start_polling(self.bot) 