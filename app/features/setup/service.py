from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException

from app.core.security import hash_password
from app.core.state import app_state
from app.features.organization.models import Organization
from app.features.users.models import User
from app.features.roles.models import Role, Permission, RolePermission, UserRole
from app.features.setup.schemas import SetupPayload

_PERMISSIONS = [
    # Organisation
    {"codename": "organization.view",   "name": "Voir les paramètres",          "category": "organization"},
    {"codename": "organization.update", "name": "Modifier les paramètres",       "category": "organization"},
    # Utilisateurs
    {"codename": "users.view",   "name": "Voir les utilisateurs",    "category": "users"},
    {"codename": "users.create", "name": "Créer des utilisateurs",   "category": "users"},
    {"codename": "users.update", "name": "Modifier des utilisateurs","category": "users"},
    {"codename": "users.delete", "name": "Désactiver des utilisateurs", "category": "users"},
    # Rôles
    {"codename": "roles.view",   "name": "Voir les rôles",           "category": "roles"},
    {"codename": "roles.create", "name": "Créer des rôles",          "category": "roles"},
    {"codename": "roles.update", "name": "Modifier des rôles",       "category": "roles"},
    {"codename": "roles.delete", "name": "Supprimer des rôles",      "category": "roles"},
    # Projets
    {"codename": "projects.view",            "name": "Voir les projets",              "category": "projects"},
    {"codename": "projects.create",          "name": "Créer des projets",             "category": "projects"},
    {"codename": "projects.update",          "name": "Modifier les paramètres projet","category": "projects"},
    {"codename": "projects.delete",          "name": "Supprimer des projets",         "category": "projects"},
    {"codename": "projects.manage_members",  "name": "Gérer les membres du projet",   "category": "projects"},
    {"codename": "projects.manage_columns",  "name": "Gérer les colonnes du projet",  "category": "projects"},
    # Tâches
    {"codename": "tasks.view",    "name": "Voir les tâches",          "category": "tasks"},
    {"codename": "tasks.create",  "name": "Créer des tâches",         "category": "tasks"},
    {"codename": "tasks.update",  "name": "Modifier des tâches",      "category": "tasks"},
    {"codename": "tasks.delete",  "name": "Supprimer des tâches",     "category": "tasks"},
    {"codename": "tasks.comment", "name": "Commenter les tâches",     "category": "tasks"},
    # Sprints
    {"codename": "sprints.view",   "name": "Voir les sprints",                  "category": "sprints"},
    {"codename": "sprints.create", "name": "Créer des sprints",                 "category": "sprints"},
    {"codename": "sprints.update", "name": "Modifier des sprints",              "category": "sprints"},
    {"codename": "sprints.delete", "name": "Supprimer des sprints",             "category": "sprints"},
    {"codename": "sprints.manage", "name": "Démarrer / terminer des sprints",   "category": "sprints"},
    # Rapports
    {"codename": "reports.view", "name": "Voir les rapports", "category": "reports"},
]


async def is_setup_complete(db: AsyncSession) -> bool:
    result = await db.execute(select(Organization).limit(1))
    org = result.scalar_one_or_none()
    return bool(org and org.setup_completed)


async def run_setup(db: AsyncSession, payload: SetupPayload) -> None:
    existing = await db.execute(select(Organization).limit(1))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Setup déjà effectué")

    org = Organization(
        name=payload.organization.name,
        app_name=payload.organization.app_name,
        primary_color=payload.organization.primary_color,
        secondary_color=payload.organization.secondary_color,
        accent_color=payload.organization.accent_color,
        default_theme=payload.organization.default_theme,
    )
    if payload.smtp:
        org.smtp_host = payload.smtp.smtp_host
        org.smtp_port = payload.smtp.smtp_port
        org.smtp_user = payload.smtp.smtp_user
        org.smtp_password = payload.smtp.smtp_password
        org.smtp_from = payload.smtp.smtp_from
        org.smtp_ssl = payload.smtp.smtp_ssl
        org.smtp_configured = True
    db.add(org)

    existing_perms_result = await db.execute(select(Permission))
    existing_by_codename = {p.codename: p for p in existing_perms_result.scalars().all()}

    permissions = []
    for p in _PERMISSIONS:
        if p["codename"] in existing_by_codename:
            permissions.append(existing_by_codename[p["codename"]])
        else:
            perm = Permission(**p)
            db.add(perm)
            permissions.append(perm)

    admin_role = Role(
        name="Administrateur",
        description="Accès complet au système",
        is_system=True,
        color="#ef4444",
    )
    db.add(admin_role)
    await db.flush()

    for perm in permissions:
        db.add(RolePermission(role_id=admin_role.id, permission_id=perm.id))

    admin_user = User(
        email=payload.admin.email,
        hashed_password=hash_password(payload.admin.password),
        first_name=payload.admin.first_name,
        last_name=payload.admin.last_name,
        is_superadmin=True,
        must_change_password=False,
    )
    db.add(admin_user)
    await db.flush()

    db.add(UserRole(user_id=admin_user.id, role_id=admin_role.id))
    org.setup_completed = True
    await db.commit()

    app_state.setup_completed = True
