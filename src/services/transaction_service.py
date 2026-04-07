import datetime
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.database.models.transaction import Transaction


class TransactionService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        user_id: int,
        category_id: int,
        amount: Decimal,
        currency: str,
        type_: str,
        description: str | None = None,
        transaction_date: datetime.date | None = None,
        wallet_id: int | None = None,
    ) -> Transaction:
        txn = Transaction(
            user_id=user_id,
            category_id=category_id,
            amount=amount,
            currency=currency,
            type=type_,
            description=description,
            transaction_date=transaction_date or datetime.date.today(),
            wallet_id=wallet_id,
        )
        self.session.add(txn)
        await self.session.commit()
        await self.session.refresh(txn)
        return txn

    async def get_history(
        self, user_id: int, limit: int = 10, offset: int = 0
    ) -> list[Transaction]:
        stmt = (
            select(Transaction)
            .options(joinedload(Transaction.category))
            .where(Transaction.user_id == user_id)
            .order_by(Transaction.transaction_date.desc(), Transaction.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_history_by_wallet(
        self, wallet_id: int, limit: int = 10, offset: int = 0
    ) -> list[Transaction]:
        stmt = (
            select(Transaction)
            .options(joinedload(Transaction.category))
            .where(Transaction.wallet_id == wallet_id)
            .order_by(Transaction.transaction_date.desc(), Transaction.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count(self, user_id: int) -> int:
        stmt = select(func.count(Transaction.id)).where(Transaction.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def count_by_wallet(self, wallet_id: int) -> int:
        stmt = select(func.count(Transaction.id)).where(Transaction.wallet_id == wallet_id)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_balance(self, user_id: int) -> dict[str, Decimal]:
        """Returns {currency: balance} where balance = income - expense."""
        stmt = (
            select(
                Transaction.currency,
                Transaction.type,
                func.sum(Transaction.amount),
            )
            .where(Transaction.user_id == user_id)
            .group_by(Transaction.currency, Transaction.type)
        )
        result = await self.session.execute(stmt)

        balances: dict[str, Decimal] = {}
        for currency, type_, total in result.all():
            if currency not in balances:
                balances[currency] = Decimal("0")
            if type_ == "income":
                balances[currency] += total
            else:
                balances[currency] -= total

        return balances

    async def get_balance_by_wallet(self, wallet_id: int) -> Decimal:
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

    async def get_wallet_statistics(self, wallet_id: int) -> dict[str, Decimal]:
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

    async def get_total_balance(self, user_id: int) -> dict[str, Decimal]:
        """Get total balance across all wallets for a user."""
        stmt = (
            select(
                Transaction.wallet_id,
                func.sum(Transaction.amount).label("total"),
            )
            .where(Transaction.user_id == user_id)
            .group_by(Transaction.wallet_id)
        )
        result = await self.session.execute(stmt)
        return {wallet_id: total for wallet_id, total in result.all()}
