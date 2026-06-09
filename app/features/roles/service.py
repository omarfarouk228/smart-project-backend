import uuid
from fastapi import HTTPException, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.features.roles.models import Role, Permission, RolePermission
from app.features.roles.schemas import (
    RoleCreate,
    RoleUpdate,
    RoleResponse,
    RoleListResponse,
    PermissionResponse,
)


async def list_permissions(db: AsyncSession) -> list[PermissionResponse]:
    result = await db.execute(
        select(Permission).order_by(Permission.category, Permission.name)
    )
    return [PermissionResponse.model_validate(p) for p in result.scalars().all()]


async def list_roles(db: AsyncSession) -> RoleListResponse:
    result = await db.execute(
        select(Role).options(selectinload(Role.permissions)).order_by(Role.created_at)
    )
    roles = result.scalars().all()
    return RoleListResponse(
        items=[RoleResponse.model_validate(r) for r in roles],
        total=len(roles),
    )


async def get_role(db: AsyncSession, role_id: uuid.UUID) -> Role:
    result = await db.execute(
        select(Role).options(selectinload(Role.permissions)).where(Role.id == role_id)
    )
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rôle introuvable")
    return role


async def create_role(db: AsyncSession, data: RoleCreate) -> Role:
    existing = await db.execute(select(Role).where(Role.name == data.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ce nom de rôle existe déjà")

    role = Role(name=data.name, description=data.description, color=data.color)
    db.add(role)
    await db.flush()

    if data.permission_ids:
        perms = (
            await db.execute(select(Permission).where(Permission.id.in_(data.permission_ids)))
        ).scalars().all()
        for p in perms:
            db.add(RolePermission(role_id=role.id, permission_id=p.id))

    await db.commit()
    await db.refresh(role)
    return role


async def update_role(db: AsyncSession, role_id: uuid.UUID, data: RoleUpdate) -> Role:
    role = await get_role(db, role_id)

    if data.name and data.name != role.name:
        if role.is_system:
            raise HTTPException(status_code=400, detail="Impossible de renommer un rôle système")
        existing = await db.execute(
            select(Role).where(Role.name == data.name, Role.id != role_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Ce nom de rôle existe déjà")
        role.name = data.name

    if data.description is not None:
        role.description = data.description
    if data.color is not None:
        role.color = data.color

    if data.permission_ids is not None:
        await db.execute(delete(RolePermission).where(RolePermission.role_id == role_id))
        await db.flush()
        for perm_id in data.permission_ids:
            db.add(RolePermission(role_id=role_id, permission_id=perm_id))

    await db.commit()
    await db.refresh(role)
    return role


async def delete_role(db: AsyncSession, role_id: uuid.UUID) -> None:
    role = await get_role(db, role_id)
    if role.is_system:
        raise HTTPException(status_code=400, detail="Impossible de supprimer un rôle système")
    await db.delete(role)
    await db.commit()
