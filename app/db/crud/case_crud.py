from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
# from sqlalchemy.orm import selectinload # No longer needed here
from typing import List, Optional

from ..models import Case # Solution model is no longer directly used here

async def create_case(db: AsyncSession, title: str, case_text: str, ai_model_used: Optional[str] = None, prompt_version: Optional[str] = None) -> Case:
    db_case = Case(
        title=title, 
        case_text=case_text, 
        ai_model_used=ai_model_used,
        prompt_version=prompt_version
    )
    db.add(db_case)
    await db.flush()
    await db.refresh(db_case)

    return db_case

async def get_case(db: AsyncSession, case_id: int) -> Optional[Case]:
    return await db.get(Case, case_id)

async def get_cases(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[Case]:
    result = await db.execute(select(Case).order_by(Case.id.desc()).offset(skip).limit(limit))
    return result.scalars().all()

async def get_random_case(db: AsyncSession) -> Optional[Case]:
    result = await db.execute(select(Case).order_by(func.random()))
    return result.scalars().first()

async def count_all_cases(db: AsyncSession) -> int:
    result = await db.execute(select(func.count(Case.id)))
    return result.scalar_one()

# Functions related to Solution have been moved to solution_crud.py
