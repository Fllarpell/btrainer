import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from app.core.config import settings
from app.db.session import SessionLocal
from app.middlewares.db import DbSessionMiddleware
from app.handlers.common import common_router
# from app.handlers import user_router, admin_router
# from app.db.engine import engine # SQLAlchemy engine для middleware

async def main():
    logging.basicConfig(
        level=settings.LOG_LEVEL,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )
    logger = logging.getLogger(__name__)
    logger.info("Starting bot...")

    # Инициализация бота и диспетчера
    # MemoryStorage используется по умолчанию для хранения состояний FSM. 
    # Для продакшена лучше использовать RedisStorage или другое персистентное хранилище.
    storage = MemoryStorage()

    bot = Bot(
        token=settings.TELEGRAM_BOT_TOKEN, 
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=storage)

    dp.update.middleware(DbSessionMiddleware(session_pool=SessionLocal))
    logger.info("Database session middleware registered.")

    dp.include_router(common_router)
    # dp.include_router(user_router) # Для пользовательских команд
    # dp.include_router(admin_router) # Для админ-команд
    logger.info("Common routers included.")

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Starting polling...")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        # from app.db.session import engine as async_engine
        # await async_engine.dispose()
        logger.info("Bot stopped.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped manually.") 