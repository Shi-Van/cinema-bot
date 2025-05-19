from functools import lru_cache

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    BOT_TOKEN: str = ""
    DATABASE_URL: str = "sqlite+aiosqlite:///cinema_bot.db"
    KINOPOISK_API_TOKEN: str | None = None
    
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    DB_ECHO: bool = True
    
    class Config:
        env_file = ".env"
        case_sensitive = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.BOT_TOKEN:
            raise ValueError("BOT_TOKEN не установлен в .env файле")

@lru_cache
def get_settings() -> Settings:
    load_dotenv()
    return Settings()

settings = get_settings() 