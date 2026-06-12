import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_permissions
from app.features.notifications.service import send_welcome_email, send_password_reset_email
from app.features.users import service
from app.features.users.models import User
from app.features.users.schemas import UserCreate, UserUpdate, UserResponse, UserListResponse

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get(
    "",
    response_model=UserListResponse,
    dependencies=[Depends(require_permissions("users.view"))],
)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    return await service.list_users(db, page, page_size, search)


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    dependencies=[Depends(require_permissions("users.view"))],
)
async def get_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await service.get_user(db, user_id)


@router.post(
    "",
    response_model=UserResponse,
    status_code=201,
    dependencies=[Depends(require_permissions("users.create"))],
)
async def create_user(data: UserCreate, db: AsyncSession = Depends(get_db)):
    user, password = await service.create_user(db, data)
    org = await service.get_organization(db)
    if org:
        await send_welcome_email(org, user.email, user.full_name, password)
    return UserResponse.model_validate(user)


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    dependencies=[Depends(require_permissions("users.update"))],
)
async def update_user(user_id: uuid.UUID, data: UserUpdate, db: AsyncSession = Depends(get_db)):
    return await service.update_user(db, user_id, data)


@router.post(
    "/{user_id}/reset-password",
    dependencies=[Depends(require_permissions("users.update"))],
)
async def reset_password(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    user, new_password = await service.reset_user_password(db, user_id)
    org = await service.get_organization(db)
    if org:
        await send_password_reset_email(org, user.email, user.full_name, new_password)
    return {"message": "Mot de passe réinitialisé et envoyé par email"}


@router.delete(
    "/{user_id}",
    status_code=204,
    dependencies=[Depends(require_permissions("users.delete"))],
)
async def delete_user(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await service.delete_user(db, user_id, current_user.id)


@router.post("/{user_id}/avatar", response_model=UserResponse)
async def upload_avatar(
    user_id: uuid.UUID,
    file: UploadFile = File(...),
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if file.size and file.size > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Fichier trop volumineux")
    content = await file.read()
    return await service.upload_avatar(db, user_id, content, file.filename or "avatar.jpg")
