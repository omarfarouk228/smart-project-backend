from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permissions
from app.features.organization import service
from app.features.organization.models import Organization
from app.features.organization.schemas import OrganizationPublic, OrganizationUpdate, SMTPConfig

router = APIRouter(prefix="/api/organization", tags=["organization"])

_DEFAULT_PUBLIC = {
    "id": "00000000-0000-0000-0000-000000000000",
    "name": "ProjectEyes",
    "app_name": "ProjectEyes",
    "logo_path": None,
    "favicon_path": None,
    "primary_color": "#6366f1",
    "secondary_color": "#8b5cf6",
    "accent_color": "#06b6d4",
    "default_theme": "light",
    "setup_completed": False,
}


@router.get("/public", response_model=OrganizationPublic)
async def get_public(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Organization).limit(1))
    org = result.scalar_one_or_none()
    if not org:
        return OrganizationPublic(**_DEFAULT_PUBLIC)
    return OrganizationPublic.model_validate(org)


@router.get(
    "",
    response_model=OrganizationPublic,
    dependencies=[Depends(require_permissions("organization.view"))],
)
async def get_organization(db: AsyncSession = Depends(get_db)):
    return OrganizationPublic.model_validate(await service.get_organization(db))


@router.patch(
    "",
    response_model=OrganizationPublic,
    dependencies=[Depends(require_permissions("organization.update"))],
)
async def update_organization(data: OrganizationUpdate, db: AsyncSession = Depends(get_db)):
    return OrganizationPublic.model_validate(await service.update_organization(db, data))


@router.put(
    "/smtp",
    response_model=OrganizationPublic,
    dependencies=[Depends(require_permissions("organization.update"))],
)
async def update_smtp(data: SMTPConfig, db: AsyncSession = Depends(get_db)):
    return OrganizationPublic.model_validate(await service.update_smtp(db, data))


@router.post(
    "/logo",
    response_model=OrganizationPublic,
    dependencies=[Depends(require_permissions("organization.update"))],
)
async def upload_logo(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    content = await file.read()
    return OrganizationPublic.model_validate(
        await service.upload_logo(db, content, file.filename or "logo.png")
    )
