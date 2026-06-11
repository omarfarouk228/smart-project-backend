import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.features.users.models import User
from app.features.projects import service as project_service
from app.features.audit import service as audit_service
from app.features.audit.schemas import AuditLogResponse

router = APIRouter(prefix="/api/projects", tags=["audit"])


@router.get("/{project_id}/audit-log", response_model=list[AuditLogResponse])
async def get_audit_log(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await project_service.get_project(db, project_id, current_user.id)
    logs = await audit_service.get_logs(db, project_id)
    return [AuditLogResponse.model_validate(l) for l in logs]
