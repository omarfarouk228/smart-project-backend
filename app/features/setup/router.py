from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.features.setup import service
from app.features.setup.schemas import SetupPayload, SetupStatus

router = APIRouter(prefix="/api/setup", tags=["setup"])


@router.get("/status", response_model=SetupStatus)
async def get_status(db: AsyncSession = Depends(get_db)):
    completed = await service.is_setup_complete(db)
    return SetupStatus(completed=completed)


@router.post("", status_code=201)
async def run_setup(payload: SetupPayload, db: AsyncSession = Depends(get_db)):
    await service.run_setup(db, payload)
    return {"message": "Setup effectué avec succès"}
