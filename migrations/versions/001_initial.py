"""Initial schema and default categories

Revision ID: 001
Revises:
Create Date: 2026-03-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), unique=True, index=True, nullable=False),
        sa.Column("username", sa.String(64), nullable=True),
        sa.Column("first_name", sa.String(128), nullable=False),
        sa.Column("default_currency", sa.String(3), nullable=False, server_default="RUB"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("type", sa.String(7), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("type", sa.String(7), nullable=False),
        sa.Column("description", sa.String(256), nullable=True),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    categories_table = sa.table(
        "categories",
        sa.column("name", sa.String),
        sa.column("type", sa.String),
        sa.column("is_default", sa.Boolean),
    )

    default_categories = [
        {"name": "Еда", "type": "expense", "is_default": True},
        {"name": "Транспорт", "type": "expense", "is_default": True},
        {"name": "Жильё", "type": "expense", "is_default": True},
        {"name": "Развлечения", "type": "expense", "is_default": True},
        {"name": "Здоровье", "type": "expense", "is_default": True},
        {"name": "Одежда", "type": "expense", "is_default": True},
        {"name": "Образование", "type": "expense", "is_default": True},
        {"name": "Другое", "type": "expense", "is_default": True},
        {"name": "Зарплата", "type": "income", "is_default": True},
        {"name": "Фриланс", "type": "income", "is_default": True},
        {"name": "Подарок", "type": "income", "is_default": True},
        {"name": "Инвестиции", "type": "income", "is_default": True},
        {"name": "Другое", "type": "income", "is_default": True},
    ]

    op.bulk_insert(categories_table, default_categories)


def downgrade() -> None:
    op.drop_table("transactions")
    op.drop_table("categories")
    op.drop_table("users")
