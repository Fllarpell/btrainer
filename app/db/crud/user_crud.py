import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import func
from typing import Optional, List
from sqlalchemy import update
import logging

from ..models import User, UserRole, SubscriptionStatus, Solution, Transaction

logger = logging.getLogger(__name__)

async def get_user(db: AsyncSession, user_id: int) -> Optional[User]:
    return await db.get(User, user_id)


async def get_user_by_telegram_id(db: AsyncSession, telegram_id: int) -> Optional[User]:
    result = await db.execute(select(User).filter(User.telegram_id == telegram_id))
    return result.scalars().first()


async def get_user_with_details(db: AsyncSession, telegram_id: int) -> User | None:
    result = await db.execute(
        select(User)
        .where(User.telegram_id == telegram_id)
        .options(selectinload(User.solutions), selectinload(User.transactions))
    )
    return result.scalars().first()


async def create_user(
    db: AsyncSession, 
    telegram_id: int, 
    username: Optional[str] = None, 
    first_name: Optional[str] = None, 
    last_name: Optional[str] = None, 
    language_code: Optional[str] = None,
    role: UserRole = UserRole.USER,
    subscription_status: SubscriptionStatus = SubscriptionStatus.NONE,
    trial_start_date: Optional[datetime.datetime] = None,
    trial_end_date: Optional[datetime.datetime] = None,
    last_seen: Optional[datetime.datetime] = None
) -> User:
    db_user = User(
        telegram_id=telegram_id, 
        username=username, 
        first_name=first_name,
        last_name=last_name,
        language_code=language_code,
        role=role,
        subscription_status=subscription_status,
        trial_start_date=trial_start_date,
        trial_end_date=trial_end_date,
        last_active_at=last_seen if last_seen else datetime.datetime.now(datetime.timezone.utc)
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user


async def update_user_activity(db: AsyncSession, telegram_id: int) -> Optional[User]:
    db_user = await get_user_by_telegram_id(db, telegram_id)
    if db_user:
        db_user.last_active_at = datetime.datetime.now(datetime.timezone.utc)
        await db.flush()
        return db_user
    return None

async def update_user(
    db: AsyncSession, telegram_id: int, update_data: dict
) -> User | None:
    allowed_updates = {
        "username",
        "first_name",
        "last_name",
        "language_code",
        "is_premium",
        "last_activity_at",
        "subscription_status",
        "subscription_expires_at",
        "current_case_id",
        "state",
        "is_admin",
        "is_blocked",
        "role",
        "trial_start_date",
        "trial_end_date",
        "current_plan_name",
        "converted_from_trial",
    }
    update_data_filtered = {
        k: v for k, v in update_data.items() if k in allowed_updates
    }

    db_user = await get_user_by_telegram_id(db, telegram_id)
    if db_user:
        for key, value in update_data_filtered.items():
            setattr(db_user, key, value)
        await db.commit()
        await db.refresh(db_user)
    return db_user


async def set_user_subscription(
    db: AsyncSession, 
    telegram_id: int, 
    status: SubscriptionStatus, 
    trial_start: Optional[datetime.datetime] = None,
    trial_end: Optional[datetime.datetime] = None,
    plan_name: Optional[str] = None
) -> Optional[User]:
    update_data = {"subscription_status": status}
    if status == SubscriptionStatus.TRIAL:
        update_data["trial_start_date"] = trial_start if trial_start else datetime.datetime.now(datetime.timezone.utc)
        update_data["trial_end_date"] = trial_end
    elif status == SubscriptionStatus.ACTIVE:
        if plan_name:
            update_data["current_plan_name"] = plan_name
        pass
    
    return await update_user(db, telegram_id, update_data)


async def set_user_role(db: AsyncSession, telegram_id: int, role: UserRole) -> Optional[User]:
    return await update_user(db, telegram_id, {"role": role})


async def block_user(db: AsyncSession, telegram_id: int) -> Optional[User]:
    return await update_user(db, telegram_id, {"is_blocked": True})


async def unblock_user(db: AsyncSession, telegram_id: int) -> Optional[User]:
    return await update_user(db, telegram_id, {"is_blocked": False})


async def get_users_by_role(db: AsyncSession, role: UserRole, skip: int = 0, limit: int = 100) -> List[User]:
    result = await db.execute(select(User).filter(User.role == role).offset(skip).limit(limit))
    return result.scalars().all()


async def get_users(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[User]:
    result = await db.execute(
        select(User).order_by(User.id).offset(skip).limit(limit)
    )
    return result.scalars().all()


async def count_users(db: AsyncSession) -> int:
    result = await db.execute(select(func.count(User.id)))
    return result.scalar_one()


async def get_total_db_request_count(db: AsyncSession) -> int:
    result = await db.execute(select(func.sum(User.db_request_count).label("total_requests")))
    total = result.scalar_one_or_none()
    return total if total is not None else 0


async def count_converted_from_trial_users(db: AsyncSession) -> int:
    result = await db.execute(
        select(func.count(User.id)).filter(User.converted_from_trial == True)
    )
    return result.scalar_one()


async def grant_subscription_to_user(
    db_session: AsyncSession, 
    telegram_id: int,
    duration_days: int, 
    plan_name: str
) -> User | None:
    user = await get_user_by_telegram_id(db_session, telegram_id)
    if not user:
        return None

    was_on_trial = user.subscription_status == SubscriptionStatus.TRIAL

    now = datetime.datetime.now(datetime.timezone.utc)
    new_expiration_date = now + datetime.timedelta(days=duration_days)

    if user.subscription_status == SubscriptionStatus.ACTIVE and user.subscription_expires_at and user.subscription_expires_at > now:
        new_expiration_date = user.subscription_expires_at + datetime.timedelta(days=duration_days)
    
    values_to_update = {
        "subscription_status": SubscriptionStatus.ACTIVE,
        "subscription_expires_at": new_expiration_date,
        "current_plan_name": plan_name,
    }
    if was_on_trial:
        values_to_update["converted_from_trial"] = True
    
    stmt = (
        update(User)
        .where(User.telegram_id == telegram_id)
        .values(**values_to_update)
        .returning(User)
    )
    result = await db_session.execute(stmt)
    await db_session.commit()
    updated_user = await get_user_by_telegram_id(db_session, telegram_id)
    return updated_user


async def update_user_referral(db_session: AsyncSession, user_id: int, referrer_id: int) -> User | None:
    print(f"[TODO]: Implement referral update for user {user_id} by {referrer_id}")
    return await get_user_by_telegram_id(db_session, user_id)

async def update_user_subscription(
    db: AsyncSession,
    telegram_id: int,
    status: SubscriptionStatus,
    plan_name: Optional[str],
    expires_at: Optional[datetime.datetime]
) -> Optional[User]:
    user = await get_user_by_telegram_id(db=db, telegram_id=telegram_id)
    if user:
        if user.subscription_status == SubscriptionStatus.TRIAL and status == SubscriptionStatus.ACTIVE:
            user.converted_from_trial = True
            logger.info(f"User {telegram_id} converted from TRIAL to ACTIVE.")
            
        user.subscription_status = status
        user.current_plan_name = plan_name
        user.subscription_expires_at = expires_at
        
        if status == SubscriptionStatus.ACTIVE or status == SubscriptionStatus.EXPIRED:
            pass
        elif status == SubscriptionStatus.TRIAL:
            pass 

        await db.commit()
        await db.refresh(user)
        logger.info(f"User {telegram_id} subscription updated to {status}, plan {plan_name}, expires {expires_at}.")
        return user
    logger.warning(f"Failed to update subscription for non-existent user {telegram_id}.")
    return None

async def get_all_users(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[User]:
    result = await db.execute(
        select(User).order_by(User.id).offset(skip).limit(limit)
    )
    return result.scalars().all()

async def grant_trial_period(db: AsyncSession, user_id: int, trial_days: int) -> Optional[User]:
    user = await db.get(User, user_id) # Fetch by primary key user_id
    if not user:
        logger.warning(f"User with DB ID {user_id} not found for granting trial.")
        return None

    now = datetime.datetime.now(datetime.timezone.utc)
    user.trial_start_date = now
    user.trial_end_date = now + datetime.timedelta(days=trial_days)
    user.subscription_status = SubscriptionStatus.TRIAL
    user.current_plan_name = None
    user.subscription_expires_at = None
    user.converted_from_trial = False
    
    try:
        await db.commit()
        await db.refresh(user)
        logger.info(f"Granted {trial_days}-day trial to user ID {user_id} (TG: {user.telegram_id}). Ends: {user.trial_end_date}")
        return user
    except Exception as e:
        logger.error(f"Error granting trial to user ID {user_id}: {e}", exc_info=True)
        await db.rollback()
        return None

async def cancel_trial_period(db: AsyncSession, user_id: int) -> Optional[User]:
    user = await db.get(User, user_id)
    if not user:
        logger.warning(f"User with DB ID {user_id} not found for cancelling trial.")
        return None

    if user.subscription_status == SubscriptionStatus.TRIAL:
        user.subscription_status = SubscriptionStatus.NONE
        user.trial_end_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=1)
        logger.info(f"Cancelled trial for user ID {user_id} (TG: {user.telegram_id}).")
    else:
        logger.warning(f"Attempted to cancel trial for user ID {user_id} (TG: {user.telegram_id}) who is not on trial (status: {user.subscription_status}).")

    try:
        await db.commit()
        await db.refresh(user)
        return user
    except Exception as e:
        logger.error(f"Error cancelling trial for user ID {user_id}: {e}", exc_info=True)
        await db.rollback()
        return None

async def activate_user_subscription(db: AsyncSession, user_id: int, plan_name: str, duration_days: int) -> Optional[User]:
    user = await db.get(User, user_id)
    if not user:
        logger.warning(f"User with DB ID {user_id} not found for activating subscription.")
        return None

    now = datetime.datetime.now(datetime.timezone.utc)
    new_expiration_date = now + datetime.timedelta(days=duration_days)

    # If user has an active subscription, extend it from the current expiration date
    if user.subscription_status == SubscriptionStatus.ACTIVE and user.subscription_expires_at and user.subscription_expires_at > now:
        new_expiration_date = user.subscription_expires_at + datetime.timedelta(days=duration_days)
    
    was_on_trial = user.subscription_status == SubscriptionStatus.TRIAL

    user.subscription_status = SubscriptionStatus.ACTIVE
    user.current_plan_name = plan_name
    user.subscription_expires_at = new_expiration_date
    if was_on_trial:
        user.converted_from_trial = True

    try:
        await db.commit()
        await db.refresh(user)
        logger.info(f"Activated subscription '{plan_name}' for user ID {user_id} (TG: {user.telegram_id}) for {duration_days} days. Expires: {new_expiration_date}")
        return user
    except Exception as e:
        logger.error(f"Error activating subscription for user ID {user_id}: {e}", exc_info=True)
        await db.rollback()
        return None

async def deactivate_user_subscription(db: AsyncSession, user_id: int) -> Optional[User]:
    user = await db.get(User, user_id)
    if not user:
        logger.warning(f"User with DB ID {user_id} not found for deactivating subscription.")
        return None

    if user.subscription_status == SubscriptionStatus.ACTIVE:
        user.subscription_status = SubscriptionStatus.EXPIRED
        user.subscription_expires_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=1)
        logger.info(f"Deactivated subscription for user ID {user_id} (TG: {user.telegram_id}). Plan was: {user.current_plan_name}")
    else:
        logger.warning(f"Attempted to deactivate subscription for user ID {user_id} (TG: {user.telegram_id}) who has no active subscription (status: {user.subscription_status}).")

    try:
        await db.commit()
        await db.refresh(user)
        return user
    except Exception as e:
        logger.error(f"Error deactivating subscription for user ID {user_id}: {e}", exc_info=True)
        await db.rollback()
        return None 