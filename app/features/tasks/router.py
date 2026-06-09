import uuid
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.features.users.models import User
from app.features.projects import service as project_service
from app.features.tasks import service as task_service
from app.features.tasks.schemas import (
    TaskCreate, TaskUpdate, TaskMoveRequest, TaskResponse, TaskDetailResponse,
    LabelCreate, LabelResponse,
    SubTaskCreate, SubTaskUpdate, SubTaskResponse,
    CommentCreate, CommentUpdate, CommentResponse,
    TimeEntryCreate, TimeEntryResponse,
)

router = APIRouter(prefix="/api/projects", tags=["tasks"])


async def _check_member(db, project_id, user_id):
    await project_service.get_project(db, project_id, user_id)


# ─── Tasks ────────────────────────────────────────────────────────────────────

@router.get("/{project_id}/tasks", response_model=list[TaskResponse])
async def list_tasks(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(db, project_id, current_user.id)
    tasks = await task_service.get_tasks(db, project_id)
    return [TaskResponse.model_validate(t) for t in tasks]


@router.post("/{project_id}/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    project_id: uuid.UUID,
    data: TaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(db, project_id, current_user.id)
    task = await task_service.create_task(db, project_id, current_user.id, data)
    return TaskResponse.model_validate(task)


@router.get("/{project_id}/tasks/{task_id}", response_model=TaskDetailResponse)
async def get_task(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(db, project_id, current_user.id)
    task = await task_service.get_task(db, task_id, project_id)
    return TaskDetailResponse.model_validate(task)


@router.patch("/{project_id}/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    data: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(db, project_id, current_user.id)
    task = await task_service.update_task(db, task_id, project_id, data, actor_id=current_user.id)
    return TaskResponse.model_validate(task)


@router.post("/{project_id}/tasks/{task_id}/move", response_model=TaskResponse)
async def move_task(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    data: TaskMoveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(db, project_id, current_user.id)
    task = await task_service.move_task(db, task_id, project_id, data)
    return TaskResponse.model_validate(task)


@router.delete("/{project_id}/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(db, project_id, current_user.id)
    await task_service.delete_task(db, task_id, project_id)


# ─── Labels ───────────────────────────────────────────────────────────────────

@router.get("/{project_id}/labels", response_model=list[LabelResponse])
async def list_labels(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(db, project_id, current_user.id)
    labels = await task_service.get_labels(db, project_id)
    return [LabelResponse.model_validate(l) for l in labels]


@router.post("/{project_id}/labels", response_model=LabelResponse, status_code=status.HTTP_201_CREATED)
async def create_label(
    project_id: uuid.UUID,
    data: LabelCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(db, project_id, current_user.id)
    label = await task_service.create_label(db, project_id, data)
    return LabelResponse.model_validate(label)


# ─── Subtasks ─────────────────────────────────────────────────────────────────

@router.post(
    "/{project_id}/tasks/{task_id}/subtasks",
    response_model=SubTaskResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_subtask(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    data: SubTaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(db, project_id, current_user.id)
    return SubTaskResponse.model_validate(
        await task_service.create_subtask(db, task_id, project_id, data)
    )


@router.patch("/{project_id}/tasks/{task_id}/subtasks/{subtask_id}", response_model=SubTaskResponse)
async def update_subtask(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    subtask_id: uuid.UUID,
    data: SubTaskUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(db, project_id, current_user.id)
    return SubTaskResponse.model_validate(
        await task_service.update_subtask(db, subtask_id, task_id, project_id, data)
    )


@router.delete(
    "/{project_id}/tasks/{task_id}/subtasks/{subtask_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_subtask(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    subtask_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(db, project_id, current_user.id)
    await task_service.delete_subtask(db, subtask_id, task_id, project_id)


# ─── Comments ─────────────────────────────────────────────────────────────────

@router.post(
    "/{project_id}/tasks/{task_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_comment(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    data: CommentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(db, project_id, current_user.id)
    return CommentResponse.model_validate(
        await task_service.create_comment(db, task_id, project_id, current_user.id, data)
    )


@router.patch("/{project_id}/tasks/{task_id}/comments/{comment_id}", response_model=CommentResponse)
async def update_comment(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    comment_id: uuid.UUID,
    data: CommentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(db, project_id, current_user.id)
    return CommentResponse.model_validate(
        await task_service.update_comment(db, comment_id, task_id, project_id, current_user.id, data)
    )


@router.delete(
    "/{project_id}/tasks/{task_id}/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_comment(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    comment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(db, project_id, current_user.id)
    await task_service.delete_comment(db, comment_id, task_id, project_id, current_user.id)


# ─── Time entries ─────────────────────────────────────────────────────────────

@router.post(
    "/{project_id}/tasks/{task_id}/time-entries",
    response_model=TimeEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_time_entry(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    data: TimeEntryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(db, project_id, current_user.id)
    return TimeEntryResponse.model_validate(
        await task_service.create_time_entry(db, task_id, project_id, current_user.id, data)
    )


@router.delete(
    "/{project_id}/tasks/{task_id}/time-entries/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_time_entry(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    entry_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(db, project_id, current_user.id)
    await task_service.delete_time_entry(db, entry_id, task_id, project_id, current_user.id)
