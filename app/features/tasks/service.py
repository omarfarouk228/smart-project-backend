import re
import uuid
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from fastapi import HTTPException

from app.features.tasks.models import Task, Label, TaskLabel, SubTask, TaskComment, TimeEntry
from app.features.tasks.schemas import (
    TaskCreate, TaskUpdate, TaskMoveRequest, LabelCreate,
    SubTaskCreate, SubTaskUpdate, CommentCreate, CommentUpdate, TimeEntryCreate,
)
from app.features.notifications.models import NotificationType
from app.core.redis import get_redis
from app.core.config import settings

_MENTION_RE = re.compile(
    r'@\[([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\]'
)


async def _publish(project_id: uuid.UUID, event_type: str, payload: dict):
    try:
        redis = await get_redis()
        await redis.publish(f"project:{project_id}", json.dumps({"type": event_type, **payload}))
    except Exception:
        pass


async def _max_position(db: AsyncSession, column_id: uuid.UUID) -> float:
    result = await db.execute(
        select(func.max(Task.position)).where(Task.column_id == column_id)
    )
    max_pos = result.scalar_one_or_none()
    return (max_pos or 0.0) + 1.0


async def create_task(
    db: AsyncSession, project_id: uuid.UUID, reporter_id: uuid.UUID, data: TaskCreate
) -> Task:
    position = await _max_position(db, data.column_id)
    task = Task(
        project_id=project_id,
        column_id=data.column_id,
        title=data.title,
        description=data.description,
        assignee_id=data.assignee_id,
        reporter_id=reporter_id,
        priority=data.priority,
        position=position,
        due_date=data.due_date,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task, attribute_names=["assignee", "reporter", "labels", "subtasks", "comments"])

    from app.features.tasks.schemas import TaskResponse
    payload = TaskResponse.model_validate(task).model_dump(mode="json")
    await _publish(project_id, "task:created", {"task": payload})
    return task


async def get_tasks(db: AsyncSession, project_id: uuid.UUID) -> list[Task]:
    result = await db.execute(
        select(Task).where(Task.project_id == project_id).order_by(Task.position)
    )
    return list(result.scalars().all())


async def get_task(db: AsyncSession, task_id: uuid.UUID, project_id: uuid.UUID) -> Task:
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.project_id == project_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Tâche introuvable")
    return task


async def update_task(
    db: AsyncSession, task_id: uuid.UUID, project_id: uuid.UUID,
    data: TaskUpdate, actor_id: uuid.UUID | None = None
) -> Task:
    task = await get_task(db, task_id, project_id)
    old_assignee_id = task.assignee_id
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    await db.commit()
    await db.refresh(task, attribute_names=["assignee", "reporter", "labels", "subtasks", "comments", "time_entries"])

    new_assignee_id = task.assignee_id
    if (
        "assignee_id" in data.model_dump(exclude_unset=True)
        and new_assignee_id
        and new_assignee_id != old_assignee_id
        and new_assignee_id != actor_id
    ):
        from app.features.notifications.service import create_notification, send_assigned_email
        await create_notification(
            db, new_assignee_id, NotificationType.assigned,
            f"Vous avez été assigné à « {task.title} »",
            task_id=task.id,
        )
        from app.features.users.models import User
        from app.features.organization.models import Organization
        assignee_result = await db.execute(select(User).where(User.id == new_assignee_id))
        assignee = assignee_result.scalar_one_or_none()
        actor_result = await db.execute(select(User).where(User.id == actor_id)) if actor_id else None
        actor = actor_result.scalar_one_or_none() if actor_result else None
        org_result = await db.execute(select(Organization).limit(1))
        org = org_result.scalar_one_or_none()
        if assignee and org:
            await send_assigned_email(
                org=org,
                to=assignee.email,
                full_name=assignee.full_name,
                assigner=actor.full_name if actor else "Quelqu'un",
                task_title=task.title,
                task_url=f"{settings.FRONTEND_URL}/projects/{project_id}",
            )

    from app.features.tasks.schemas import TaskResponse
    payload = TaskResponse.model_validate(task).model_dump(mode="json")
    await _publish(project_id, "task:updated", {"task": payload})
    return task


async def move_task(
    db: AsyncSession, task_id: uuid.UUID, project_id: uuid.UUID, data: TaskMoveRequest
) -> Task:
    task = await get_task(db, task_id, project_id)
    task.column_id = data.column_id
    task.position = data.position
    await db.commit()
    await db.refresh(task, attribute_names=["assignee", "reporter", "labels", "subtasks", "comments"])

    await _publish(
        project_id,
        "task:moved",
        {"task_id": str(task_id), "column_id": str(data.column_id), "position": data.position},
    )
    return task


async def delete_task(db: AsyncSession, task_id: uuid.UUID, project_id: uuid.UUID) -> None:
    task = await get_task(db, task_id, project_id)
    await db.delete(task)
    await db.commit()
    await _publish(project_id, "task:deleted", {"task_id": str(task_id)})


# ─── Labels ───────────────────────────────────────────────────────────────────

async def get_labels(db: AsyncSession, project_id: uuid.UUID) -> list[Label]:
    result = await db.execute(select(Label).where(Label.project_id == project_id))
    return list(result.scalars().all())


async def create_label(db: AsyncSession, project_id: uuid.UUID, data: LabelCreate) -> Label:
    label = Label(project_id=project_id, name=data.name, color=data.color)
    db.add(label)
    await db.commit()
    await db.refresh(label)
    return label


# ─── Subtasks ─────────────────────────────────────────────────────────────────

async def create_subtask(
    db: AsyncSession, task_id: uuid.UUID, project_id: uuid.UUID, data: SubTaskCreate
) -> SubTask:
    task = await get_task(db, task_id, project_id)
    max_pos = (
        await db.execute(select(func.max(SubTask.position)).where(SubTask.task_id == task_id))
    ).scalar_one_or_none() or 0.0

    subtask = SubTask(task_id=task_id, title=data.title, position=max_pos + 1.0)
    db.add(subtask)
    await db.commit()
    await db.refresh(subtask)
    return subtask


async def update_subtask(
    db: AsyncSession, subtask_id: uuid.UUID, task_id: uuid.UUID, project_id: uuid.UUID,
    data: SubTaskUpdate
) -> SubTask:
    await get_task(db, task_id, project_id)
    result = await db.execute(
        select(SubTask).where(SubTask.id == subtask_id, SubTask.task_id == task_id)
    )
    subtask = result.scalar_one_or_none()
    if not subtask:
        raise HTTPException(status_code=404, detail="Sous-tâche introuvable")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(subtask, field, value)
    await db.commit()
    await db.refresh(subtask)
    return subtask


async def delete_subtask(
    db: AsyncSession, subtask_id: uuid.UUID, task_id: uuid.UUID, project_id: uuid.UUID
) -> None:
    await get_task(db, task_id, project_id)
    result = await db.execute(
        select(SubTask).where(SubTask.id == subtask_id, SubTask.task_id == task_id)
    )
    subtask = result.scalar_one_or_none()
    if not subtask:
        raise HTTPException(status_code=404, detail="Sous-tâche introuvable")
    await db.delete(subtask)
    await db.commit()


# ─── Comments ─────────────────────────────────────────────────────────────────

async def create_comment(
    db: AsyncSession, task_id: uuid.UUID, project_id: uuid.UUID,
    user_id: uuid.UUID, data: CommentCreate
) -> TaskComment:
    task = await get_task(db, task_id, project_id)
    comment = TaskComment(task_id=task_id, user_id=user_id, content=data.content)
    db.add(comment)
    await db.commit()
    await db.refresh(comment, attribute_names=["user"])

    mentioned_ids = {
        uuid.UUID(m) for m in _MENTION_RE.findall(data.content)
        if uuid.UUID(m) != user_id
    }
    if mentioned_ids:
        from app.features.notifications.service import create_notification, send_mention_email
        from app.features.users.models import User
        from app.features.organization.models import Organization
        mentioner_result = await db.execute(select(User).where(User.id == user_id))
        mentioner = mentioner_result.scalar_one_or_none()
        org_result = await db.execute(select(Organization).limit(1))
        org = org_result.scalar_one_or_none()

        for mid in mentioned_ids:
            await create_notification(
                db, mid, NotificationType.mention,
                f"{mentioner.full_name if mentioner else 'Quelqu\'un'} vous a mentionné",
                body=data.content[:200],
                task_id=task_id,
            )
            if mentioner and org:
                mentioned_result = await db.execute(select(User).where(User.id == mid))
                mentioned_user = mentioned_result.scalar_one_or_none()
                if mentioned_user:
                    await send_mention_email(
                        org=org,
                        to=mentioned_user.email,
                        full_name=mentioned_user.full_name,
                        mentioner=mentioner.full_name,
                        task_title=task.title,
                        task_url=f"{settings.FRONTEND_URL}/projects/{project_id}",
                    )

    return comment


async def update_comment(
    db: AsyncSession, comment_id: uuid.UUID, task_id: uuid.UUID,
    project_id: uuid.UUID, user_id: uuid.UUID, data: CommentUpdate
) -> TaskComment:
    await get_task(db, task_id, project_id)
    result = await db.execute(
        select(TaskComment).where(TaskComment.id == comment_id, TaskComment.task_id == task_id)
    )
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="Commentaire introuvable")
    if comment.user_id != user_id:
        raise HTTPException(status_code=403, detail="Accès refusé")
    comment.content = data.content
    await db.commit()
    await db.refresh(comment, attribute_names=["user"])
    return comment


async def delete_comment(
    db: AsyncSession, comment_id: uuid.UUID, task_id: uuid.UUID,
    project_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    await get_task(db, task_id, project_id)
    result = await db.execute(
        select(TaskComment).where(TaskComment.id == comment_id, TaskComment.task_id == task_id)
    )
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="Commentaire introuvable")
    if comment.user_id != user_id:
        raise HTTPException(status_code=403, detail="Accès refusé")
    await db.delete(comment)
    await db.commit()


# ─── Time entries ─────────────────────────────────────────────────────────────

async def create_time_entry(
    db: AsyncSession, task_id: uuid.UUID, project_id: uuid.UUID,
    user_id: uuid.UUID, data: TimeEntryCreate
) -> TimeEntry:
    await get_task(db, task_id, project_id)
    entry = TimeEntry(
        task_id=task_id, user_id=user_id,
        minutes=data.minutes, description=data.description,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry, attribute_names=["user"])
    return entry


async def delete_time_entry(
    db: AsyncSession, entry_id: uuid.UUID, task_id: uuid.UUID,
    project_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    await get_task(db, task_id, project_id)
    result = await db.execute(
        select(TimeEntry).where(TimeEntry.id == entry_id, TimeEntry.task_id == task_id)
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Entrée de temps introuvable")
    if entry.user_id != user_id:
        raise HTTPException(status_code=403, detail="Accès refusé")
    await db.delete(entry)
    await db.commit()
