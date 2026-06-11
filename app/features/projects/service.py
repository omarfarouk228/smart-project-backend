import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from fastapi import HTTPException

from app.core.config import settings
from app.features.projects.models import Project, ProjectMember, Column
from app.features.projects.schemas import (
    ProjectCreate, ProjectUpdate, AddMemberRequest,
    ColumnCreate, ColumnUpdate,
)

DEFAULT_COLUMNS = [
    {"name": "À faire", "color": "#94a3b8", "position": 0, "is_done_column": False},
    {"name": "En cours", "color": "#3b82f6", "position": 1, "is_done_column": False},
    {"name": "Terminé", "color": "#10b981", "position": 2, "is_done_column": True},
]


async def create_project(db: AsyncSession, owner_id: uuid.UUID, data: ProjectCreate) -> Project:
    project = Project(
        name=data.name,
        description=data.description,
        key=data.key.upper(),
        color=data.color,
        owner_id=owner_id,
    )
    db.add(project)
    await db.flush()

    for col_data in DEFAULT_COLUMNS:
        db.add(Column(project_id=project.id, **col_data))

    db.add(ProjectMember(project_id=project.id, user_id=owner_id, role="owner"))
    await db.commit()
    await db.refresh(project, attribute_names=["columns", "members", "owner"])
    return project


async def get_projects(
    db: AsyncSession, user_id: uuid.UUID, page: int = 1, page_size: int = 20
) -> tuple[list[Project], int]:
    base = (
        select(Project)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(ProjectMember.user_id == user_id)
    )
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    projects = (
        await db.execute(
            base.options(
                selectinload(Project.columns),
                selectinload(Project.members),
            )
            .order_by(Project.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return list(projects), total


async def get_project(db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID) -> Project:
    result = await db.execute(
        select(Project)
        .options(
            selectinload(Project.columns),
            selectinload(Project.members),
        )
        .where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Projet introuvable")

    member = (
        await db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=403, detail="Accès refusé")

    return project


async def update_project(
    db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID, data: ProjectUpdate
) -> Project:
    project = await get_project(db, project_id, user_id)
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(project, field, value)
    await db.commit()
    await db.refresh(project)
    return project


async def delete_project(db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID) -> None:
    project = await get_project(db, project_id, user_id)
    await db.delete(project)
    await db.commit()


async def get_members(db: AsyncSession, project_id: uuid.UUID) -> list[ProjectMember]:
    result = await db.execute(
        select(ProjectMember)
        .where(ProjectMember.project_id == project_id)
        .options(selectinload(ProjectMember.user))
        .order_by(ProjectMember.joined_at)
    )
    return list(result.scalars().all())


async def get_member_role(db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID) -> str:
    member = (
        await db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=403, detail="Accès refusé")
    return member.role


async def add_member(
    db: AsyncSession, project_id: uuid.UUID, data: AddMemberRequest,
    actor_id: uuid.UUID | None = None,
) -> ProjectMember:
    existing = (
        await db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == data.user_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Déjà membre du projet")

    member = ProjectMember(project_id=project_id, user_id=data.user_id, role=data.role)
    db.add(member)
    await db.commit()
    await db.refresh(member, attribute_names=["user"])

    from app.features.audit.service import log as audit_log
    from app.features.audit.models import AuditAction
    await audit_log(
        db, project_id, actor_id, AuditAction.member_added, "member",
        str(data.user_id), member.user.full_name, {"role": data.role},
    )
    await db.commit()

    # Notify the added user (in-app + email)
    if data.user_id != actor_id:
        from app.features.notifications.models import NotificationType
        from app.features.notifications.service import create_notification, send_project_added_email
        from app.features.users.models import User
        from app.features.organization.models import Organization

        project_result = await db.execute(select(Project).where(Project.id == project_id))
        project = project_result.scalar_one_or_none()

        actor_result = await db.execute(select(User).where(User.id == actor_id)) if actor_id else None
        actor = actor_result.scalar_one_or_none() if actor_result else None
        actor_name = actor.full_name if actor else "Un administrateur"

        if project:
            await create_notification(
                db, data.user_id, NotificationType.project_added,
                f"Vous avez été ajouté au projet « {project.name} »",
                body=f"Ajouté par {actor_name} — rôle : {data.role}",
            )
            user_result = await db.execute(select(User).where(User.id == data.user_id))
            user = user_result.scalar_one_or_none()
            org_result = await db.execute(select(Organization).limit(1))
            org = org_result.scalar_one_or_none()
            if user and org:
                await send_project_added_email(
                    org=org,
                    to=user.email,
                    full_name=user.full_name,
                    adder=actor_name,
                    project_name=project.name,
                    role=data.role,
                    project_url=f"{settings.FRONTEND_URL}/projects/{project_id}",
                )

    return member


async def remove_member(
    db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    member = (
        await db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Membre introuvable")
    if member.role == "owner":
        owner_count = (
            await db.execute(
                select(func.count(ProjectMember.id)).where(
                    ProjectMember.project_id == project_id,
                    ProjectMember.role == "owner",
                )
            )
        ).scalar_one()
        if owner_count <= 1:
            raise HTTPException(status_code=400, detail="Le projet doit avoir au moins un propriétaire")

    await db.refresh(member, attribute_names=["user"])
    member_name = member.user.full_name if member.user else str(user_id)

    await db.delete(member)

    from app.features.audit.service import log as audit_log
    from app.features.audit.models import AuditAction
    await audit_log(
        db, project_id, None, AuditAction.member_removed, "member",
        str(user_id), member_name, None,
    )

    await db.commit()


# ─── Column CRUD ──────────────────────────────────────────────────────────────

async def _get_column(db: AsyncSession, column_id: uuid.UUID, project_id: uuid.UUID) -> Column:
    col = (
        await db.execute(
            select(Column).where(Column.id == column_id, Column.project_id == project_id)
        )
    ).scalar_one_or_none()
    if not col:
        raise HTTPException(status_code=404, detail="Colonne introuvable")
    return col


async def create_column(
    db: AsyncSession, project_id: uuid.UUID, data: ColumnCreate
) -> Column:
    max_pos = (
        await db.execute(
            select(func.max(Column.position)).where(Column.project_id == project_id)
        )
    ).scalar_one_or_none() or -1

    col = Column(
        project_id=project_id,
        name=data.name,
        color=data.color,
        position=max_pos + 1,
        is_done_column=data.is_done_column,
    )
    db.add(col)
    await db.commit()
    await db.refresh(col)
    return col


async def update_column(
    db: AsyncSession, column_id: uuid.UUID, project_id: uuid.UUID, data: ColumnUpdate
) -> Column:
    col = await _get_column(db, column_id, project_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(col, field, value)
    await db.commit()
    await db.refresh(col)
    return col


async def delete_column(
    db: AsyncSession, column_id: uuid.UUID, project_id: uuid.UUID
) -> None:
    col = await _get_column(db, column_id, project_id)
    # Verify at least one column will remain
    count = (
        await db.execute(
            select(func.count(Column.id)).where(Column.project_id == project_id)
        )
    ).scalar_one()
    if count <= 1:
        raise HTTPException(status_code=400, detail="Impossible de supprimer la dernière colonne")
    await db.delete(col)
    await db.commit()


async def reorder_columns(
    db: AsyncSession, project_id: uuid.UUID, ids: list[uuid.UUID]
) -> list[Column]:
    cols = (
        await db.execute(
            select(Column).where(Column.project_id == project_id)
        )
    ).scalars().all()
    col_map = {c.id: c for c in cols}
    for pos, col_id in enumerate(ids):
        if col_id in col_map:
            col_map[col_id].position = pos
    await db.commit()
    result = (
        await db.execute(
            select(Column).where(Column.project_id == project_id).order_by(Column.position)
        )
    ).scalars().all()
    return list(result)


# ─── Dashboard ────────────────────────────────────────────────────────────────

async def get_dashboard_stats(db: AsyncSession, user_id: uuid.UUID) -> dict:
    from app.features.tasks.models import Task as TaskModel
    from app.features.sprints.models import Sprint, SprintStatus

    projects_count = (
        await db.execute(
            select(func.count(Project.id))
            .join(ProjectMember, ProjectMember.project_id == Project.id)
            .where(ProjectMember.user_id == user_id)
        )
    ).scalar_one()

    tasks_in_progress = (
        await db.execute(
            select(func.count(TaskModel.id))
            .join(Column, Column.id == TaskModel.column_id)
            .where(
                TaskModel.assignee_id == user_id,
                Column.is_done_column.is_(False),
            )
        )
    ).scalar_one()

    active_sprints = (
        await db.execute(
            select(func.count(Sprint.id))
            .join(ProjectMember, ProjectMember.project_id == Sprint.project_id)
            .where(
                ProjectMember.user_id == user_id,
                Sprint.status == SprintStatus.active,
            )
        )
    ).scalar_one()

    my_tasks_count = (
        await db.execute(
            select(func.count(TaskModel.id))
            .where(TaskModel.assignee_id == user_id)
        )
    ).scalar_one()

    from datetime import date, timedelta
    today = date.today()
    week_ago = today - timedelta(days=7)
    week_ahead = today + timedelta(days=7)

    # Projects the user belongs to (with task counts)
    user_projects_result = await db.execute(
        select(Project)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(ProjectMember.user_id == user_id)
        .order_by(Project.created_at.desc())
        .limit(4)
    )
    user_projects = user_projects_result.scalars().all()

    from app.features.tasks.models import Task as TaskModel

    recent_projects = []
    for p in user_projects:
        task_count = (await db.execute(
            select(func.count(TaskModel.id)).where(TaskModel.project_id == p.id)
        )).scalar_one()
        recent_projects.append({
            "id": str(p.id),
            "name": p.name,
            "key": p.key,
            "color": p.color,
            "member_count": (await db.execute(
                select(func.count(ProjectMember.id)).where(ProjectMember.project_id == p.id)
            )).scalar_one(),
            "task_count": task_count,
        })

    # Overdue tasks assigned to me
    overdue_tasks = (
        await db.execute(
            select(func.count(TaskModel.id))
            .join(Column, Column.id == TaskModel.column_id)
            .where(
                TaskModel.assignee_id == user_id,
                Column.is_done_column.is_(False),
                TaskModel.due_date < today,
            )
        )
    ).scalar_one()

    # Completed this week
    completed_this_week = (
        await db.execute(
            select(func.count(TaskModel.id))
            .join(Column, Column.id == TaskModel.column_id)
            .where(
                TaskModel.assignee_id == user_id,
                Column.is_done_column.is_(True),
                TaskModel.updated_at >= week_ago,
            )
        )
    ).scalar_one()

    # Upcoming tasks (due in next 7 days)
    upcoming_rows = (await db.execute(
        select(TaskModel, Project)
        .join(Column, Column.id == TaskModel.column_id)
        .join(Project, Project.id == TaskModel.project_id)
        .where(
            TaskModel.assignee_id == user_id,
            Column.is_done_column.is_(False),
            TaskModel.due_date >= today,
            TaskModel.due_date <= week_ahead,
        )
        .order_by(TaskModel.due_date)
        .limit(5)
    )).all()

    upcoming_tasks = [
        {
            "id": str(t.id),
            "title": t.title,
            "priority": t.priority.value,
            "due_date": t.due_date.isoformat(),
            "project_name": p.name,
            "project_color": p.color,
        }
        for t, p in upcoming_rows
    ]

    return {
        "projects_count": projects_count,
        "tasks_in_progress": tasks_in_progress,
        "active_sprints": active_sprints,
        "my_tasks_count": my_tasks_count,
        "overdue_tasks": overdue_tasks,
        "completed_this_week": completed_this_week,
        "recent_projects": recent_projects,
        "upcoming_tasks": upcoming_tasks,
    }


async def get_project_analytics(
    db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID
) -> dict:
    from datetime import date
    from app.features.tasks.models import Task as TaskModel
    from app.features.sprints.models import Sprint, SprintTask, SprintStatus

    project = await get_project(db, project_id, user_id)

    # All tasks
    all_tasks = (await db.execute(
        select(TaskModel).where(TaskModel.project_id == project_id)
    )).scalars().all()

    today = date.today()
    total = len(all_tasks)
    overdue = sum(1 for t in all_tasks if t.due_date and t.due_date < today)

    # By column
    by_column = []
    for col in sorted(project.columns, key=lambda c: c.position):
        count = sum(1 for t in all_tasks if t.column_id == col.id)
        done = sum(1 for t in all_tasks if t.column_id == col.id and col.is_done_column)
        by_column.append({
            "column_id": str(col.id),
            "column_name": col.name,
            "color": col.color,
            "task_count": count,
            "is_done_column": col.is_done_column,
        })

    done_tasks = sum(c["task_count"] for c in by_column if c["is_done_column"])

    # By priority
    priority_counts: dict[str, int] = {}
    for t in all_tasks:
        priority_counts[t.priority.value] = priority_counts.get(t.priority.value, 0) + 1
    by_priority = [{"priority": p, "count": c} for p, c in priority_counts.items()]

    # Member workload
    members = (await db.execute(
        select(ProjectMember).where(ProjectMember.project_id == project_id)
    )).scalars().all()

    from app.features.users.models import User
    workload = []
    done_column_ids = {col.id for col in project.columns if col.is_done_column}
    for member in members:
        user_result = await db.execute(select(User).where(User.id == member.user_id))
        user = user_result.scalar_one_or_none()
        if not user:
            continue
        assigned = [t for t in all_tasks if t.assignee_id == member.user_id]
        done = sum(1 for t in assigned if t.column_id in done_column_ids)
        workload.append({
            "user_id": str(user.id),
            "full_name": user.full_name,
            "avatar_path": user.avatar_path,
            "task_count": len(assigned),
            "done_count": done,
        })

    # Sprint stats
    sprints = (await db.execute(
        select(Sprint).where(Sprint.project_id == project_id).options(selectinload(Sprint.sprint_tasks))
    )).scalars().all()

    sprint_stats = []
    for sprint in sprints:
        sprint_task_ids = {st.task_id for st in sprint.sprint_tasks}
        sprint_tasks = [t for t in all_tasks if t.id in sprint_task_ids]
        done_s = sum(1 for t in sprint_tasks if t.column_id in done_column_ids)
        sprint_stats.append({
            "sprint_id": str(sprint.id),
            "sprint_name": sprint.name,
            "status": sprint.status.value,
            "total_tasks": len(sprint_tasks),
            "done_tasks": done_s,
        })

    return {
        "total_tasks": total,
        "overdue_tasks": overdue,
        "done_tasks": done_tasks,
        "by_column": by_column,
        "by_priority": by_priority,
        "member_workload": workload,
        "sprint_stats": sprint_stats,
    }
