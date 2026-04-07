"""Add exchange_rates and transfers tables

Revision ID: 004
Revises: 003
Create Date: 2026-03-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "exchange_rates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("rate_byn", sa.Numeric(16, 6), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.UniqueConstraint("currency", "date", name="uq_exchange_rates_currency_date"),
    )
    op.create_index("ix_exchange_rates_date", "exchange_rates", ["date"])

    op.create_table(
        "transfers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("from_wallet_id", sa.Integer(), sa.ForeignKey("wallets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("to_wallet_id", sa.Integer(), sa.ForeignKey("wallets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("from_currency", sa.String(3), nullable=False),
        sa.Column("to_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("to_currency", sa.String(3), nullable=False),
        sa.Column("exchange_rate", sa.Numeric(16, 8), nullable=False),
        sa.Column("description", sa.String(256), nullable=True),
        sa.Column("transfer_date", sa.Date(), nullable=False, server_default=sa.func.current_date()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("transfers")
    op.drop_index("ix_exchange_rates_date", table_name="exchange_rates")
    op.drop_table("exchange_rates")
