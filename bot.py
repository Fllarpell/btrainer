import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.middlewares.db import DbSessionMiddleware

from app.handlers.user.user_onboarding_handlers import user_onboarding_router
from app.handlers.user.feature_handlers import feature_router as user_feature_router
from app.handlers.case.case_lifecycle_handlers import case_lifecycle_router
from app.handlers.admin.admin import admin_router
from app.handlers.payment_handlers import payment_router


async def main():
    logging.basicConfig(
        level=settings.LOG_LEVEL,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        handlers=[
            logging.FileHandler("app.log", encoding="utf-8"),
            logging.StreamHandler()
    ]
)
    logger = logging.getLogger(__name__)
    logger.info("Starting bot...")

    # Для продакшена лучше использовать RedisStorage
    storage = MemoryStorage()

    bot = Bot(
        token=settings.TELEGRAM_BOT_TOKEN, 
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=storage)

    dp.update.middleware(DbSessionMiddleware(session_pool=AsyncSessionLocal))
    logger.info("Database session middleware registered.")

    dp.include_router(user_onboarding_router)
    dp.include_router(user_feature_router)
    dp.include_router(case_lifecycle_router)
    dp.include_router(admin_router)
    dp.include_router(payment_router)

    logger.info("All application routers and payment handlers included.")

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Starting polling...")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

        from app.db.session import async_engine
        await async_engine.dispose()
        logger.info("Bot stopped.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped manually.") 
