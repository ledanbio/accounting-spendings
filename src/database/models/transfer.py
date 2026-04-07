import datetime
from decimal import Decimal

from sqlalchemy import String, Numeric, Date, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base


class Transfer(Base):
    __tablename__ = "transfers"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    from_wallet_id: Mapped[int] = mapped_column(ForeignKey("wallets.id", ondelete="CASCADE"))
    to_wallet_id: Mapped[int] = mapped_column(ForeignKey("wallets.id", ondelete="CASCADE"))
    from_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    from_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    to_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    to_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    # effective ratio: to_amount / from_amount
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(16, 8), nullable=False)
    description: Mapped[str | None] = mapped_column(String(256))
    transfer_date: Mapped[datetime.date] = mapped_column(Date, nullable=False, server_default=func.current_date())
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())

    from_wallet: Mapped["Wallet"] = relationship(foreign_keys=[from_wallet_id])
    to_wallet: Mapped["Wallet"] = relationship(foreign_keys=[to_wallet_id])
