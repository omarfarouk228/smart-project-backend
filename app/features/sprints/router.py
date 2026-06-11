import uuid
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_permissions
from app.features.projects.dependencies import require_project_role
from app.features.users.models import User
from app.features.projects import service as project_service
from app.features.sprints import service as sprint_service
from app.features.tasks.schemas import TaskResponse
from app.features.sprints.schemas import (
    SprintCreate, SprintUpdate, SprintResponse, SprintWithTasksResponse,
    SprintBoardResponse, BacklogResponse,
)

router = APIRouter(prefix="/api/projects", tags=["sprints"])


async def _check_member(db, project_id, user_id):
    await project_service.get_project(db, project_id, user_id)


@router.get("/{project_id}/sprints", response_model=list[SprintResponse],
            dependencies=[Depends(require_permissions("sprints.view"))])
async def list_sprints(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(db, project_id, current_user.id)
    sprints = await sprint_service.get_sprints(db, project_id)
    return [SprintResponse.model_validate(s) for s in sprints]


@router.post("/{project_id}/sprints", response_model=SprintResponse, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_permissions("sprints.create")), Depends(require_project_role("member"))])
async def create_sprint(
    project_id: uuid.UUID,
    data: SprintCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(db, project_id, current_user.id)
    sprint = await sprint_service.create_sprint(db, project_id, data, actor_id=current_user.id)
    return SprintResponse.model_validate(sprint)


@router.get("/{project_id}/sprints/{sprint_id}", response_model=SprintResponse,
            dependencies=[Depends(require_permissions("sprints.view"))])
async def get_sprint(
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(db, project_id, current_user.id)
    sprint = await sprint_service.get_sprint(db, sprint_id, project_id)
    return SprintResponse.model_validate(sprint)


@router.patch("/{project_id}/sprints/{sprint_id}", response_model=SprintResponse,
              dependencies=[Depends(require_permissions("sprints.update")), Depends(require_project_role("member"))])
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


@router.delete("/{project_id}/sprints/{sprint_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_permissions("sprints.delete")), Depends(require_project_role("owner"))])
async def delete_sprint(
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(db, project_id, current_user.id)
    await sprint_service.delete_sprint(db, sprint_id, project_id)


@router.post("/{project_id}/sprints/{sprint_id}/start", response_model=SprintResponse,
             dependencies=[Depends(require_permissions("sprints.manage")), Depends(require_project_role("owner"))])
async def start_sprint(
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(db, project_id, current_user.id)
    sprint = await sprint_service.start_sprint(db, sprint_id, project_id)
    return SprintResponse.model_validate(sprint)


@router.post("/{project_id}/sprints/{sprint_id}/complete", response_model=SprintResponse,
             dependencies=[Depends(require_permissions("sprints.manage")), Depends(require_project_role("owner"))])
async def complete_sprint(
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(db, project_id, current_user.id)
    sprint = await sprint_service.complete_sprint(db, sprint_id, project_id)
    return SprintResponse.model_validate(sprint)


@router.get("/{project_id}/sprints/{sprint_id}/board", response_model=SprintBoardResponse,
            dependencies=[Depends(require_permissions("sprints.view"))])
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


@router.get("/{project_id}/backlog", response_model=BacklogResponse,
            dependencies=[Depends(require_permissions("sprints.view"))])
async def get_backlog(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(db, project_id, current_user.id)
    tasks = await sprint_service.get_backlog_tasks(db, project_id)
    sprints = await sprint_service.get_sprints(db, project_id)

    sprints_with_tasks = []
    for sprint in sprints:
        sprint_tasks = await sprint_service.get_sprint_tasks(db, sprint.id)
        sprints_with_tasks.append(
            SprintWithTasksResponse(
                **SprintResponse.model_validate(sprint).model_dump(),
                tasks=[TaskResponse.model_validate(t) for t in sprint_tasks],
            )
        )

    return BacklogResponse(
        tasks=[TaskResponse.model_validate(t) for t in tasks],
        sprints=sprints_with_tasks,
    )


@router.post("/{project_id}/sprints/{sprint_id}/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT,
             dependencies=[Depends(require_permissions("sprints.update"))])
async def add_task_to_sprint(
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(db, project_id, current_user.id)
    await sprint_service.add_task_to_sprint(db, sprint_id, project_id, task_id)


@router.delete("/{project_id}/sprints/{sprint_id}/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_permissions("sprints.update"))])
async def remove_task_from_sprint(
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(db, project_id, current_user.id)
    await sprint_service.remove_task_from_sprint(db, sprint_id, project_id, task_id)
