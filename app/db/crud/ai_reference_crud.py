import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, update, delete
from typing import Optional, List, Dict, Any

from ..models import AIReference, AISourceType # Ensure AISourceType is imported if used in function signatures or type hints for data

import logging
logger = logging.getLogger(__name__)

async def create_ai_reference(db: AsyncSession, source_data: Dict[str, Any]) -> AIReference:
    """
    Creates a new AI reference source.
    source_data should be a dictionary with keys like 'source_type', 'description', 'url', etc.
    Example: {'source_type': AISourceType.URL, 'description': 'Example URL', 'url': 'http://example.com'}
    """
    # Ensure source_type is an enum member if passed as string
    if isinstance(source_data.get('source_type'), str):
        try:
            source_data['source_type'] = AISourceType[source_data['source_type'].upper()]
        except KeyError:
            # Handle invalid string for source_type, perhaps raise ValueError or use a default
            logger.error(f"Invalid source_type string: {source_data.get('source_type')}")
            raise ValueError(f"Invalid source_type: {source_data.get('source_type')}")

    db_source = AIReference(**source_data)
    db.add(db_source)
    await db.commit()
    await db.refresh(db_source)
    logger.info(f"Created AI Reference: ID {db_source.id}, Type: {db_source.source_type}, Desc: {db_source.description[:50]}")
    return db_source

async def get_ai_reference(db: AsyncSession, reference_id: int) -> Optional[AIReference]:
    """Gets a single AI reference by its ID."""
    return await db.get(AIReference, reference_id)

async def get_all_ai_references(
    db: AsyncSession, 
    skip: int = 0, 
    limit: int = 100,
    is_active: Optional[bool] = None
) -> List[AIReference]:
    """Gets all AI references, optionally filtered by is_active status, with pagination."""
    stmt = select(AIReference).order_by(AIReference.id).offset(skip).limit(limit)
    if is_active is not None:
        stmt = stmt.filter(AIReference.is_active == is_active)
    
    result = await db.execute(stmt)
    return result.scalars().all()

async def count_ai_references(db: AsyncSession, is_active: Optional[bool] = None) -> int:
    """Counts AI references, optionally filtered by is_active status."""
    stmt = select(func.count(AIReference.id))
    if is_active is not None:
        stmt = stmt.filter(AIReference.is_active == is_active)
    result = await db.execute(stmt)
    return result.scalar_one()


async def update_ai_reference(db: AsyncSession, reference_id: int, update_data: Dict[str, Any]) -> Optional[AIReference]:
    """
    Updates an existing AI reference.
    update_data should be a dictionary with fields to update.
    Example: {'description': 'New Description', 'is_active': False}
    """
    db_source = await get_ai_reference(db, reference_id)
    if not db_source:
        return None

    # Ensure source_type is an enum member if passed as string and being updated
    if 'source_type' in update_data and isinstance(update_data['source_type'], str):
        try:
            update_data['source_type'] = AISourceType[update_data['source_type'].upper()]
        except KeyError:
            logger.error(f"Invalid source_type string in update: {update_data['source_type']}")
            raise ValueError(f"Invalid source_type for update: {update_data['source_type']}")

    for key, value in update_data.items():
        if hasattr(db_source, key):
            setattr(db_source, key, value)
        else:
            logger.warning(f"Attempted to update non-existent attribute '{key}' on AIReference ID {reference_id}")

    db_source.updated_at = datetime.datetime.now(datetime.timezone.utc) # Manually update timestamp
    
    await db.commit()
    await db.refresh(db_source)
    logger.info(f"Updated AI Reference: ID {db_source.id}")
    return db_source

async def delete_ai_reference(db: AsyncSession, reference_id: int) -> bool:
    """Deletes an AI reference by its ID. Returns True if deletion was successful, False otherwise."""
    db_source = await get_ai_reference(db, reference_id)
    if not db_source:
        logger.warning(f"Attempted to delete non-existent AI Reference ID {reference_id}")
        return False
    
    await db.delete(db_source)
    await db.commit()
    logger.info(f"Deleted AI Reference: ID {reference_id}")
    return True

async def get_active_ai_references_for_prompt(db: AsyncSession) -> List[Dict[str, str]]:
    """
    Gets all active AI references formatted specifically for inclusion in an AI prompt.
    Returns a list of dictionaries, e.g., [{'source_type': 'url', 'description': 'Some description', 'url': 'http://...'}]
    """
    stmt = select(AIReference.source_type, AIReference.description, AIReference.url, AIReference.citation_details).filter(AIReference.is_active == True).order_by(AIReference.id)
    result = await db.execute(stmt)
    
    formatted_sources = []
    for row in result.mappings().all(): # .mappings() gives us dict-like rows
        source_entry = {
            "type": row.source_type.value, # Get the string value of the enum
            "description": row.description
        }
        if row.url:
            source_entry["url"] = row.url
        if row.citation_details:
            source_entry["citation"] = row.citation_details
        formatted_sources.append(source_entry)
        
    return formatted_sources 