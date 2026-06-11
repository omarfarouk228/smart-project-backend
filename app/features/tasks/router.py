import uuid
from typing import Optional
from fastapi import APIRouter, Depends, status, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_permissions
from app.features.projects.dependencies import require_project_role
from app.features.users.models import User
from app.features.projects import service as project_service
from app.features.tasks import service as task_service
from app.features.tasks.schemas import (
    TaskCreate, TaskUpdate, TaskMoveRequest, TaskResponse, TaskDetailResponse,
    LabelCreate, LabelResponse,
    SubTaskCreate, SubTaskUpdate, SubTaskResponse,
    CommentCreate, CommentUpdate, CommentResponse,
    TimeEntryCreate, TimeEntryResponse,
    AttachmentResponse,
)

router = APIRouter(prefix="/api/projects", tags=["tasks"])
my_tasks_router = APIRouter(prefix="/api/tasks", tags=["tasks"])


async def _check_member(db, project_id, user_id):
    await project_service.get_project(db, project_id, user_id)


# ─── My tasks (top-level) ────────────────────────────────────────────────────

@my_tasks_router.get("", response_model=list[TaskResponse])
async def get_my_tasks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tasks = await task_service.get_my_tasks(db, current_user.id)
    return [TaskResponse.model_validate(t) for t in tasks]


# ─── Tasks ────────────────────────────────────────────────────────────────────

@router.get("/{project_id}/tasks", response_model=list[TaskResponse],
            dependencies=[Depends(require_permissions("tasks.view"))])
async def list_tasks(
    project_id: uuid.UUID,
    search: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    assignee_id: Optional[uuid.UUID] = Query(None),
    label_id: Optional[uuid.UUID] = Query(None),
    due_before: Optional[str] = Query(None),
    due_after: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(db, project_id, current_user.id)
    tasks = await task_service.get_tasks(
        db, project_id,
        search=search, priority=priority, assignee_id=assignee_id,
        label_id=label_id, due_before=due_before, due_after=due_after,
    )
    return [TaskResponse.model_validate(t) for t in tasks]


@router.post("/{project_id}/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_permissions("tasks.create")), Depends(require_project_role("member"))])
async def create_task(
    project_id: uuid.UUID,
    data: TaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(db, project_id, current_user.id)
    task = await task_service.create_task(db, project_id, current_user.id, data)
    return TaskResponse.model_validate(task)


@router.get("/{project_id}/tasks/{task_id}", response_model=TaskDetailResponse,
            dependencies=[Depends(require_permissions("tasks.view"))])
async def get_task(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(db, project_id, current_user.id)
    task = await task_service.get_task(db, task_id, project_id)
    return TaskDetailResponse.model_validate(task)


@router.patch("/{project_id}/tasks/{task_id}", response_model=TaskResponse,
              dependencies=[Depends(require_permissions("tasks.update")), Depends(require_project_role("member"))])
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


@router.post("/{project_id}/tasks/{task_id}/move", response_model=TaskResponse,
             dependencies=[Depends(require_permissions("tasks.update")), Depends(require_project_role("member"))])
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


@router.delete("/{project_id}/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_permissions("tasks.delete")), Depends(require_project_role("member"))])
async def delete_task(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(db, project_id, current_user.id)
    await task_service.delete_task(db, task_id, project_id, actor_id=current_user.id)


# ─── Labels ───────────────────────────────────────────────────────────────────

@router.get("/{project_id}/labels", response_model=list[LabelResponse],
            dependencies=[Depends(require_permissions("tasks.view"))])
async def list_labels(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(db, project_id, current_user.id)
    labels = await task_service.get_labels(db, project_id)
    return [LabelResponse.model_validate(l) for l in labels]


@router.post("/{project_id}/labels", response_model=LabelResponse, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_permissions("tasks.update"))])
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
    dependencies=[Depends(require_permissions("tasks.update"))],
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


@router.patch("/{project_id}/tasks/{task_id}/subtasks/{subtask_id}", response_model=SubTaskResponse,
              dependencies=[Depends(require_permissions("tasks.update"))])
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
    dependencies=[Depends(require_permissions("tasks.update"))],
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
    dependencies=[Depends(require_permissions("tasks.comment"))],
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


@router.patch("/{project_id}/tasks/{task_id}/comments/{comment_id}", response_model=CommentResponse,
              dependencies=[Depends(require_permissions("tasks.comment"))])
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
    dependencies=[Depends(require_permissions("tasks.comment"))],
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
    dependencies=[Depends(require_permissions("tasks.update"))],
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
    dependencies=[Depends(require_permissions("tasks.update"))],
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


# ─── Labels assignment ────────────────────────────────────────────────────────

@router.post(
    "/{project_id}/tasks/{task_id}/labels/{label_id}",
    response_model=TaskResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permissions("tasks.update"))],
)
async def add_label(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    label_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(db, project_id, current_user.id)
    task = await task_service.add_label_to_task(db, task_id, project_id, label_id)
    return TaskResponse.model_validate(task)


@router.delete(
    "/{project_id}/tasks/{task_id}/labels/{label_id}",
    response_model=TaskResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permissions("tasks.update"))],
)
async def remove_label(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    label_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(db, project_id, current_user.id)
    task = await task_service.remove_label_from_task(db, task_id, project_id, label_id)
    return TaskResponse.model_validate(task)


# ─── Attachments ─────────────────────────────────────────────────────────────

@router.post(
    "/{project_id}/tasks/{task_id}/attachments",
    response_model=AttachmentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions("tasks.update"))],
)
async def upload_attachment(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(db, project_id, current_user.id)
    content = await file.read()
    attachment = await task_service.upload_attachment(
        db, task_id, project_id, current_user.id, content, file.filename or "fichier"
    )
    return AttachmentResponse.model_validate(attachment)


@router.delete(
    "/{project_id}/tasks/{task_id}/attachments/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions("tasks.update"))],
)
async def delete_attachment(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    attachment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(db, project_id, current_user.id)
    await task_service.delete_attachment(db, attachment_id, task_id, project_id, current_user.id)
