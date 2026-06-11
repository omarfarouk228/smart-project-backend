"""add audit_logs table

Revision ID: 002
Revises: 001
Create Date: 2026-06-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    audit_action_enum = postgresql.ENUM(
        "task_created", "task_updated", "task_deleted", "task_moved",
        "sprint_created", "sprint_started", "sprint_completed", "sprint_deleted",
        "member_added", "member_removed", "project_updated",
        "column_created", "column_deleted", "comment_added",
        name="auditaction", create_type=True,
    )
    audit_action_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", postgresql.ENUM(
            "task_created", "task_updated", "task_deleted", "task_moved",
            "sprint_created", "sprint_started", "sprint_completed", "sprint_deleted",
            "member_added", "member_removed", "project_updated",
            "column_created", "column_deleted", "comment_added",
            name="auditaction", create_type=False,
        ), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.String(100), nullable=True),
        sa.Column("entity_name", sa.String(500), nullable=True),
        sa.Column("details", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_logs_project_id", "audit_logs", ["project_id"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.execute("DROP TYPE IF EXISTS auditaction")
