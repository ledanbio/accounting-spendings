from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.wallet import Wallet
from src.database.models.transaction import Transaction


class WalletService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_wallets(self, user_id: int, include_archived: bool = False) -> list[Wallet]:
        """Get all wallets for a user."""
        stmt = select(Wallet).where(Wallet.user_id == user_id)
        if not include_archived:
            stmt = stmt.where(Wallet.is_archived == False)
        stmt = stmt.order_by(Wallet.created_at)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        user_id: int,
        name: str,
        currency: str,
        emoji: str | None = None,
    ) -> Wallet:
        """Create a new wallet."""
        wallet = Wallet(
            user_id=user_id,
            name=name,
            currency=currency,
            emoji=emoji,
            is_archived=False,
        )
        self.session.add(wallet)
        await self.session.commit()
        await self.session.refresh(wallet)
        return wallet

    async def get_by_id(self, wallet_id: int) -> Wallet | None:
        """Get wallet by ID."""
        stmt = select(Wallet).where(Wallet.id == wallet_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def archive(self, wallet_id: int) -> Wallet | None:
        """Archive a wallet."""
        wallet = await self.get_by_id(wallet_id)
        if wallet:
            wallet.is_archived = True
            await self.session.commit()
            await self.session.refresh(wallet)
        return wallet

    async def get_balance(self, wallet_id: int) -> Decimal:
        """Get balance for a single wallet (income - expense)."""
        stmt = (
            select(
                Transaction.type,
                func.sum(Transaction.amount),
            )
            .where(Transaction.wallet_id == wallet_id)
            .group_by(Transaction.type)
        )
        result = await self.session.execute(stmt)

        balance = Decimal("0")
        for type_, total in result.all():
            if type_ == "income":
                balance += total
            else:
                balance -= total

        return balance

    async def get_statistics(self, wallet_id: int) -> dict[str, Decimal]:
        """Get income and expense totals for a wallet separately."""
        stmt = (
            select(
                Transaction.type,
                func.sum(Transaction.amount),
            )
            .where(Transaction.wallet_id == wallet_id)
            .group_by(Transaction.type)
        )
        result = await self.session.execute(stmt)

        stats = {"income": Decimal("0"), "expense": Decimal("0")}
        for type_, total in result.all():
            if total:
                stats[type_] = total

        return stats
