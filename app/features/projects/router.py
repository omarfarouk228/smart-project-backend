import uuid
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.features.users.models import User
from app.features.projects import service
from app.features.projects.schemas import (
    ProjectCreate, ProjectUpdate, ProjectResponse, ProjectListResponse,
    ProjectMemberResponse, AddMemberRequest, ColumnResponse,
)
from app.features.tasks.schemas import BoardResponse, TaskResponse

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _project_response(project, member_count: int | None = None) -> dict:
    count = member_count if member_count is not None else len(project.members)
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "key": project.key,
        "color": project.color,
        "owner_id": project.owner_id,
        "member_count": count,
        "created_at": project.created_at,
        "columns": project.columns,
    }


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    projects, total = await service.get_projects(db, current_user.id, page, page_size)
    items = [ProjectResponse.model_validate(_project_response(p)) for p in projects]
    return ProjectListResponse(items=items, total=total)


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await service.create_project(db, current_user.id, data)
    return ProjectResponse.model_validate(_project_response(project))


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await service.get_project(db, project_id, current_user.id)
    return ProjectResponse.model_validate(_project_response(project))


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    data: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await service.update_project(db, project_id, current_user.id, data)
    return ProjectResponse.model_validate(_project_response(project))


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await service.delete_project(db, project_id, current_user.id)


@router.get("/{project_id}/board", response_model=BoardResponse)
async def get_board(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.features.tasks import service as task_service

    project = await service.get_project(db, project_id, current_user.id)
    tasks = await task_service.get_tasks(db, project_id)

    columns = [
        {"id": str(c.id), "name": c.name, "color": c.color, "position": c.position, "is_done_column": c.is_done_column}
        for c in project.columns
    ]
    task_list = [TaskResponse.model_validate(t) for t in tasks]
    return BoardResponse(columns=columns, tasks=task_list)


@router.get("/{project_id}/members", response_model=list[ProjectMemberResponse])
async def list_members(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await service.get_project(db, project_id, current_user.id)
    members = await service.get_members(db, project_id)
    return [ProjectMemberResponse.model_validate(m) for m in members]


@router.post("/{project_id}/members", response_model=ProjectMemberResponse, status_code=status.HTTP_201_CREATED)
async def add_member(
    project_id: uuid.UUID,
    data: AddMemberRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await service.get_project(db, project_id, current_user.id)
    member = await service.add_member(db, project_id, data)
    return ProjectMemberResponse.model_validate(member)


@router.delete("/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await service.get_project(db, project_id, current_user.id)
    await service.remove_member(db, project_id, user_id)
