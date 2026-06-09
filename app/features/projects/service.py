import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from fastapi import HTTPException

from app.features.projects.models import Project, ProjectMember, Column
from app.features.projects.schemas import ProjectCreate, ProjectUpdate, AddMemberRequest

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
            base.order_by(Project.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return list(projects), total


async def get_project(db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id))
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
        .order_by(ProjectMember.joined_at)
    )
    return list(result.scalars().all())


async def add_member(
    db: AsyncSession, project_id: uuid.UUID, data: AddMemberRequest
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
        raise HTTPException(status_code=400, detail="Impossible de retirer le propriétaire")
    await db.delete(member)
    await db.commit()
