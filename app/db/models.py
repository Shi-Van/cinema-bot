from datetime import datetime

from sqlalchemy import Float, ForeignKey, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(unique=True)
    username: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    
    search_history: Mapped[list["SearchHistory"]] = relationship(back_populates="user")

class SearchHistory(Base):
    __tablename__ = "search_history"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    query: Mapped[str] = mapped_column(String(255))
    movie_id: Mapped[str] = mapped_column(String(255))
    movie_title: Mapped[str] = mapped_column(String(255))
    movie_url: Mapped[str | None] = mapped_column(String(512))
    movie_rating: Mapped[float | None] = mapped_column(Float)
    timestamp: Mapped[datetime] = mapped_column(default=func.now())
    
    user: Mapped["User"] = relationship(back_populates="search_history")
 