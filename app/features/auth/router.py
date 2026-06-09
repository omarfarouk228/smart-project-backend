from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.features.auth import service
from app.features.auth.schemas import LoginRequest, TokenResponse, RefreshRequest, ChangePasswordRequest
from app.features.users.schemas import UserResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    return await service.login(db, data)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    return await service.refresh(db, data.refresh_token)


@router.post("/logout")
async def logout(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    await service.logout(db, data.refresh_token)
    return {"message": "Déconnecté avec succès"}


@router.post("/change-password")
async def change_password(
    data: ChangePasswordRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await service.change_password(db, user, data)
    return {"message": "Mot de passe modifié avec succès"}


@router.get("/me", response_model=UserResponse)
async def me(user=Depends(get_current_user)):
    return user
