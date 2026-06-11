import uuid
from fastapi import Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.features.users.models import User

_ROLE_ORDER = {"viewer": 0, "member": 1, "owner": 2}


def require_project_role(min_role: str):
    async def _dep(
        project_id: uuid.UUID = Path(...),
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ):
        from app.features.projects import service
        role = await service.get_member_role(db, project_id, current_user.id)
        if _ROLE_ORDER.get(role, -1) < _ROLE_ORDER.get(min_role, 0):
            raise HTTPException(
                status_code=403,
                detail=f"Rôle projet insuffisant (requis : {min_role})",
            )
    return _dep
