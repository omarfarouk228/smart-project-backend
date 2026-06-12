import os
import uuid
from typing import Optional

import aiofiles
from fastapi import HTTPException, status
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.security import hash_password, generate_password
from app.features.organization.models import Organization
from app.features.roles.models import Role, UserRole
from app.features.users.models import User
from app.features.users.schemas import UserCreate, UserUpdate, UserResponse, UserListResponse


async def get_organization(db: AsyncSession) -> Optional[Organization]:
    result = await db.execute(select(Organization).limit(1))
    return result.scalar_one_or_none()


async def list_users(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
) -> UserListResponse:
    query = select(User).options(selectinload(User.roles))
    if search:
        query = query.where(
            User.email.ilike(f"%{search}%")
            | User.first_name.ilike(f"%{search}%")
            | User.last_name.ilike(f"%{search}%")
        )

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar_one()

    query = query.offset((page - 1) * page_size).limit(page_size).order_by(User.created_at.desc())
    users = (await db.execute(query)).scalars().all()

    return UserListResponse(
        items=[UserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
    )


async def get_user(db: AsyncSession, user_id: uuid.UUID) -> User:
    result = await db.execute(
        select(User).options(selectinload(User.roles)).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable")
    return user


async def create_user(db: AsyncSession, data: UserCreate) -> tuple[User, str]:
    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email déjà utilisé")

    password = generate_password()
    user = User(
        email=data.email,
        hashed_password=hash_password(password),
        first_name=data.first_name,
        last_name=data.last_name,
        must_change_password=True,
    )
    db.add(user)
    await db.flush()

    if data.role_ids:
        roles = (await db.execute(select(Role).where(Role.id.in_(data.role_ids)))).scalars().all()
        for role in roles:
            db.add(UserRole(user_id=user.id, role_id=role.id))

    await db.commit()
    await db.refresh(user)
    return user, password


async def update_user(db: AsyncSession, user_id: uuid.UUID, data: UserUpdate) -> User:
    user = await get_user(db, user_id)

    if data.first_name is not None:
        user.first_name = data.first_name
    if data.last_name is not None:
        user.last_name = data.last_name
    if data.email is not None and data.email != user.email:
        existing = await db.execute(select(User).where(User.email == data.email))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email déjà utilisé")
        user.email = data.email
    if data.is_active is not None:
        user.is_active = data.is_active

    if data.role_ids is not None:
        await db.execute(delete(UserRole).where(UserRole.user_id == user_id))
        await db.flush()
        for role_id in data.role_ids:
            db.add(UserRole(user_id=user_id, role_id=role_id))

    await db.commit()
    await db.refresh(user)
    return user


async def delete_user(db: AsyncSession, user_id: uuid.UUID, current_user_id: uuid.UUID) -> None:
    if user_id == current_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Impossible de supprimer votre propre compte")
    user = await get_user(db, user_id)
    if user.is_superadmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Impossible de supprimer un super administrateur")
    await db.delete(user)
    await db.commit()


async def reset_user_password(db: AsyncSession, user_id: uuid.UUID) -> tuple[User, str]:
    user = await get_user(db, user_id)
    new_password = generate_password()
    user.hashed_password = hash_password(new_password)
    user.must_change_password = True
    await db.commit()
    return user, new_password


async def upload_avatar(
    db: AsyncSession, user_id: uuid.UUID, content: bytes, filename: str
) -> User:
    user = await get_user(db, user_id)
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext not in ("jpg", "jpeg", "png", "webp"):
        raise HTTPException(status_code=400, detail="Format non supporté (jpg, png, webp)")

    storage_dir = os.path.join(settings.STORAGE_PATH, "avatars")
    os.makedirs(storage_dir, exist_ok=True)
    file_name = f"{user_id}.{ext}"
    async with aiofiles.open(os.path.join(storage_dir, file_name), "wb") as f:
        await f.write(content)

    user.avatar_path = f"avatars/{file_name}"
    await db.commit()
    return user
