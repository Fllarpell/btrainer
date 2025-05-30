import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import func, and_
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
    last_seen: Optional[datetime.datetime] = None,
    trial_ending_notification_sent: bool = False
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
        last_active_at=last_seen if last_seen else datetime.datetime.now(datetime.timezone.utc),
        trial_ending_notification_sent=trial_ending_notification_sent
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
        "trial_ending_notification_sent"
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
    
    if status != SubscriptionStatus.EXPIRED:
         update_data["trial_ending_notification_sent"] = False

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
    
    values_to_update["trial_ending_notification_sent"] = False

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
            user.trial_ending_notification_sent = False
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
    trial_end = now + datetime.timedelta(days=trial_days)

    user.subscription_status = SubscriptionStatus.TRIAL
    user.trial_start_date = now
    user.trial_end_date = trial_end
    user.trial_ending_notification_sent = False
    user.converted_from_trial = False

    await db.commit()
    await db.refresh(user)
    logger.info(f"Granted {trial_days}-day trial to user {user.telegram_id} (DB ID: {user.id}). Trial ends: {trial_end}")
    return user

async def get_users_trial_ending_soon(db: AsyncSession, hours_before_end: int) -> List[User]:
    now = datetime.datetime.now(datetime.timezone.utc)
    # Calculate the time range for trial ending: between (target_hours - 1) and target_hours from now
    start_window = now + datetime.timedelta(hours=hours_before_end - 1)
    end_window = now + datetime.timedelta(hours=hours_before_end)

    # Ensure end_time_start is not in the past relative to now
    if start_window < now:
        start_window = now

    result = await db.execute(
        select(User).where(
            and_(
                User.subscription_status == SubscriptionStatus.TRIAL,
                User.trial_end_date >= start_window,
                User.trial_end_date < end_window, # Use < to avoid including the exact end time twice
                User.trial_ending_notification_sent == False,
                User.is_blocked == False # Do not send notification to blocked users
            )
        )
    )
    return result.scalars().all()

async def set_trial_ending_notification_sent(db: AsyncSession, user_id: int) -> Optional[User]:
    user = await db.get(User, user_id) # Fetch by primary key user_id
    if user:
        user.trial_ending_notification_sent = True
        await db.commit()
        await db.refresh(user)
        logger.info(f"Marked trial ending notification sent for user DB ID {user_id}.")
        return user
    logger.warning(f"User with DB ID {user_id} not found to mark notification sent.")
    return None

async def reset_trial_ending_notification_sent(db: AsyncSession, user_id: int) -> Optional[User]:
    user = await db.get(User, user_id) # Fetch by primary key user_id
    if user:
        user.trial_ending_notification_sent = False
        await db.commit()
        await db.refresh(user)
        logger.info(f"Reset trial ending notification sent flag for user DB ID {user_id}.")
        return user
    logger.warning(f"User with DB ID {user_id} not found to reset notification sent flag.")
    return None

async def cancel_trial_period(db: AsyncSession, user_id: int) -> Optional[User]:
    user = await db.get(User, user_id)
    if not user:
        logger.warning(f"User with DB ID {user_id} not found for cancelling trial.")
        return None

    if user.subscription_status == SubscriptionStatus.TRIAL:
        user.subscription_status = SubscriptionStatus.EXPIRED # Or NONE, depending on desired final state after cancellation
        user.trial_end_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=1)
        user.trial_ending_notification_sent = False # Reset flag if trial is cancelled manually
        logger.info(f"Cancelled trial for user ID {user_id} (TG: {user.telegram_id}).")
    else:
        logger.warning(f"Attempted to cancel trial for user ID {user_id} (TG: {user.telegram_id}) who is not on trial (status: {user.subscription_status}).")

    await db.commit()
    await db.refresh(user)
    return user

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
    user.trial_ending_notification_sent = False # Reset flag on subscription activation
    if was_on_trial:
        user.converted_from_trial = True

    await db.commit()
    await db.refresh(user)
    logger.info(f"Activated subscription '{plan_name}' for user ID {user_id} (TG: {user.telegram_id}) for {duration_days} days. Expires: {new_expiration_date}")
    return user

async def deactivate_user_subscription(db: AsyncSession, user_id: int) -> Optional[User]:
    user = await db.get(User, user_id)
    if not user:
        logger.warning(f"User with DB ID {user_id} not found for deactivating subscription.")
        return None

    if user.subscription_status == SubscriptionStatus.ACTIVE:
        user.subscription_status = SubscriptionStatus.EXPIRED
        # Set expiration to a time in the past to ensure it's not considered active
        user.subscription_expires_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=1)
        user.trial_ending_notification_sent = False # Reset flag on subscription deactivation (optional, but safe)
        logger.info(f"Deactivated subscription for user ID {user_id} (TG: {user.telegram_id}). Plan was: {user.current_plan_name}")
    else:
        logger.warning(f"Attempted to deactivate subscription for user ID {user_id} (TG: {user.telegram_id}) who has no active subscription (status: {user.subscription_status}).")

    await db.commit()
    await db.refresh(user)
    return user 