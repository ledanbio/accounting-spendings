from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.user_service import UserService
from src.services.transaction_service import TransactionService

router = Router()


@router.message(Command("balance"))
async def cmd_balance(message: Message, session: AsyncSession) -> None:
    user_svc = UserService(session)
    user = await user_svc.get_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("Сначала введите /start")
        return

    txn_svc = TransactionService(session)
    balances = await txn_svc.get_balance(user.id)

    if not balances:
        await message.answer("У вас пока нет транзакций.")
        return

    lines = ["<b>Ваш баланс:</b>\n"]
    for currency, amount in sorted(balances.items()):
        sign = "+" if amount >= 0 else ""
        lines.append(f"  {currency}: <b>{sign}{amount}</b>")

    await message.answer("\n".join(lines))
