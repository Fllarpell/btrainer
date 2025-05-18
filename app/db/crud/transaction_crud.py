from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload
import datetime
from sqlalchemy import update
from decimal import Decimal
from typing import Optional, List
import logging

from app.db.models import Transaction, User, TransactionStatus
from app.db.session import AsyncSession # Ensure AsyncSession is imported for type hints

logger = logging.getLogger(__name__)

async def create_transaction(
    db: AsyncSession, 
    user_id: int, 
    internal_transaction_id: str, # Added this to be explicit, was missing
    amount: Decimal,
    currency: str,
    plan_name: Optional[str] = None,
    status: TransactionStatus = TransactionStatus.PENDING,
    # yookassa_payment_id: Optional[str] = None, # Retaining for potential future direct YooKassa use
    telegram_payment_charge_id: Optional[str] = None
) -> Transaction:
    new_transaction = Transaction(
        user_id=user_id,
        internal_transaction_id=internal_transaction_id,
        amount=amount,
        currency=currency,
        plan_name=plan_name,
        status=status,
        # yookassa_payment_id=yookassa_payment_id, # Ensure this is in your model if used
        telegram_payment_charge_id=telegram_payment_charge_id
    )
    db.add(new_transaction)
    await db.flush() 
    logger.info(f"Transaction {new_transaction.id} created for user {user_id} with internal_id {internal_transaction_id}, status {status}.")
    return new_transaction

async def get_transaction_by_internal_id(db: AsyncSession, internal_id: str) -> Optional[Transaction]:
    result = await db.execute(select(Transaction).filter(Transaction.internal_transaction_id == internal_id))
    transaction = result.scalars().first()
    if transaction:
        logger.debug(f"Retrieved transaction by internal_id {internal_id}: {transaction.id}")
    else:
        logger.debug(f"No transaction found with internal_id {internal_id}")
    return transaction

async def update_transaction_status(
    db: AsyncSession, 
    internal_id: str, 
    new_status: TransactionStatus,
    telegram_charge_id: Optional[str] = None,
    yookassa_payment_id: Optional[str] = None # if we get an update from yookassa webhook later for some reason
) -> Optional[Transaction]:
    transaction = await get_transaction_by_internal_id(db=db, internal_id=internal_id)
    if transaction:
        transaction.status = new_status
        if telegram_charge_id:
            transaction.telegram_payment_charge_id = telegram_charge_id
        if yookassa_payment_id:
            transaction.yookassa_payment_id = yookassa_payment_id
        # transaction.updated_at will be updated automatically by SQLAlchemy if configured in model
        await db.flush() # Or commit if this function is responsible for it
        # await db.commit()
        # await db.refresh(transaction)
        logger.info(f"Transaction {transaction.id} (internal: {internal_id}) status updated to {new_status}.")
        return transaction
    logger.warning(f"Failed to update transaction status: No transaction found with internal_id {internal_id}.")
    return None

async def update_transaction_successful(
    db: AsyncSession,
    internal_id: str,
    telegram_charge_id: str,
    provider_payment_charge_id: Optional[str] # YooKassa might also return its own charge ID via Telegram
) -> Optional[Transaction]:
    transaction = await get_transaction_by_internal_id(db=db, internal_id=internal_id)
    if transaction:
        transaction.status = TransactionStatus.SUCCEEDED
        transaction.telegram_payment_charge_id = telegram_charge_id
        # Store YooKassa's charge ID if provided and if yookassa_payment_id field exists and is distinct
        if provider_payment_charge_id and hasattr(transaction, 'yookassa_payment_id'):
            transaction.yookassa_payment_id = provider_payment_charge_id 

        await db.flush()
        logger.info(f"Transaction {transaction.id} (internal: {internal_id}) marked SUCCEEDED. TG Charge ID: {telegram_charge_id}")
        return transaction
    logger.warning(f"Failed to mark transaction successful: No transaction found with internal_id {internal_id}.")
    return None

async def get_transaction_by_id(db: AsyncSession, transaction_id: int) -> Transaction | None:
    result = await db.execute(
        select(Transaction)
        .where(Transaction.id == transaction_id)
        .options(joinedload(Transaction.user))
    )
    return result.scalars().first()

async def get_transactions_by_user(
    db: AsyncSession, user_id: int
) -> list[Transaction]:
    result = await db.execute(
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .order_by(Transaction.created_at.desc())
    )
    return result.scalars().all()

async def get_transaction_by_yookassa_id(db_session: AsyncSession, yookassa_id: str) -> Transaction | None:
    stmt = select(Transaction).where(Transaction.yookassa_payment_id == yookassa_id)
    result = await db_session.execute(stmt)
    return result.scalar_one_or_none()

async def update_transaction_external_id(db_session: AsyncSession, internal_transaction_id: str, external_id: str) -> Transaction | None:
    stmt = (
        update(Transaction)
        .where(Transaction.internal_transaction_id == internal_transaction_id)
        .values(yookassa_payment_id=external_id)
        .returning(Transaction)
    )
    result = await db_session.execute(stmt)
    await db_session.commit()
    transaction = result.scalar_one_or_none()
    return transaction

async def update_transaction_status_by_internal_id(
    db_session: AsyncSession, 
    internal_transaction_id: str, 
    new_status: TransactionStatus
) -> Transaction | None:
    stmt = (
        update(Transaction)
        .where(Transaction.internal_transaction_id == internal_transaction_id)
        .values(status=new_status)
        .returning(Transaction)
    )
    result = await db_session.execute(stmt)
    await db_session.commit()
    transaction = result.scalar_one_or_none()
    return transaction

async def update_transaction_status_by_id(
    db_session: AsyncSession, 
    transaction_id: int, 
    new_status: TransactionStatus
) -> Transaction | None:
    stmt = (
        update(Transaction)
        .where(Transaction.id == transaction_id)
        .values(status=new_status)
        .returning(Transaction)
    )
    result = await db_session.execute(stmt)
    await db_session.commit()
    transaction = result.scalar_one_or_none()
    return transaction

async def get_transactions_by_user_id(db: AsyncSession, user_id: int, limit: int = 100, offset: int = 0) -> List[Transaction]:
    result = await db.execute(
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .order_by(Transaction.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all() 