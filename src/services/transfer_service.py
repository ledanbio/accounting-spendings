import datetime
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.database.models.transfer import Transfer
from src.database.models.wallet import Wallet
from src.services.exchange_rate_service import ExchangeRateService


class TransferService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self._fx = ExchangeRateService(session)

    async def create(
        self,
        user_id: int,
        from_wallet_id: int,
        to_wallet_id: int,
        from_amount: Decimal,
        description: str | None = None,
        transfer_date: datetime.date | None = None,
    ) -> Transfer:
        from_wallet = await self.session.get(Wallet, from_wallet_id)
        to_wallet = await self.session.get(Wallet, to_wallet_id)
        if from_wallet is None or to_wallet is None:
            raise ValueError("Wallet not found")

        today = transfer_date or datetime.date.today()
        to_amount, exchange_rate = await self._fx.convert(
            from_amount, from_wallet.currency, to_wallet.currency, today
        )

        transfer = Transfer(
            user_id=user_id,
            from_wallet_id=from_wallet_id,
            to_wallet_id=to_wallet_id,
            from_amount=from_amount,
            from_currency=from_wallet.currency,
            to_amount=to_amount,
            to_currency=to_wallet.currency,
            exchange_rate=exchange_rate,
            description=description,
            transfer_date=today,
        )
        self.session.add(transfer)

        # Atomically update both wallet balances
        await self.session.execute(
            update(Wallet).where(Wallet.id == from_wallet_id).values(balance=Wallet.balance - from_amount)
        )
        await self.session.execute(
            update(Wallet).where(Wallet.id == to_wallet_id).values(balance=Wallet.balance + to_amount)
        )

        await self.session.commit()
        await self.session.refresh(transfer)
        return transfer

    async def preview(
        self,
        from_wallet_id: int,
        to_wallet_id: int,
        from_amount: Decimal,
    ) -> tuple[Decimal, Decimal]:
        """Return (to_amount, effective_rate) without persisting anything."""
        from_wallet = await self.session.get(Wallet, from_wallet_id)
        to_wallet = await self.session.get(Wallet, to_wallet_id)
        if from_wallet is None or to_wallet is None:
            raise ValueError("Wallet not found")
        return await self._fx.convert(from_amount, from_wallet.currency, to_wallet.currency)

    async def get_recent(self, user_id: int, limit: int = 20, offset: int = 0) -> list[Transfer]:
        stmt = (
            select(Transfer)
            .options(
                joinedload(Transfer.from_wallet),
                joinedload(Transfer.to_wallet),
            )
            .where(Transfer.user_id == user_id)
            .order_by(Transfer.transfer_date.desc(), Transfer.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    async def count(self, user_id: int) -> int:
        from sqlalchemy import func
        stmt = select(func.count(Transfer.id)).where(Transfer.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one()
