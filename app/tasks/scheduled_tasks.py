import datetime
import logging
from typing import List
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession
from app.db.crud.user_crud import get_users_trial_ending_soon, set_trial_ending_notification_sent
from app.db.session import AsyncSessionLocal
from app.db.models import User
from app.core.config import settings

logger = logging.getLogger(__name__)

MSK_TZ = ZoneInfo("Europe/Moscow")

TRIAL_ENDING_NOTIFICATION_HOURS = 6

ADMIN_NOTIFICATION_CHAT_ID = 1024566187

NOTIFICATION_MESSAGE_TEMPLATE = """
🔔 Важное уведомление

Дорогой пользователь, спешу напомнить вам, что пробный период использования BTrainer скоро завершится ({end_date} МСК)

Чтобы сохранить доступ ко всем функциям бота, вы можете оформить подписку на месяц по тарифу Simple — всего за 450 рублей до конца мая. Успейте оформить подписку до повышения цены!

🚀 Почему стоит выбрать подписку?
- Неограниченный доступ к генерации кейсов.
- Подробный анализ ваших решений с рекомендациями.
- Возможность следить за своим прогрессом и видеть, как растёт ваш профессионализм.

🔗 Для оформления подписки в главном меню просто нажмите кнопку Тарифы и подписка.

Не упустите возможность продолжить обучение с BTrainer! ✨

Если у вас есть вопросы, мы всегда рады помочь — пишите нам в поддержку.

С заботой о вашем развитии,
Команда BTrainer ❤️
"""

ADMIN_NOTIFICATION_TEMPLATE = """
Отправлено уведомление об окончании триала:
Пользователь: TG ID `{user_tg_id}` (DB ID `{user_db_id}`)
Username: @{username}
Имя: {first_name} {last_name}
Триал заканчивается: {trial_end_date}
"""

async def send_trial_ending_notifications(bot):
    logger.info("Running scheduled task: send_trial_ending_notifications")
    async with AsyncSessionLocal() as db:
        users_to_notify: List[User] = await get_users_trial_ending_soon(db, TRIAL_ENDING_NOTIFICATION_HOURS)

        if not users_to_notify:
            logger.info("No users found whose trial is ending soon and need notification.")
            return

        logger.info(f"Found {len(users_to_notify)} users whose trial is ending soon and need notification.")

        for user in users_to_notify:
            try:
                end_date_str = 'ближайшее время'
                if user.trial_end_date:
                    msk_end_date = user.trial_end_date.astimezone(MSK_TZ)
                    end_date_str = msk_end_date.strftime('%d.%m.%Y %H:%M')

                message_text = NOTIFICATION_MESSAGE_TEMPLATE.format(end_date=end_date_str)

                await bot.send_message(chat_id=user.telegram_id, text=message_text)
                logger.info(f"Sent trial ending notification to user {user.telegram_id} (DB ID: {user.id}).")

                await set_trial_ending_notification_sent(db, user.id)

                admin_message_text = ADMIN_NOTIFICATION_TEMPLATE.format(
                    user_tg_id=user.telegram_id,
                    user_db_id=user.id,
                    username=user.username if user.username else 'N/A',
                    first_name=user.first_name if user.first_name else '',
                    last_name=user.last_name if user.last_name else '',
                    trial_end_date=end_date_str
                ).replace('  ', ' ')

                try:
                    await bot.send_message(chat_id=ADMIN_NOTIFICATION_CHAT_ID, text=admin_message_text)
                    logger.info(f"Sent trial ending notification confirmation to admin chat ID {ADMIN_NOTIFICATION_CHAT_ID} for user {user.id}.")
                except Exception as admin_e:
                    logger.error(f"Failed to send admin notification for user {user.id} to chat ID {ADMIN_NOTIFICATION_CHAT_ID}: {admin_e}", exc_info=True)

            except Exception as e:
                logger.error(f"Failed to send trial ending notification to user {user.telegram_id} (DB ID: {user.id}): {e}", exc_info=True)
