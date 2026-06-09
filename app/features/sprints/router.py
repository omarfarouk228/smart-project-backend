import uuid
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.features.users.models import User
from app.features.projects import service as project_service
from app.features.sprints import service as sprint_service
from app.features.tasks.schemas import TaskResponse
from app.features.sprints.schemas import (
    SprintCreate, SprintUpdate, SprintResponse, SprintBoardResponse, BacklogResponse,
)

router = APIRouter(prefix="/api/projects", tags=["sprints"])


async def _check_member(db, project_id, user_id):
    await project_service.get_project(db, project_id, user_id)


@router.get("/{project_id}/sprints", response_model=list[SprintResponse])
async def list_sprints(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(db, project_id, current_user.id)
    sprints = await sprint_service.get_sprints(db, project_id)
    return [SprintResponse.model_validate(s) for s in sprints]


@router.post("/{project_id}/sprints", response_model=SprintResponse, status_code=status.HTTP_201_CREATED)
async def create_sprint(
    project_id: uuid.UUID,
    data: SprintCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(db, project_id, current_user.id)
    sprint = await sprint_service.create_sprint(db, project_id, data)
    return SprintResponse.model_validate(sprint)


@router.get("/{project_id}/sprints/{sprint_id}", response_model=SprintResponse)
async def get_sprint(
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(db, project_id, current_user.id)
    sprint = await sprint_service.get_sprint(db, sprint_id, project_id)
    return SprintResponse.model_validate(sprint)


@router.patch("/{project_id}/sprints/{sprint_id}", response_model=SprintResponse)
async def update_sprint(
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
    data: SprintUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(db, project_id, current_user.id)
    sprint = await sprint_service.update_sprint(db, sprint_id, project_id, data)
    return SprintResponse.model_validate(sprint)


@router.delete("/{project_id}/sprints/{sprint_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sprint(
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(db, project_id, current_user.id)
    await sprint_service.delete_sprint(db, sprint_id, project_id)


@router.post("/{project_id}/sprints/{sprint_id}/start", response_model=SprintResponse)
async def start_sprint(
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(db, project_id, current_user.id)
    sprint = await sprint_service.start_sprint(db, sprint_id, project_id)
    return SprintResponse.model_validate(sprint)


@router.post("/{project_id}/sprints/{sprint_id}/complete", response_model=SprintResponse)
async def complete_sprint(
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(db, project_id, current_user.id)
    sprint = await sprint_service.complete_sprint(db, sprint_id, project_id)
    return SprintResponse.model_validate(sprint)


@router.get("/{project_id}/sprints/{sprint_id}/board", response_model=SprintBoardResponse)
async def get_sprint_board(
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await _check_member(db, project_id, current_user.id) or await project_service.get_project(db, project_id, current_user.id)
    sprint = await sprint_service.get_sprint(db, sprint_id, project_id)
    tasks = await sprint_service.get_sprint_tasks(db, sprint_id)

    from app.features.projects import service as ps
    proj = await ps.get_project(db, project_id, current_user.id)
    columns = [
        {"id": str(c.id), "name": c.name, "color": c.color, "position": c.position, "is_done_column": c.is_done_column}
        for c in proj.columns
    ]
    return SprintBoardResponse(
        sprint=SprintResponse.model_validate(sprint),
        columns=columns,
        tasks=[TaskResponse.model_validate(t) for t in tasks],
    )


@router.get("/{project_id}/backlog", response_model=BacklogResponse)
async def get_backlog(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(db, project_id, current_user.id)
    tasks = await sprint_service.get_backlog_tasks(db, project_id)
    sprints = await sprint_service.get_sprints(db, project_id)
    return BacklogResponse(
        tasks=[TaskResponse.model_validate(t) for t in tasks],
        sprints=[SprintResponse.model_validate(s) for s in sprints],
    )


@router.post("/{project_id}/sprints/{sprint_id}/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def add_task_to_sprint(
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(db, project_id, current_user.id)
    await sprint_service.add_task_to_sprint(db, sprint_id, project_id, task_id)


@router.delete("/{project_id}/sprints/{sprint_id}/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_task_from_sprint(
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(db, project_id, current_user.id)
    await sprint_service.remove_task_from_sprint(db, sprint_id, project_id, task_id)
