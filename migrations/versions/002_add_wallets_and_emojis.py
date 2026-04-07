"""Add wallets and emoji support

Revision ID: 002
Revises: 001
Create Date: 2026-03-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add emoji_enabled to users table
    op.add_column("users", sa.Column("emoji_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")))

    # Add emoji to categories table
    op.add_column("categories", sa.Column("emoji", sa.String(1), nullable=True))

    # Create wallets table
    op.create_table(
        "wallets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("emoji", sa.String(1), nullable=True),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    # Add wallet_id to transactions table (nullable for backward compatibility)
    op.add_column("transactions", sa.Column("wallet_id", sa.Integer(), sa.ForeignKey("wallets.id", ondelete="CASCADE"), nullable=True, index=True))


def downgrade() -> None:
    op.drop_column("transactions", "wallet_id")
    op.drop_table("wallets")
    op.drop_column("categories", "emoji")
    op.drop_column("users", "emoji_enabled")
