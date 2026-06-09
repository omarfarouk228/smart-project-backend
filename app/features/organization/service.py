import os
import uuid

import aiofiles
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.features.organization.models import Organization
from app.features.organization.schemas import OrganizationUpdate, SMTPConfig


async def get_organization(db: AsyncSession) -> Organization:
    result = await db.execute(select(Organization).limit(1))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=500, detail="Organisation non configurée")
    return org


async def update_organization(db: AsyncSession, data: OrganizationUpdate) -> Organization:
    org = await get_organization(db)
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(org, field, value)
    await db.commit()
    await db.refresh(org)
    return org


async def update_smtp(db: AsyncSession, data: SMTPConfig) -> Organization:
    org = await get_organization(db)
    org.smtp_host = data.smtp_host
    org.smtp_port = data.smtp_port
    org.smtp_user = data.smtp_user
    org.smtp_password = data.smtp_password
    org.smtp_from = data.smtp_from
    org.smtp_ssl = data.smtp_ssl
    org.smtp_configured = True
    await db.commit()
    await db.refresh(org)
    return org


async def upload_logo(db: AsyncSession, content: bytes, filename: str) -> Organization:
    org = await get_organization(db)
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext not in ("jpg", "jpeg", "png", "webp", "svg"):
        raise HTTPException(status_code=400, detail="Format non supporté")

    storage_dir = os.path.join(settings.STORAGE_PATH, "logos")
    os.makedirs(storage_dir, exist_ok=True)
    file_name = f"logo_{uuid.uuid4()}.{ext}"
    async with aiofiles.open(os.path.join(storage_dir, file_name), "wb") as f:
        await f.write(content)

    org.logo_path = f"logos/{file_name}"
    await db.commit()
    await db.refresh(org)
    return org
