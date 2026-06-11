import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.features.audit.models import AuditLog, AuditAction


async def log(
    db: AsyncSession,
    project_id: uuid.UUID,
    user_id: uuid.UUID | None,
    action: AuditAction,
    entity_type: str,
    entity_id: str | None = None,
    entity_name: str | None = None,
    details: dict | None = None,
) -> None:
    entry = AuditLog(
        project_id=project_id,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_name=entity_name,
        details=details,
    )
    db.add(entry)
    # Flush but don't commit — caller's transaction will commit it
    await db.flush()


async def get_logs(
    db: AsyncSession, project_id: uuid.UUID, limit: int = 100
) -> list[AuditLog]:
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.project_id == project_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
