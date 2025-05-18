from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload
import datetime
from typing import Optional, Dict, Any

from app.db.models import Feedback, User, Solution


async def create_feedback(
    db: AsyncSession,
    user_id: int,
    text: str,
    is_meaningful_ai: Optional[bool] = None,
    ai_analysis_reason: Optional[str] = None,
    ai_analysis_category: Optional[str] = None,
    raw_ai_response: Optional[Dict[str, Any]] = None
) -> Feedback:
    db_feedback = Feedback(
        user_id=user_id,
        text=text,
        is_meaningful_ai=is_meaningful_ai,
        ai_analysis_reason=ai_analysis_reason,
        ai_analysis_category=ai_analysis_category,
        raw_ai_response=raw_ai_response
        # submitted_at will be set by the database default
    )
    db.add(db_feedback)
    await db.commit()
    await db.refresh(db_feedback)
    return db_feedback


async def get_feedback_by_id(db: AsyncSession, feedback_id: int) -> Feedback | None:
    result = await db.execute(
        select(Feedback)
        .where(Feedback.id == feedback_id)
        .options(joinedload(Feedback.solution).joinedload(Solution.user))
    )
    return result.scalars().first()


async def get_feedback_by_solution(
    db: AsyncSession, solution_id: int
) -> list[Feedback]:
    result = await db.execute(
        select(Feedback)
        .where(Feedback.solution_id == solution_id)
        .order_by(Feedback.created_at.desc())
    )
    return result.scalars().all()


async def get_feedback_by_user(db: AsyncSession, user_id: int) -> list[Feedback]:
    result = await db.execute(
        select(Feedback)
        .join(Feedback.solution)
        .where(Solution.user_id == user_id)
        .order_by(Feedback.created_at.desc())
    )
    return result.scalars().all() 