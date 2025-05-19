from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery, Update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
import logging
from datetime import datetime, timezone

# Import for fetching user
from app.db.crud.user_crud import get_user_by_telegram_id
# Import for enums
from app.db.models import SubscriptionStatus, UserRole
from app.core.config import is_admin

logger = logging.getLogger(__name__)

class DbSessionMiddleware(BaseMiddleware):
    def __init__(self, session_pool: async_sessionmaker[AsyncSession]):
        super().__init__()
        self.session_pool = session_pool

    async def __call__(
        self, 
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        logger.info(f"[Middleware] Entered __call__ for raw event type: {type(event).__name__}, Update ID: {event.update_id}")
        
        actual_event: TelegramObject | None = None
        user_id: int | None = None
        event_for_reply: Message | CallbackQuery | None = None
        is_start_command = False # Flag to indicate if the event is a /start command
        
        # Determine the actual event type from the Update object
        if event.message:
            actual_event = event.message
            event_for_reply = event.message
            if event.message.from_user:
                user_id = event.message.from_user.id
            if event.message.text == "/start": # Check if the command is /start
                is_start_command = True
        elif event.callback_query:
            actual_event = event.callback_query
            event_for_reply = event.callback_query # We can use .answer() on this
            if event.callback_query.from_user:
                user_id = event.callback_query.from_user.id
        elif event.edited_message:
            actual_event = event.edited_message
            # Potentially handle edited messages if necessary, for now, just get user_id
            if event.edited_message.from_user:
                user_id = event.edited_message.from_user.id
        # Add other event types like inline_query, chosen_inline_result etc. if needed for user checks
        else:
            # If it's an Update type we don't extract a user from (e.g., poll update, etc.)
            logger.info(f"[Middleware] Update type {type(event).__name__} does not have a direct user interaction to check for blocking/subscription. Update ID: {event.update_id}")
            # We might still want to provide the session and proceed for non-user-specific handlers
            async with self.session_pool() as session:
                data["session"] = session
                try:
                    return await handler(event, data) # Pass the original Update object
                except Exception as e:
                    logger.error(f"DbSessionMiddleware: Exception in handler (no user context), rolling back session: {e}", exc_info=True)
                    if session.is_active:
                        await session.rollback()
                    raise
        
        logger.info(f"[Middleware] Actual event type: {type(actual_event).__name__ if actual_event else 'N/A'}, User ID: {user_id}")

        async with self.session_pool() as session:
            data["session"] = session
            
            if user_id and actual_event: # Ensure we have a user and an event to act upon
                db_user = await get_user_by_telegram_id(db=session, telegram_id=user_id)
                logger.info(f"[Middleware] Checking user_id: {user_id}. Found db_user: {bool(db_user)}")
                if db_user:
                    logger.info(f"[Middleware] For user_id: {user_id}, db_user.is_blocked = {db_user.is_blocked}, role = {db_user.role}, request_count = {db_user.db_request_count}")
                    # Increment request count here, before other checks, as it's a request to the DB path
                    db_user.db_request_count += 1
                    # No need to await session.flush() or add() here for a simple increment on an existing object if it's committed later.

                # 1. Blocked check
                if db_user and db_user.is_blocked:
                    logger.warning(f"[Middleware] BLOCKED user {user_id} tried to access. Event: {type(actual_event).__name__}. Halting.")
                    try:
                        if isinstance(actual_event, CallbackQuery):
                            await actual_event.answer("Ваш аккаунт заблокирован. Обратитесь к администратору.", show_alert=True)
                        elif isinstance(actual_event, Message):
                            await actual_event.reply("Ваш аккаунт заблокирован. Обратитесь к администратору.")
                    except Exception as e:
                        logger.error(f"Failed to notify blocked user {user_id}: {e}")
                    return 

                # 2. Subscription/Trial Check (using actual_event and event_for_reply)
                if db_user:
                    if not is_admin(user_id, db_user):
                        is_active_subscriber = db_user.subscription_status == SubscriptionStatus.ACTIVE
                        is_active_trial = (
                            db_user.subscription_status == SubscriptionStatus.TRIAL and
                            db_user.trial_end_date and
                            db_user.trial_end_date > datetime.now(timezone.utc)
                        )
                        if not (is_active_subscriber or is_active_trial):
                            logger.warning(f"User {user_id} without active subscription/trial. Status: {db_user.subscription_status}, Trial ends: {db_user.trial_end_date}")
                            message_text = "Для доступа к функциям бота необходима активная подписка или пробный период. Пожалуйста, оформите подписку или используйте /start для просмотра опций."
                            allow_bypass = False
                            
                            # Determine if the current event should bypass the subscription check
                            if isinstance(actual_event, Message):
                                if actual_event.text in ["/start", "💳 Тарифы и подписка", "ℹ️ Помощь"]:
                                    allow_bypass = True
                                elif actual_event.successful_payment: # Allow SuccessfulPayment messages
                                    allow_bypass = True
                            elif isinstance(actual_event, CallbackQuery) and actual_event.data:
                                if actual_event.data.startswith("onboarding:") or \
                                   actual_event.data.startswith("subscribe_action:"):
                                    allow_bypass = True
                            
                            if not allow_bypass:
                                try:
                                    if isinstance(event_for_reply, CallbackQuery):
                                        await event_for_reply.answer(message_text, show_alert=True)
                                    elif isinstance(event_for_reply, Message):
                                        await event_for_reply.reply(message_text)
                                except Exception as e:
                                    logger.error(f"Failed to notify user {user_id} about subscription requirement: {e}")
                                return
                elif user_id: # db_user is None, but we have a user_id from the event
                    # If the command is /start and user is not found, let it pass to the handler to create the user
                    if not is_start_command:
                        logger.warning(f"User {user_id} not found in DB. Event: {type(actual_event).__name__}")
                        message_text = "Ваш профиль не найден. Пожалуйста, используйте команду /start для регистрации и доступа к боту."
                        try:
                            if isinstance(event_for_reply, CallbackQuery):
                                await event_for_reply.answer(message_text, show_alert=True)
                            elif isinstance(event_for_reply, Message):
                                await event_for_reply.reply(message_text)
                        except Exception as e:
                            logger.error(f"Failed to notify non-registered user {user_id}: {e}")
                        return
            
            # Proceed with the handler if user passed all checks or no user_id was extracted (e.g. channel post)
            # Pass the original Update object to the handler, as that's what dp.update.middleware provides
            try:
                result = await handler(event, data)
                # If we had a db_user and the handler didn't cause a rollback by raising an exception that this middleware caught,
                # the incremented db_request_count will be committed along with other changes.
                if session.is_active: 
                    await session.commit()
                return result
            except Exception as e:
                logger.error(f"DbSessionMiddleware: Exception in handler, rolling back session: {e}", exc_info=True)
                if session.is_active:
                    await session.rollback()
                raise
