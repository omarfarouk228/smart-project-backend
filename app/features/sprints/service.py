import uuid
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, not_, exists
from sqlalchemy.orm import selectinload
from fastapi import HTTPException

from app.features.sprints.models import Sprint, SprintTask, SprintStatus
from app.features.tasks.models import Task
from app.features.sprints.schemas import SprintCreate, SprintUpdate


async def get_sprints(db: AsyncSession, project_id: uuid.UUID) -> list[Sprint]:
    result = await db.execute(
        select(Sprint)
        .options(selectinload(Sprint.sprint_tasks))
        .where(Sprint.project_id == project_id)
        .order_by(Sprint.created_at.desc())
    )
    return list(result.scalars().all())


async def get_sprint(db: AsyncSession, sprint_id: uuid.UUID, project_id: uuid.UUID) -> Sprint:
    result = await db.execute(
        select(Sprint)
        .options(selectinload(Sprint.sprint_tasks))
        .where(Sprint.id == sprint_id, Sprint.project_id == project_id)
    )
    sprint = result.scalar_one_or_none()
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint introuvable")
    return sprint


async def create_sprint(db: AsyncSession, project_id: uuid.UUID, data: SprintCreate, actor_id: uuid.UUID | None = None) -> Sprint:
    sprint = Sprint(
        project_id=project_id,
        name=data.name,
        goal=data.goal,
        start_date=data.start_date,
        end_date=data.end_date,
    )
    db.add(sprint)
    await db.flush()

    from app.features.audit.service import log as audit_log
    from app.features.audit.models import AuditAction
    await audit_log(db, project_id, actor_id, AuditAction.sprint_created, "sprint", str(sprint.id), sprint.name)

    await db.commit()
    return await get_sprint(db, sprint.id, project_id)


async def update_sprint(
    db: AsyncSession, sprint_id: uuid.UUID, project_id: uuid.UUID, data: SprintUpdate
) -> Sprint:
    sprint = await get_sprint(db, sprint_id, project_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(sprint, field, value)
    await db.commit()
    return await get_sprint(db, sprint_id, project_id)


async def start_sprint(db: AsyncSession, sprint_id: uuid.UUID, project_id: uuid.UUID) -> Sprint:
    sprint = await get_sprint(db, sprint_id, project_id)
    if sprint.status != SprintStatus.planning:
        raise HTTPException(status_code=400, detail="Seul un sprint en planification peut être démarré")

    # Check no other sprint is active
    active = (
        await db.execute(
            select(Sprint).where(
                Sprint.project_id == project_id,
                Sprint.status == SprintStatus.active,
            )
        )
    ).scalar_one_or_none()
    if active:
        raise HTTPException(status_code=409, detail="Un sprint est déjà actif pour ce projet")

    sprint.status = SprintStatus.active
    if not sprint.start_date:
        sprint.start_date = date.today()

    from app.features.audit.service import log as audit_log
    from app.features.audit.models import AuditAction
    await audit_log(db, project_id, None, AuditAction.sprint_started, "sprint", str(sprint_id), sprint.name)

    await db.commit()
    return await get_sprint(db, sprint_id, project_id)


async def complete_sprint(db: AsyncSession, sprint_id: uuid.UUID, project_id: uuid.UUID) -> Sprint:
    sprint = await get_sprint(db, sprint_id, project_id)
    if sprint.status != SprintStatus.active:
        raise HTTPException(status_code=400, detail="Seul un sprint actif peut être terminé")
    sprint.status = SprintStatus.completed
    if not sprint.end_date:
        sprint.end_date = date.today()

    from app.features.audit.service import log as audit_log
    from app.features.audit.models import AuditAction
    await audit_log(db, project_id, None, AuditAction.sprint_completed, "sprint", str(sprint_id), sprint.name)

    await db.commit()
    return await get_sprint(db, sprint_id, project_id)


async def delete_sprint(db: AsyncSession, sprint_id: uuid.UUID, project_id: uuid.UUID) -> None:
    sprint = await get_sprint(db, sprint_id, project_id)
    if sprint.status == SprintStatus.active:
        raise HTTPException(status_code=400, detail="Impossible de supprimer un sprint actif")
    await db.delete(sprint)
    await db.commit()


async def add_task_to_sprint(
    db: AsyncSession, sprint_id: uuid.UUID, project_id: uuid.UUID, task_id: uuid.UUID
) -> None:
    sprint = await get_sprint(db, sprint_id, project_id)

    # Verify task belongs to project
    task = (
        await db.execute(select(Task).where(Task.id == task_id, Task.project_id == project_id))
    ).scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Tâche introuvable")

    existing = (
        await db.execute(
            select(SprintTask).where(SprintTask.sprint_id == sprint_id, SprintTask.task_id == task_id)
        )
    ).scalar_one_or_none()
    if existing:
        return  # already in sprint, idempotent

    db.add(SprintTask(sprint_id=sprint_id, task_id=task_id))
    await db.commit()


async def remove_task_from_sprint(
    db: AsyncSession, sprint_id: uuid.UUID, project_id: uuid.UUID, task_id: uuid.UUID
) -> None:
    await get_sprint(db, sprint_id, project_id)
    st = (
        await db.execute(
            select(SprintTask).where(SprintTask.sprint_id == sprint_id, SprintTask.task_id == task_id)
        )
    ).scalar_one_or_none()
    if not st:
        raise HTTPException(status_code=404, detail="Tâche non trouvée dans le sprint")
    await db.delete(st)
    await db.commit()


async def get_sprint_tasks(db: AsyncSession, sprint_id: uuid.UUID) -> list[Task]:
    result = await db.execute(
        select(Task)
        .join(SprintTask, SprintTask.task_id == Task.id)
        .where(SprintTask.sprint_id == sprint_id)
        .order_by(Task.position)
    )
    return list(result.scalars().all())


async def get_backlog_tasks(db: AsyncSession, project_id: uuid.UUID) -> list[Task]:
    """Tasks not assigned to any sprint."""
    in_sprint_subq = select(SprintTask.task_id)
    result = await db.execute(
        select(Task)
        .where(Task.project_id == project_id, not_(Task.id.in_(in_sprint_subq)))
        .order_by(Task.position)
    )
    return list(result.scalars().all())
