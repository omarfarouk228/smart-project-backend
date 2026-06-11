import uuid
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_permissions
from app.features.users.models import User
from app.features.projects import service
from app.features.projects.dependencies import require_project_role
from app.features.projects.schemas import (
    ProjectCreate, ProjectUpdate, ProjectResponse, ProjectListResponse,
    ProjectMemberResponse, AddMemberRequest, ColumnResponse,
    ColumnCreate, ColumnUpdate, ColumnReorderRequest, DashboardResponse,
    ProjectAnalyticsResponse,
)
from app.features.tasks.schemas import BoardResponse, TaskResponse

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _project_response(project, member_count: int | None = None, current_user_id=None) -> dict:
    count = member_count if member_count is not None else len(project.members)
    my_role = None
    if current_user_id:
        for m in project.members:
            if m.user_id == current_user_id:
                my_role = m.role
                break
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
        "my_role": my_role,
    }


# ─── Dashboard (must come before /{project_id}) ───────────────────────────────

@router.get("/dashboard", response_model=DashboardResponse, tags=["dashboard"])
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stats = await service.get_dashboard_stats(db, current_user.id)
    return DashboardResponse(**stats)


# ─── Projects ─────────────────────────────────────────────────────────────────

@router.get("", response_model=ProjectListResponse)
async def list_projects(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    projects, total = await service.get_projects(db, current_user.id, page, page_size)
    items = [ProjectResponse.model_validate(_project_response(p, current_user_id=current_user.id)) for p in projects]
    return ProjectListResponse(items=items, total=total)


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_permissions("projects.create"))])
async def create_project(
    data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await service.create_project(db, current_user.id, data)
    return ProjectResponse.model_validate(_project_response(project, current_user_id=current_user.id))


@router.get("/{project_id}/analytics", response_model=ProjectAnalyticsResponse)
async def get_project_analytics(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = await service.get_project_analytics(db, project_id, current_user.id)
    return ProjectAnalyticsResponse(**data)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await service.get_project(db, project_id, current_user.id)
    return ProjectResponse.model_validate(_project_response(project, current_user_id=current_user.id))


@router.patch("/{project_id}", response_model=ProjectResponse,
              dependencies=[Depends(require_permissions("projects.update")), Depends(require_project_role("owner"))])
async def update_project(
    project_id: uuid.UUID,
    data: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await service.update_project(db, project_id, current_user.id, data)
    return ProjectResponse.model_validate(_project_response(project, current_user_id=current_user.id))


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_permissions("projects.delete")), Depends(require_project_role("owner"))])
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


# ─── Members ──────────────────────────────────────────────────────────────────

@router.get("/{project_id}/members", response_model=list[ProjectMemberResponse])
async def list_members(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await service.get_project(db, project_id, current_user.id)
    members = await service.get_members(db, project_id)
    return [ProjectMemberResponse.model_validate(m) for m in members]


@router.post("/{project_id}/members", response_model=ProjectMemberResponse, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_permissions("projects.manage_members")), Depends(require_project_role("owner"))])
async def add_member(
    project_id: uuid.UUID,
    data: AddMemberRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await service.get_project(db, project_id, current_user.id)
    member = await service.add_member(db, project_id, data, actor_id=current_user.id)
    return ProjectMemberResponse.model_validate(member)


@router.delete("/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_permissions("projects.manage_members")), Depends(require_project_role("owner"))])
async def remove_member(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await service.get_project(db, project_id, current_user.id)
    await service.remove_member(db, project_id, user_id)


# ─── Columns (reorder before /{column_id} to avoid shadowing) ─────────────────

@router.post("/{project_id}/columns/reorder", response_model=list[ColumnResponse],
             dependencies=[Depends(require_permissions("projects.manage_columns")), Depends(require_project_role("owner"))])
async def reorder_columns(
    project_id: uuid.UUID,
    data: ColumnReorderRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await service.get_project(db, project_id, current_user.id)
    cols = await service.reorder_columns(db, project_id, data.ids)
    return [ColumnResponse.model_validate(c) for c in cols]


@router.post(
    "/{project_id}/columns",
    response_model=ColumnResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions("projects.manage_columns")), Depends(require_project_role("owner"))],
)
async def create_column(
    project_id: uuid.UUID,
    data: ColumnCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await service.get_project(db, project_id, current_user.id)
    col = await service.create_column(db, project_id, data)
    return ColumnResponse.model_validate(col)


@router.patch("/{project_id}/columns/{column_id}", response_model=ColumnResponse,
              dependencies=[Depends(require_permissions("projects.manage_columns")), Depends(require_project_role("owner"))])
async def update_column(
    project_id: uuid.UUID,
    column_id: uuid.UUID,
    data: ColumnUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await service.get_project(db, project_id, current_user.id)
    col = await service.update_column(db, column_id, project_id, data)
    return ColumnResponse.model_validate(col)


@router.delete("/{project_id}/columns/{column_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_permissions("projects.manage_columns")), Depends(require_project_role("owner"))])
async def delete_column(
    project_id: uuid.UUID,
    column_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await service.get_project(db, project_id, current_user.id)
    await service.delete_column(db, column_id, project_id)
