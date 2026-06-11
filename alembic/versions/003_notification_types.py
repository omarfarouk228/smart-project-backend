"""extend notificationtype enum

Revision ID: 003
Revises: 002
Create Date: 2026-06-11
"""
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'project_added'")
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'task_updated'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values; downgrade is a no-op
    pass
