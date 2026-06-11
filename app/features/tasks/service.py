import os
import re
import uuid
import json
import mimetypes
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete as sa_delete
from sqlalchemy.orm import selectinload
from fastapi import HTTPException
import aiofiles

from app.features.tasks.models import Task, Label, TaskLabel, SubTask, TaskComment, TimeEntry, TaskAttachment
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
    await db.flush()

    from app.features.audit.service import log as audit_log
    from app.features.audit.models import AuditAction
    await audit_log(db, project_id, reporter_id, AuditAction.task_created, "task", str(task.id), task.title)

    await db.commit()
    await db.refresh(task, attribute_names=["assignee", "reporter", "labels", "subtasks", "comments", "attachments", "time_entries"])

    # Notify assignee if one was set at creation
    if task.assignee_id and task.assignee_id != reporter_id:
        from app.features.notifications.service import create_notification, send_assigned_email
        from app.features.users.models import User
        from app.features.organization.models import Organization
        await create_notification(
            db, task.assignee_id, NotificationType.assigned,
            f"Vous avez été assigné à « {task.title} »",
            task_id=task.id,
        )
        reporter_result = await db.execute(select(User).where(User.id == reporter_id))
        reporter = reporter_result.scalar_one_or_none()
        org_result = await db.execute(select(Organization).limit(1))
        org = org_result.scalar_one_or_none()
        if task.assignee and org:
            await send_assigned_email(
                org=org,
                to=task.assignee.email,
                full_name=task.assignee.full_name,
                assigner=reporter.full_name if reporter else "Quelqu'un",
                task_title=task.title,
                task_url=f"{settings.FRONTEND_URL}/projects/{project_id}",
            )

    from app.features.tasks.schemas import TaskResponse
    payload = TaskResponse.model_validate(task).model_dump(mode="json")
    await _publish(project_id, "task:created", {"task": payload})
    return task


async def get_tasks(
    db: AsyncSession,
    project_id: uuid.UUID,
    *,
    search: str | None = None,
    priority: str | None = None,
    assignee_id: uuid.UUID | None = None,
    label_id: uuid.UUID | None = None,
    due_before: str | None = None,
    due_after: str | None = None,
) -> list[Task]:
    from datetime import date as date_type
    from sqlalchemy import and_, or_, cast
    from sqlalchemy import Date as SADate

    q = select(Task).where(Task.project_id == project_id)

    if search:
        q = q.where(Task.title.ilike(f"%{search}%"))
    if priority:
        q = q.where(Task.priority == priority)
    if assignee_id:
        q = q.where(Task.assignee_id == assignee_id)
    if label_id:
        q = q.join(TaskLabel, and_(TaskLabel.task_id == Task.id, TaskLabel.label_id == label_id))
    if due_before:
        try:
            q = q.where(Task.due_date <= date_type.fromisoformat(due_before))
        except ValueError:
            pass
    if due_after:
        try:
            q = q.where(Task.due_date >= date_type.fromisoformat(due_after))
        except ValueError:
            pass

    result = await db.execute(
        q.options(
            selectinload(Task.assignee),
            selectinload(Task.reporter),
            selectinload(Task.labels),
            selectinload(Task.subtasks),
            selectinload(Task.time_entries),
            selectinload(Task.attachments),
        ).order_by(Task.position)
    )
    return list(result.scalars().all())


_TASK_EAGER = [
    selectinload(Task.assignee),
    selectinload(Task.reporter),
    selectinload(Task.labels),
    selectinload(Task.subtasks),
    selectinload(Task.comments),
    selectinload(Task.time_entries),
    selectinload(Task.attachments),
]


async def get_task(db: AsyncSession, task_id: uuid.UUID, project_id: uuid.UUID) -> Task:
    result = await db.execute(
        select(Task)
        .options(*_TASK_EAGER)
        .where(Task.id == task_id, Task.project_id == project_id)
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
    from app.features.audit.service import log as audit_log
    from app.features.audit.models import AuditAction
    changed = list(data.model_dump(exclude_unset=True).keys())
    await audit_log(db, project_id, actor_id, AuditAction.task_updated, "task", str(task_id), task.title, {"fields": changed})

    await db.commit()
    task = await get_task(db, task_id, project_id)

    new_assignee_id = task.assignee_id
    from app.features.notifications.service import create_notification, send_assigned_email
    from app.features.users.models import User
    from app.features.organization.models import Organization

    if (
        "assignee_id" in data.model_dump(exclude_unset=True)
        and new_assignee_id
        and new_assignee_id != old_assignee_id
        and new_assignee_id != actor_id
    ):
        await create_notification(
            db, new_assignee_id, NotificationType.assigned,
            f"Vous avez été assigné à « {task.title} »",
            task_id=task.id,
        )
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

    # Notify current assignee when meaningful fields change (no email to avoid spam)
    _NOTIF_FIELDS = {"title", "priority", "due_date", "column_id", "description"}
    updated_fields = set(data.model_dump(exclude_unset=True).keys())
    notifiable_changes = updated_fields & _NOTIF_FIELDS
    if (
        notifiable_changes
        and task.assignee_id
        and task.assignee_id != actor_id
        and not ("assignee_id" in updated_fields and new_assignee_id != old_assignee_id)
    ):
        field_labels = {
            "title": "titre", "priority": "priorité", "due_date": "date d'échéance",
            "column_id": "statut", "description": "description",
        }
        changed_labels = ", ".join(field_labels[f] for f in notifiable_changes if f in field_labels)
        await create_notification(
            db, task.assignee_id, NotificationType.task_updated,
            f"La tâche « {task.title} » a été mise à jour",
            body=f"Champ(s) modifié(s) : {changed_labels}",
            task_id=task.id,
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
    task = await get_task(db, task_id, project_id)

    await _publish(
        project_id,
        "task:moved",
        {"task_id": str(task_id), "column_id": str(data.column_id), "position": data.position},
    )
    return task


async def delete_task(db: AsyncSession, task_id: uuid.UUID, project_id: uuid.UUID, actor_id: uuid.UUID | None = None) -> None:
    task = await get_task(db, task_id, project_id)
    title = task.title
    await db.delete(task)

    from app.features.audit.service import log as audit_log
    from app.features.audit.models import AuditAction
    await audit_log(db, project_id, actor_id, AuditAction.task_deleted, "task", str(task_id), title)

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

        actor_name = mentioner.full_name if mentioner else "Quelqu’un"
        for mid in mentioned_ids:
            await create_notification(
                db, mid, NotificationType.mention,
                f"{actor_name} vous a mentionné",
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


# ─── Labels assignment ────────────────────────────────────────────────────────

async def add_label_to_task(
    db: AsyncSession, task_id: uuid.UUID, project_id: uuid.UUID, label_id: uuid.UUID
) -> Task:
    task = await get_task(db, task_id, project_id)
    label = (await db.execute(
        select(Label).where(Label.id == label_id, Label.project_id == project_id)
    )).scalar_one_or_none()
    if not label:
        raise HTTPException(status_code=404, detail="Étiquette introuvable")

    existing = (await db.execute(
        select(TaskLabel).where(TaskLabel.task_id == task_id, TaskLabel.label_id == label_id)
    )).scalar_one_or_none()
    if not existing:
        db.add(TaskLabel(task_id=task_id, label_id=label_id))
        await db.commit()
        await db.refresh(task, attribute_names=["labels"])
    return task


async def remove_label_from_task(
    db: AsyncSession, task_id: uuid.UUID, project_id: uuid.UUID, label_id: uuid.UUID
) -> Task:
    task = await get_task(db, task_id, project_id)
    await db.execute(
        sa_delete(TaskLabel).where(TaskLabel.task_id == task_id, TaskLabel.label_id == label_id)
    )
    await db.commit()
    await db.refresh(task, attribute_names=["labels"])
    return task


# ─── Attachments ─────────────────────────────────────────────────────────────

async def upload_attachment(
    db: AsyncSession, task_id: uuid.UUID, project_id: uuid.UUID,
    uploader_id: uuid.UUID, content: bytes, filename: str
) -> TaskAttachment:
    await get_task(db, task_id, project_id)

    if len(content) > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Fichier trop volumineux")

    storage_dir = os.path.join(settings.STORAGE_PATH, "attachments", str(task_id))
    os.makedirs(storage_dir, exist_ok=True)

    safe_name = f"{uuid.uuid4()}_{filename}"
    file_path = os.path.join(storage_dir, safe_name)
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    relative_path = f"attachments/{task_id}/{safe_name}"
    mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

    attachment = TaskAttachment(
        task_id=task_id,
        uploader_id=uploader_id,
        filename=filename,
        file_path=relative_path,
        file_size=len(content),
        mime_type=mime_type,
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment, attribute_names=["uploader"])
    return attachment


async def delete_attachment(
    db: AsyncSession, attachment_id: uuid.UUID, task_id: uuid.UUID,
    project_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    await get_task(db, task_id, project_id)
    result = await db.execute(
        select(TaskAttachment).where(
            TaskAttachment.id == attachment_id, TaskAttachment.task_id == task_id
        )
    )
    attachment = result.scalar_one_or_none()
    if not attachment:
        raise HTTPException(status_code=404, detail="Pièce jointe introuvable")
    if attachment.uploader_id != user_id:
        raise HTTPException(status_code=403, detail="Accès refusé")

    full_path = os.path.join(settings.STORAGE_PATH, attachment.file_path)
    if os.path.exists(full_path):
        os.remove(full_path)

    await db.delete(attachment)
    await db.commit()


# ─── My tasks ────────────────────────────────────────────────────────────────

async def get_my_tasks(db: AsyncSession, user_id: uuid.UUID) -> list[Task]:
    from app.features.projects.models import ProjectMember
    result = await db.execute(
        select(Task)
        .join(ProjectMember, ProjectMember.project_id == Task.project_id)
        .where(Task.assignee_id == user_id, ProjectMember.user_id == user_id)
        .options(
            selectinload(Task.assignee),
            selectinload(Task.reporter),
            selectinload(Task.labels),
            selectinload(Task.subtasks),
            selectinload(Task.time_entries),
            selectinload(Task.attachments),
        )
        .order_by(Task.due_date.asc().nulls_last(), Task.created_at.desc())
    )
    return list(result.scalars().all())
