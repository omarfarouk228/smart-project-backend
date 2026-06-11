"""add unique constraint on refresh_tokens.token_hash

Revision ID: 004
Revises: 003
Create Date: 2026-06-11
"""
from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Remove duplicate rows first — keep the most recent one per hash
    op.execute("""
        DELETE FROM refresh_tokens
        WHERE id NOT IN (
            SELECT DISTINCT ON (token_hash) id
            FROM refresh_tokens
            ORDER BY token_hash, created_at DESC
        )
    """)
    op.create_unique_constraint("uq_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"])


def downgrade() -> None:
    op.drop_constraint("uq_refresh_tokens_token_hash", "refresh_tokens", type_="unique")
