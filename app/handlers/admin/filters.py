import logging
from aiogram import types
from aiogram.filters import Filter
from sqlalchemy.ext.asyncio import AsyncSession # For type hint

from app.core.config import settings
from app.db.crud.user_crud import get_user_by_telegram_id
from app.db.models import UserRole

logger = logging.getLogger(__name__)

class AdminTelegramFilter(Filter):
    async def __call__(self, message_or_cq: types.Message | types.CallbackQuery, session: AsyncSession) -> bool: 
        user_id = message_or_cq.from_user.id
        
        logger.debug(f"AdminTelegramFilter checking access for user_id: {user_id}")
        logger.debug(f"Current ADMIN_IDS list: {settings.ADMIN_IDS}")
        
        if settings.ADMIN_IDS and user_id in settings.ADMIN_IDS:
            logger.debug(f"User {user_id} is in ADMIN_IDS list. Granting access.")
            return True
        else:
            logger.debug(f"User {user_id} is NOT in ADMIN_IDS list. Checking DB role...")
        
        db_user = await get_user_by_telegram_id(db=session, telegram_id=user_id)
        
        if db_user and db_user.role == UserRole.ADMIN:
            logger.debug(f"User {user_id} has ADMIN role in DB. Granting access.")
            return True
        
        logger.debug(f"User {user_id} is not an admin (not in ADMIN_IDS and no ADMIN role in DB). Denying access.")
        return False 