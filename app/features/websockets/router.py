import asyncio
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.core.redis import get_redis
from app.features.projects.models import ProjectMember

router = APIRouter(tags=["websockets"])


@router.websocket("/api/ws/{project_id}")
async def ws_project(
    websocket: WebSocket,
    project_id: str,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    # Validate JWT
    try:
        payload = decode_token(token)
        user_id = uuid.UUID(payload.get("sub", ""))
    except Exception:
        await websocket.close(code=4001, reason="Invalid token")
        return

    # Check project membership
    member = (
        await db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == uuid.UUID(project_id),
                ProjectMember.user_id == user_id,
            )
        )
    ).scalar_one_or_none()

    if not member:
        await websocket.close(code=4003, reason="Not a project member")
        return

    await websocket.accept()

    redis = await get_redis()
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"project:{project_id}")

    async def forward_redis():
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    await websocket.send_text(message["data"])
                except Exception:
                    break

    async def keep_alive():
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass

    redis_task = asyncio.create_task(forward_redis())
    client_task = asyncio.create_task(keep_alive())

    try:
        done, pending = await asyncio.wait(
            [redis_task, client_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for t in pending:
            t.cancel()
    finally:
        await pubsub.unsubscribe(f"project:{project_id}")
        await pubsub.aclose()
