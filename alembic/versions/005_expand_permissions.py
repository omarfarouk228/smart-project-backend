"""expand permissions: tasks, sprints, project settings

Revision ID: 005
Revises: 004
Create Date: 2026-06-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None

_NEW_PERMISSIONS = [
    # Projets (compléments)
    ("projects.manage_members", "Gérer les membres du projet",    "projects"),
    ("projects.manage_columns", "Gérer les colonnes du projet",   "projects"),
    # Tâches
    ("tasks.view",    "Voir les tâches",          "tasks"),
    ("tasks.create",  "Créer des tâches",         "tasks"),
    ("tasks.update",  "Modifier des tâches",      "tasks"),
    ("tasks.delete",  "Supprimer des tâches",     "tasks"),
    ("tasks.comment", "Commenter les tâches",     "tasks"),
    # Sprints
    ("sprints.view",   "Voir les sprints",                 "sprints"),
    ("sprints.create", "Créer des sprints",                "sprints"),
    ("sprints.update", "Modifier des sprints",             "sprints"),
    ("sprints.delete", "Supprimer des sprints",            "sprints"),
    ("sprints.manage", "Démarrer / terminer des sprints",  "sprints"),
]


def upgrade() -> None:
    conn = op.get_bind()

    # Fetch the Administrateur role id
    admin_role = conn.execute(
        sa.text("SELECT id FROM roles WHERE name = 'Administrateur' LIMIT 1")
    ).fetchone()
    admin_role_id = admin_role[0] if admin_role else None

    for codename, name, category in _NEW_PERMISSIONS:
        # Skip if already exists (idempotent)
        existing = conn.execute(
            sa.text("SELECT id FROM permissions WHERE codename = :c"),
            {"c": codename},
        ).fetchone()
        if existing:
            perm_id = existing[0]
        else:
            perm_id = uuid.uuid4()
            conn.execute(
                sa.text(
                    "INSERT INTO permissions (id, codename, name, description, category) "
                    "VALUES (:id, :c, :n, NULL, :cat)"
                ),
                {"id": perm_id, "c": codename, "n": name, "cat": category},
            )

        # Assign to Administrateur role if not already linked
        if admin_role_id:
            linked = conn.execute(
                sa.text(
                    "SELECT 1 FROM role_permissions "
                    "WHERE role_id = :r AND permission_id = :p"
                ),
                {"r": admin_role_id, "p": perm_id},
            ).fetchone()
            if not linked:
                conn.execute(
                    sa.text(
                        "INSERT INTO role_permissions (role_id, permission_id) "
                        "VALUES (:r, :p)"
                    ),
                    {"r": admin_role_id, "p": perm_id},
                )


def downgrade() -> None:
    conn = op.get_bind()
    codenames = [c for c, _, _ in _NEW_PERMISSIONS]
    for codename in codenames:
        conn.execute(
            sa.text(
                "DELETE FROM role_permissions WHERE permission_id = "
                "(SELECT id FROM permissions WHERE codename = :c)"
            ),
            {"c": codename},
        )
        conn.execute(
            sa.text("DELETE FROM permissions WHERE codename = :c"),
            {"c": codename},
        )
