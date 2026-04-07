"""Squashed: delete default categories, backfill wallet_id, add wallet balance

Revision ID: 003
Revises: 002
Create Date: 2026-04-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) Allow users to "delete" default categories (hide per user)
    op.create_table(
        "deleted_categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_deleted_categories_user_id", "deleted_categories", ["user_id"])
    op.create_index("ix_deleted_categories_category_id", "deleted_categories", ["category_id"])
    op.create_unique_constraint(
        "uq_deleted_categories_user_category",
        "deleted_categories",
        ["user_id", "category_id"],
    )

    # 2) Backfill wallet_id for existing transactions
    # 2.1 Prefer wallet with same currency
    op.execute(
        """
        UPDATE transactions
        SET wallet_id = (
            SELECT w.id
            FROM wallets w
            WHERE w.user_id = transactions.user_id
              AND w.currency = transactions.currency
              AND w.is_archived = false
            ORDER BY w.created_at ASC, w.id ASC
            LIMIT 1
        )
        WHERE transactions.wallet_id IS NULL
        """
    )

    # 2.2 Fallback: any wallet of the user
    op.execute(
        """
        UPDATE transactions
        SET wallet_id = (
            SELECT w.id
            FROM wallets w
            WHERE w.user_id = transactions.user_id
              AND w.is_archived = false
            ORDER BY w.created_at ASC, w.id ASC
            LIMIT 1
        )
        WHERE transactions.wallet_id IS NULL
        """
    )

    # 3) Add denormalized balance to wallets and backfill
    op.add_column(
        "wallets",
        sa.Column("balance", sa.Numeric(14, 2), nullable=False, server_default="0"),
    )

    op.execute(
        """
        WITH agg AS (
            SELECT
                wallet_id,
                SUM(
                    CASE
                        WHEN type = 'income' THEN amount
                        WHEN type = 'expense' THEN -amount
                        ELSE 0
                    END
                ) AS balance
            FROM transactions
            WHERE wallet_id IS NOT NULL
            GROUP BY wallet_id
        )
        UPDATE wallets w
        SET balance = COALESCE(agg.balance, 0)
        FROM agg
        WHERE w.id = agg.wallet_id
        """
    )


def downgrade() -> None:
    op.drop_column("wallets", "balance")

    op.drop_constraint("uq_deleted_categories_user_category", "deleted_categories", type_="unique")
    op.drop_index("ix_deleted_categories_category_id", table_name="deleted_categories")
    op.drop_index("ix_deleted_categories_user_id", table_name="deleted_categories")
    op.drop_table("deleted_categories")

