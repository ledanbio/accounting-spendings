import datetime
from decimal import Decimal

from sqlalchemy import select, func, update, distinct
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.database.models.transaction import Transaction
from src.database.models.wallet import Wallet


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

        if wallet_id is not None:
            delta = amount if type_ == "income" else -amount
            await self.session.execute(
                update(Wallet)
                .where(Wallet.id == wallet_id)
                .values(balance=Wallet.balance + delta)
            )

        await self.session.commit()
        await self.session.refresh(txn)
        return txn

    async def get_history(
        self, user_id: int, limit: int = 10, offset: int = 0
    ) -> list[Transaction]:
        stmt = (
            select(Transaction)
            .options(joinedload(Transaction.category), joinedload(Transaction.wallet))
            .where(Transaction.user_id == user_id)
            .order_by(Transaction.transaction_date.desc(), Transaction.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_available_months(self, user_id: int, limit: int = 24) -> list[str]:
        """Return months with transactions as 'YYYY-MM' (newest first)."""
        month_str = func.to_char(Transaction.transaction_date, "YYYY-MM")
        stmt = (
            select(distinct(month_str))
            .where(Transaction.user_id == user_id)
            .order_by(distinct(month_str).desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [row[0] for row in result.all() if row[0]]

    async def get_month_history(
        self,
        user_id: int,
        month: str,
        limit: int = 10,
        offset: int = 0,
    ) -> list[Transaction]:
        """History for a month. month format: 'YYYY-MM'."""
        start = datetime.date.fromisoformat(f"{month}-01")
        if start.month == 12:
            end = datetime.date(start.year + 1, 1, 1)
        else:
            end = datetime.date(start.year, start.month + 1, 1)

        stmt = (
            select(Transaction)
            .options(joinedload(Transaction.category), joinedload(Transaction.wallet))
            .where(
                Transaction.user_id == user_id,
                Transaction.transaction_date >= start,
                Transaction.transaction_date < end,
            )
            .order_by(Transaction.transaction_date.desc(), Transaction.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_month(self, user_id: int, month: str) -> int:
        start = datetime.date.fromisoformat(f"{month}-01")
        if start.month == 12:
            end = datetime.date(start.year + 1, 1, 1)
        else:
            end = datetime.date(start.year, start.month + 1, 1)

        stmt = select(func.count(Transaction.id)).where(
            Transaction.user_id == user_id,
            Transaction.transaction_date >= start,
            Transaction.transaction_date < end,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_history_by_wallet(
        self, wallet_id: int, limit: int = 10, offset: int = 0
    ) -> list[Transaction]:
        stmt = (
            select(Transaction)
            .options(joinedload(Transaction.category), joinedload(Transaction.wallet))
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
