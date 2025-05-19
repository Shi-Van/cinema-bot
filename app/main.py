import asyncio
import logging

from .bot import CinemaBot
from .config import settings

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format=settings.LOG_FORMAT
)

async def main():
    bot = CinemaBot()
    await bot.start()

if __name__ == "__main__":
    asyncio.run(main()) 