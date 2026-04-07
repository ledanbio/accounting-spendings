import datetime
from decimal import Decimal

from sqlalchemy import String, Numeric, Date, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base


class ExchangeRate(Base):
    __tablename__ = "exchange_rates"
    __table_args__ = (
        UniqueConstraint("currency", "date", name="uq_exchange_rates_currency_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    rate_byn: Mapped[Decimal] = mapped_column(Numeric(16, 6), nullable=False)
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False, index=True)
