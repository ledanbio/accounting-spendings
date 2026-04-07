from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.user_service import UserService
from src.services.transaction_service import TransactionService
from src.services.wallet_service import WalletService

router = Router()


@router.message(Command("balance"))
async def cmd_balance(message: Message, session: AsyncSession) -> None:
    user_svc = UserService(session)
    user = await user_svc.get_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("Сначала введите /start")
        return

    wallet_svc = WalletService(session)
    wallets = await wallet_svc.get_wallets(user.id)

    if not wallets:
        await message.answer("У вас нет кошельков.")
        return

    lines = ["<b>💼 Ваш баланс по кошелькам:</b>\n"]

    total_balance = 0

    for wallet in wallets:
        total_balance += wallet.balance
        emoji = wallet.emoji or "💼"
        sign = "+" if wallet.balance >= 0 else ""
        lines.append(
            f"  {emoji} <b>{wallet.name}</b> ({wallet.currency}): {sign}{wallet.balance}"
        )

    lines.append("\n" + "─" * 30)
    sign = "+" if total_balance >= 0 else ""
    lines.append(f"  <b>Итого:</b> {sign}{total_balance}")

    await message.answer("\n".join(lines))
