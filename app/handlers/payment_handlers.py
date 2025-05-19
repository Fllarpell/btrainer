import logging
import datetime
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.crud import user_crud, transaction_crud
from app.db.models import SubscriptionStatus, TransactionStatus, UserRole

logger = logging.getLogger(__name__)
payment_router = Router(name="payment_handlers")

MONTHLY_PLAN_PRICE_RUB = 450.00
MONTHLY_PLAN_TITLE = "Доступ BTrainer Pro (1 месяц)"

price_str = str(MONTHLY_PLAN_PRICE_RUB).replace('.', ',')
MONTHLY_PLAN_DESCRIPTION = f"Полный доступ ко всем функциям BTrainer на 30 дней!"
MONTHLY_PLAN_CURRENCY = "RUB"
MONTHLY_PLAN_DURATION_DAYS = 30
MONTHLY_PLAN_ID = "monthly_sub_v1"

@payment_router.pre_checkout_query()
async def handle_pre_checkout_query(pre_checkout_query: types.PreCheckoutQuery, bot: Bot, session: AsyncSession):
    logger.info(f"Received PreCheckoutQuery from user {pre_checkout_query.from_user.id} for payload {pre_checkout_query.invoice_payload}")

    if not settings.TELEGRAM_PAYMENT_PROVIDER_TOKEN:
        logger.error("TELEGRAM_PAYMENT_PROVIDER_TOKEN is not set. Cannot process payment.")
        await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=False, error_message="Платежная система временно недоступна.")
        return

    transaction = await transaction_crud.get_transaction_by_internal_id(db=session, internal_id=pre_checkout_query.invoice_payload)

    if not transaction:
        logger.error(f"PreCheckoutQuery: Transaction with internal_id {pre_checkout_query.invoice_payload} not found.")
        await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=False, error_message="Заказ не найден. Пожалуйста, попробуйте создать платеж заново.")
        return

    if transaction.status != TransactionStatus.PENDING:
        logger.warning(f"PreCheckoutQuery: Transaction {transaction.id} is not PENDING (status: {transaction.status}).")
        await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=False, error_message="Этот платеж уже обработан или истек.")
        return

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
        await message.answer("Произошла ошибка при обработке вашего платежа (транзакция не найдена). Пожалуйста, свяжитесь с поддержкой.")
        return

    if transaction.status == TransactionStatus.SUCCEEDED:
        logger.warning(f"SuccessfulPayment: Transaction {transaction.id} already marked as SUCCEEDED for user {user_telegram_id}.")
        await message.answer(f"Ваша подписка по этому платежу уже активна! Спасибо!")
        return
    
    updated_transaction = await transaction_crud.update_transaction_successful(
        db=session,
        internal_id=internal_transaction_id,
        telegram_charge_id=payment_info.telegram_payment_charge_id,
        provider_payment_charge_id=payment_info.provider_payment_charge_id
    )

    
    db_user = await user_crud.get_user_by_telegram_id(session, telegram_id=user_telegram_id)
    now = datetime.datetime.now(datetime.timezone.utc)
    expiry_date = now + datetime.timedelta(days=MONTHLY_PLAN_DURATION_DAYS)
    if db_user and db_user.subscription_status == SubscriptionStatus.ACTIVE and db_user.subscription_expires_at and db_user.subscription_expires_at > now:
        expiry_date = db_user.subscription_expires_at + datetime.timedelta(days=MONTHLY_PLAN_DURATION_DAYS)
    else:
        expiry_date = now + datetime.timedelta(days=MONTHLY_PLAN_DURATION_DAYS)

    db_user = await user_crud.update_user_subscription(
        db=session,
        telegram_id=user_telegram_id,
        status=SubscriptionStatus.ACTIVE,
        plan_name=MONTHLY_PLAN_ID,
        expires_at=expiry_date
    )

    if db_user and updated_transaction:
        logger.info(f"User {user_telegram_id} (DB ID: {db_user.id}) subscription activated for plan {MONTHLY_PLAN_ID}. Expires: {expiry_date}. Transaction {updated_transaction.id} updated.")
        await message.answer(
            f"🎉 Спасибо за оплату!\n\n"
            f"Ваша подписка <b>{MONTHLY_PLAN_TITLE}</b> активна до <b>{expiry_date.strftime('%d.%m.%Y %H:%M UTC')}</b>.\n\n"
            f"Теперь вам доступны все возможности BTrainer! Удачной практики!",
            parse_mode='HTML'
        )
    else:
        logger.error(f"Failed to update subscription or transaction for user {user_telegram_id}, payload {internal_transaction_id}.")
        await message.answer(
            "Ваш платеж прошел успешно, но произошла ошибка при активации подписки. Пожалуйста, срочно свяжитесь с поддержкой, указав детали платежа."
        )
