from decimal import Decimal

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.user_service import UserService
from src.services.wallet_service import WalletService
from src.services.exchange_rate_service import ExchangeRateService

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

    fx = ExchangeRateService(session)
    try:
        await fx.ensure_today_rates()
    except Exception:
        # If rate refresh fails, we'll still show per-wallet balances.
        pass

    total_in_default = Decimal("0")
    skipped_currencies: set[str] = set()

    for wallet in wallets:
        emoji = wallet.emoji or "💼"
        sign = "+" if wallet.balance >= 0 else ""
        lines.append(
            f"  {emoji} <b>{wallet.name}</b> ({wallet.currency}): {sign}{wallet.balance}"
        )
        try:
            converted, _ = await fx.convert(wallet.balance, wallet.currency, user.default_currency)
            total_in_default += converted
        except Exception:
            skipped_currencies.add(wallet.currency)

    lines.append("\n" + "─" * 30)
    sign = "+" if total_in_default >= 0 else ""
    lines.append(f"  <b>Итого:</b> {sign}{total_in_default} {user.default_currency}")
    if skipped_currencies:
        skipped = ", ".join(sorted(skipped_currencies))
        lines.append(f"\n<i>Не удалось конвертировать валюты: {skipped}</i>")

    await message.answer("\n".join(lines))
