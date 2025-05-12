from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.orm import sessionmaker, Session
import logging

class DbSessionMiddleware(BaseMiddleware):
    def __init__(self, session_pool: sessionmaker[Session]):
        super().__init__()
        self.session_pool = session_pool

    async def __call__(
        self, 
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        db_session: Session = self.session_pool()
        data["db_session"] = db_session
        
        logger = data.get("logger", logging.getLogger(__name__))

        try:
            result = await handler(event, data)
            db_session.commit()
            return result
        except Exception as e:
            db_session.rollback()
            raise
        finally:
            db_session.close()
