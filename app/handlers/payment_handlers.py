import logging
import datetime
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.crud import user_crud, transaction_crud
from app.db.models import SubscriptionStatus, TransactionStatus, UserRole # Assuming UserRole might be used for special plans later

logger = logging.getLogger(__name__)
payment_router = Router(name="payment_handlers")

# Define our single plan for now
MONTHLY_PLAN_PRICE_RUB = 450.00
MONTHLY_PLAN_TITLE = "Доступ BTrainer Pro (1 месяц)"
# MODIFIED: Format price with comma and ensure the description string is safe for MarkdownV2
# We will rely on escape_md() being called on the whole description later.
# The f-string formatting itself doesn't introduce Markdown special chars other than what's in the variable.
# The problematic character was '.' from the float to string conversion.
# Let's format it with a comma for Russian locale.
price_str = str(MONTHLY_PLAN_PRICE_RUB).replace('.', ',')
MONTHLY_PLAN_DESCRIPTION = f"Полный доступ ко всем функциям BTrainer на 30 дней!"
MONTHLY_PLAN_CURRENCY = "RUB"
MONTHLY_PLAN_DURATION_DAYS = 30
MONTHLY_PLAN_ID = "monthly_sub_v1" # Internal ID for the plan

@payment_router.pre_checkout_query()
async def handle_pre_checkout_query(pre_checkout_query: types.PreCheckoutQuery, bot: Bot, session: AsyncSession):
    logger.info(f"Received PreCheckoutQuery from user {pre_checkout_query.from_user.id} for payload {pre_checkout_query.invoice_payload}")

    if not settings.TELEGRAM_PAYMENT_PROVIDER_TOKEN:
        logger.error("TELEGRAM_PAYMENT_PROVIDER_TOKEN is not set. Cannot process payment.")
        await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=False, error_message="Платежная система временно недоступна.")
        return

    # The invoice_payload should be our internal_transaction_id
    transaction = await transaction_crud.get_transaction_by_internal_id(db=session, internal_id=pre_checkout_query.invoice_payload)

    if not transaction:
        logger.error(f"PreCheckoutQuery: Transaction with internal_id {pre_checkout_query.invoice_payload} not found.")
        await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=False, error_message="Заказ не найден. Пожалуйста, попробуйте создать платеж заново.")
        return

    if transaction.status != TransactionStatus.PENDING:
        logger.warning(f"PreCheckoutQuery: Transaction {transaction.id} is not PENDING (status: {transaction.status}).")
        await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=False, error_message="Этот платеж уже обработан или истек.")
        return

    # Additional checks can be performed here (e.g., item availability, user status)
    # For now, we assume if the transaction exists and is pending, it's okay.
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)
    logger.info(f"PreCheckoutQuery for {pre_checkout_query.invoice_payload} answered OK.")


@payment_router.message(F.successful_payment)
async def handle_successful_payment(message: types.Message, session: AsyncSession, bot: Bot):
    payment_info = message.successful_payment
    user_telegram_id = message.from_user.id
    internal_transaction_id = payment_info.invoice_payload

    logger.info(f"Received SuccessfulPayment from user {user_telegram_id} for payload {internal_transaction_id}. TG Charge ID: {payment_info.telegram_payment_charge_id}")

    transaction = await transaction_crud.get_transaction_by_internal_id(db=session, internal_id=internal_transaction_id)

    if not transaction:
        logger.error(f"SuccessfulPayment: Transaction with internal_id {internal_transaction_id} not found for user {user_telegram_id}.")
        # This should ideally not happen if PreCheckoutQuery was handled correctly.
        # We can still try to inform the user, but the subscription won't be activated without a transaction record.
        await message.answer("Произошла ошибка при обработке вашего платежа (транзакция не найдена). Пожалуйста, свяжитесь с поддержкой.")
        return

    if transaction.status == TransactionStatus.SUCCEEDED:
        logger.warning(f"SuccessfulPayment: Transaction {transaction.id} already marked as SUCCEEDED for user {user_telegram_id}.")
        await message.answer(f"Ваша подписка по этому платежу уже активна! Спасибо!")
        return
    
    # Update transaction
    updated_transaction = await transaction_crud.update_transaction_successful(
        db=session,
        internal_id=internal_transaction_id,
        telegram_charge_id=payment_info.telegram_payment_charge_id,
        provider_payment_charge_id=payment_info.provider_payment_charge_id # Store this too
    )
    
    # Update user's subscription
    expiry_date = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=MONTHLY_PLAN_DURATION_DAYS)
    db_user = await user_crud.update_user_subscription(
        db=session,
        telegram_id=user_telegram_id,
        status=SubscriptionStatus.ACTIVE,
        plan_name=MONTHLY_PLAN_ID, # Or use a more descriptive name from plan details
        expires_at=expiry_date
    )

    if db_user and updated_transaction:
        logger.info(f"User {user_telegram_id} (DB ID: {db_user.id}) subscription activated for plan {MONTHLY_PLAN_ID}. Expires: {expiry_date}. Transaction {updated_transaction.id} updated.")
        await message.answer(
            f"Спасибо за оплату! 🎉\n\nВаша подписка '{MONTHLY_PLAN_TITLE}' активна до {expiry_date.strftime('%d.%m.%Y %H:%M UTC')}.\n\nТеперь вам доступны все возможности BTrainer!"
        )
    else:
        logger.error(f"Failed to update subscription or transaction for user {user_telegram_id}, payload {internal_transaction_id}.")
        # This is a critical error, needs investigation. The payment went through.
        await message.answer(
            "Ваш платеж прошел успешно, но произошла ошибка при активации подписки. Пожалуйста, срочно свяжитесь с поддержкой, указав детали платежа."
        )
        # Consider logging more details about the payment_info object here
        # Consider raising an exception to ensure rollback if anything partially committed. 