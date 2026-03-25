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
    ) -> Transaction:
        txn = Transaction(
            user_id=user_id,
            category_id=category_id,
            amount=amount,
            currency=currency,
            type=type_,
            description=description,
            transaction_date=transaction_date or datetime.date.today(),
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

    async def count(self, user_id: int) -> int:
        stmt = select(func.count(Transaction.id)).where(Transaction.user_id == user_id)
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
