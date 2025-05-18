from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload # Needed for get_solutions_by_user
from typing import List, Optional

# Assuming Solution and Case models are in ..models
from ..models import Solution, Case # Case might be needed for selectinload

async def create_solution(
    db: AsyncSession, 
    case_id: int, 
    user_id: int,
    solution_text: str, 
    ai_analysis: Optional[str] = None
) -> Solution:
    db_solution = Solution(
        case_id=case_id, 
        user_id=user_id,
        solution_text=solution_text, 
        ai_analysis_text=ai_analysis
    )
    db.add(db_solution)
    await db.flush()
    await db.refresh(db_solution)
    return db_solution

async def get_solution(db: AsyncSession, solution_id: int) -> Optional[Solution]:
    return await db.get(Solution, solution_id)

async def get_solutions_for_case(db: AsyncSession, case_id: int, skip: int = 0, limit: int = 100) -> List[Solution]:
    result = await db.execute(
        select(Solution).filter(Solution.case_id == case_id).order_by(Solution.submitted_at.desc()).offset(skip).limit(limit)
    )
    return result.scalars().all()

async def get_solutions_by_user(db: AsyncSession, user_id: int, skip: int = 0, limit: int = 100) -> List[Solution]:
    result = await db.execute(
        select(Solution)
        .where(Solution.user_id == user_id)
        .options(selectinload(Solution.case)) # Eager load the related Case
        .order_by(Solution.submitted_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

async def update_solution_ratings(
    db: AsyncSession, 
    solution_id: int, 
    user_rating_of_case: Optional[int] = None, 
    user_rating_of_analysis: Optional[int] = None
) -> Optional[Solution]:
    db_solution = await get_solution(db, solution_id) # Use the get_solution from this file
    if db_solution:
        if user_rating_of_case is not None:
            db_solution.user_rating_of_case = user_rating_of_case
        if user_rating_of_analysis is not None:
            db_solution.user_rating_of_analysis = user_rating_of_analysis
        # await db.flush() # Consider if flush/commit is needed here or handled by caller
        # await db.refresh(db_solution)
    return db_solution

async def count_solutions_by_user(db: AsyncSession, user_id: int) -> int: # Moved from case_crud.py
    result = await db.execute(
        select(func.count(Solution.id)).where(Solution.user_id == user_id)
    )
    return result.scalar_one()

async def count_solutions_by_user_and_rating( # Moved from case_crud.py
    db: AsyncSession, 
    user_id: int, 
    target_rating: str
) -> int:
    # Assuming solution_rating is stored as a key in a JSON string in ai_analysis_text
    # This search pattern is specific, ensure it matches your actual data structure
    search_pattern = f'%"solution_rating": "{target_rating}"%' 
    
    result = await db.execute(
        select(func.count(Solution.id))
        .where(
            Solution.user_id == user_id,
            Solution.ai_analysis_text.ilike(search_pattern) 
        )
    )
    return result.scalar_one() 