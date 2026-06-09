import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permissions
from app.features.roles import service
from app.features.roles.schemas import (
    RoleCreate,
    RoleUpdate,
    RoleResponse,
    RoleListResponse,
    PermissionResponse,
)

router = APIRouter(prefix="/api/roles", tags=["roles"])


@router.get(
    "/permissions",
    response_model=list[PermissionResponse],
    dependencies=[Depends(require_permissions("roles.view"))],
)
async def list_permissions(db: AsyncSession = Depends(get_db)):
    return await service.list_permissions(db)


@router.get(
    "",
    response_model=RoleListResponse,
    dependencies=[Depends(require_permissions("roles.view"))],
)
async def list_roles(db: AsyncSession = Depends(get_db)):
    return await service.list_roles(db)


@router.get(
    "/{role_id}",
    response_model=RoleResponse,
    dependencies=[Depends(require_permissions("roles.view"))],
)
async def get_role(role_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await service.get_role(db, role_id)


@router.post(
    "",
    response_model=RoleResponse,
    status_code=201,
    dependencies=[Depends(require_permissions("roles.create"))],
)
async def create_role(data: RoleCreate, db: AsyncSession = Depends(get_db)):
    return await service.create_role(db, data)


@router.patch(
    "/{role_id}",
    response_model=RoleResponse,
    dependencies=[Depends(require_permissions("roles.update"))],
)
async def update_role(role_id: uuid.UUID, data: RoleUpdate, db: AsyncSession = Depends(get_db)):
    return await service.update_role(db, role_id, data)


@router.delete(
    "/{role_id}",
    status_code=204,
    dependencies=[Depends(require_permissions("roles.delete"))],
)
async def delete_role(role_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    await service.delete_role(db, role_id)
