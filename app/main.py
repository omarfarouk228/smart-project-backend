import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.middleware import SetupMiddleware
from app.core.state import app_state
from app.features.auth.router import router as auth_router
from app.features.notifications.router import router as notifications_router
from app.features.organization.router import router as organization_router
from app.features.projects.router import router as projects_router
from app.features.roles.router import router as roles_router
from app.features.sprints.router import router as sprints_router
from app.features.setup.router import router as setup_router
from app.features.tasks.router import router as tasks_router
from app.features.users.router import router as users_router
from app.features.websockets.router import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.features.organization.models import Organization

    for sub in ("logos", "avatars", "attachments"):
        os.makedirs(os.path.join(settings.STORAGE_PATH, sub), exist_ok=True)

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Organization).limit(1))
        org = result.scalar_one_or_none()
        if org and org.setup_completed:
            app_state.setup_completed = True

    yield


app = FastAPI(title="SmartTask API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SetupMiddleware)

_storage = os.path.abspath(settings.STORAGE_PATH)
os.makedirs(_storage, exist_ok=True)
app.mount("/storage", StaticFiles(directory=_storage), name="storage")

app.include_router(setup_router)
app.include_router(auth_router)
app.include_router(notifications_router)
app.include_router(users_router)
app.include_router(roles_router)
app.include_router(organization_router)
app.include_router(projects_router)
app.include_router(tasks_router)
app.include_router(sprints_router)
app.include_router(ws_router)


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "version": "1.0.0"}
