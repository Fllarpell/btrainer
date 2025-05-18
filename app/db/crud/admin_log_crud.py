from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload
from typing import Optional

from app.db.models import AdminLog, User


async def create_admin_log(
    db: AsyncSession, admin_user_id: int, action: str, target_user_id: int | None = None, details: Optional[str] = None
) -> AdminLog:
    db_log = AdminLog(
        admin_user_id=admin_user_id, action=action, target_user_id=target_user_id, details=details
    )
    db.add(db_log)
    await db.flush()
    await db.refresh(db_log)
    return db_log


async def get_admin_logs(
    db: AsyncSession, skip: int = 0, limit: int = 100
) -> list[AdminLog]:
    result = await db.execute(
        select(AdminLog)
        .options(joinedload(AdminLog.admin), joinedload(AdminLog.target_user))
        .order_by(AdminLog.timestamp.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


async def get_admin_logs_by_admin(db: AsyncSession, admin_id: int) -> list[AdminLog]:
    result = await db.execute(
        select(AdminLog)
        .where(AdminLog.admin_id == admin_id)
        .options(joinedload(AdminLog.target_user))
        .order_by(AdminLog.timestamp.desc())
    )
    return result.scalars().all() 