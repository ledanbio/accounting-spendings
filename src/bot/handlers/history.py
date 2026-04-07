from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.user_service import UserService
from src.services.transaction_service import TransactionService
from src.services.wallet_service import WalletService
from src.bot.keyboards.inline import history_keyboard, wallets_keyboard, wallet_stats_filter_keyboard

router = Router()

PAGE_SIZE = 10


@router.message(Command("history"))
async def cmd_history(message: Message, session: AsyncSession) -> None:
    await _send_history(message, session, message.from_user.id, offset=0)


@router.callback_query(F.data.startswith("hist:"))
async def on_history_page(callback: CallbackQuery, session: AsyncSession) -> None:
    offset = int(callback.data.split(":")[1])
    await _send_history(
        callback.message,
        session,
        callback.from_user.id,
        offset=offset,
        edit=True,
    )
    await callback.answer()


@router.callback_query(F.data == "wallet_stats")
async def on_wallet_stats(callback: CallbackQuery, session: AsyncSession) -> None:
    """Show wallet statistics list."""
    user_svc = UserService(session)
    user = await user_svc.get_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.message.edit_text("Сначала введите /start")
        await callback.answer()
        return

    wallet_svc = WalletService(session)
    wallets = await wallet_svc.get_wallets(user.id)

    if not wallets:
        await callback.message.edit_text("У вас нет кошельков.")
        await callback.answer()
        return

    txn_svc = TransactionService(session)
    lines = ["<b>💼 Ваши кошельки:</b>\n"]
    for wallet in wallets:
        emoji = wallet.emoji or "💼"
        stats = await txn_svc.get_wallet_statistics(wallet.id)
        income = stats.get("income", 0)
        expense = stats.get("expense", 0)
        lines.append(f"{emoji} <b>{wallet.name}</b> ({wallet.currency}): +{income} / -{expense}")

    lines.append("\n<i>Нажмите на кошелек чтобы посмотреть детали</i>")
    text = "\n".join(lines)

    await callback.message.edit_text(text, reply_markup=wallets_keyboard(wallets))
    await callback.answer()


@router.callback_query(F.data.startswith("wallet:"))
async def on_wallet_selected(callback: CallbackQuery, session: AsyncSession) -> None:
    """Show history for a specific wallet."""
    wallet_id = int(callback.data.split(":")[1])
    await _send_wallet_history(callback.message, session, wallet_id, offset=0, edit=True)
    await callback.answer()


@router.callback_query(F.data.startswith("whist:"))
async def on_wallet_history_page(callback: CallbackQuery, session: AsyncSession) -> None:
    """Navigate wallet history pages."""
    parts = callback.data.split(":")
    wallet_id = int(parts[1])
    offset = int(parts[2])
    await _send_wallet_history(callback.message, session, wallet_id, offset=offset, edit=True)
    await callback.answer()


@router.callback_query(F.data == "wallet_back")
async def on_wallet_back(callback: CallbackQuery, session: AsyncSession) -> None:
    """Return to wallet list from wallet history."""
    user_svc = UserService(session)
    user = await user_svc.get_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.message.edit_text("Сначала введите /start")
        await callback.answer()
        return

    wallet_svc = WalletService(session)
    wallets = await wallet_svc.get_wallets(user.id)

    txn_svc = TransactionService(session)
    lines = ["<b>💼 Ваши кошельки:</b>\n"]
    for wallet in wallets:
        emoji = wallet.emoji or "💼"
        stats = await txn_svc.get_wallet_statistics(wallet.id)
        income = stats.get("income", 0)
        expense = stats.get("expense", 0)
        lines.append(f"{emoji} <b>{wallet.name}</b> ({wallet.currency}): +{income} / -{expense}")

    lines.append("\n<i>Нажмите на кошелек чтобы посмотреть детали</i>")
    text = "\n".join(lines)

    await callback.message.edit_text(text, reply_markup=wallets_keyboard(wallets))
    await callback.answer()


async def _send_history(
    target: Message,
    session: AsyncSession,
    telegram_id: int,
    offset: int,
    edit: bool = False,
) -> None:
    user_svc = UserService(session)
    user = await user_svc.get_by_telegram_id(telegram_id)
    if not user:
        text = "Сначала введите /start"
        if edit:
            await target.edit_text(text)
        else:
            await target.answer(text)
        return

    txn_svc = TransactionService(session)
    total = await txn_svc.count(user.id)

    if total == 0:
        text = "У вас пока нет транзакций."
        if edit:
            await target.edit_text(text)
        else:
            await target.answer(text)
        return

    transactions = await txn_svc.get_history(user.id, limit=PAGE_SIZE, offset=offset)

    lines = [f"<b>История транзакций</b> ({offset + 1}–{offset + len(transactions)} из {total}):\n"]

    total_income = 0
    total_expense = 0
    for txn in transactions:
        if txn.type == "income":
            total_income += txn.amount
        else:
            total_expense += txn.amount

        icon = "📈" if txn.type == "income" else "📉"
        cat_name = txn.category.name if txn.category else "—"
        desc = f" — {txn.description}" if txn.description else ""
        wallet_name = f" [{txn.wallet.name}]" if txn.wallet else ""
        lines.append(
            f"{icon} {txn.transaction_date} | {cat_name} | "
            f"{txn.amount} {txn.currency}{desc}{wallet_name}"
        )

    lines.append(f"\n<b>Итого:</b> Доход: +{total_income} | Расход: -{total_expense}")

    text = "\n".join(lines)

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    buttons = []
    if offset > 0:
        buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"hist:{offset - PAGE_SIZE}"))
    if offset + PAGE_SIZE < total:
        buttons.append(InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"hist:{offset + PAGE_SIZE}"))
    if buttons:
        builder.row(*buttons)

    builder.row(InlineKeyboardButton(text="💼 По кошелькам", callback_data="wallet_stats"))

    markup = builder.as_markup()

    if edit:
        await target.edit_text(text, reply_markup=markup)
    else:
        await target.answer(text, reply_markup=markup)


async def _send_wallet_history(
    target: Message,
    session: AsyncSession,
    wallet_id: int,
    offset: int,
    edit: bool = False,
) -> None:
    wallet_svc = WalletService(session)
    wallet = await wallet_svc.get_by_id(wallet_id)

    if not wallet:
        text = "Кошелек не найден."
        if edit:
            await target.edit_text(text)
        else:
            await target.answer(text)
        return

    txn_svc = TransactionService(session)
    total = await txn_svc.count_by_wallet(wallet_id)

    if total == 0:
        text = f"В кошельке <b>{wallet.name}</b> нет транзакций."
        if edit:
            await target.edit_text(text, reply_markup=_wallet_back_keyboard())
        else:
            await target.answer(text, reply_markup=_wallet_back_keyboard())
        return

    transactions = await txn_svc.get_history_by_wallet(wallet_id, limit=PAGE_SIZE, offset=offset)

    emoji = wallet.emoji or "💼"
    lines = [f"{emoji} <b>{wallet.name}</b> ({offset + 1}–{offset + len(transactions)} из {total}):\n"]

    total_income = 0
    total_expense = 0
    for txn in transactions:
        if txn.type == "income":
            total_income += txn.amount
        else:
            total_expense += txn.amount

        icon = "📈" if txn.type == "income" else "📉"
        cat_name = txn.category.name if txn.category else "—"
        desc = f" — {txn.description}" if txn.description else ""
        lines.append(
            f"{icon} {txn.transaction_date} | {cat_name} | {txn.amount} {txn.currency}{desc}"
        )

    lines.append(f"\n<b>Итого:</b> Доход: +{total_income} | Расход: -{total_expense}")

    text = "\n".join(lines)

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    buttons = []
    if offset > 0:
        buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"whist:{wallet_id}:{offset - PAGE_SIZE}"))
    if offset + PAGE_SIZE < total:
        buttons.append(InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"whist:{wallet_id}:{offset + PAGE_SIZE}"))
    if buttons:
        builder.row(*buttons)

    builder.row(InlineKeyboardButton(text="↩️ Вернуться", callback_data="wallet_back"))

    markup = builder.as_markup()

    if edit:
        await target.edit_text(text, reply_markup=markup)
    else:
        await target.answer(text, reply_markup=markup)


def _wallet_back_keyboard():
    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="↩️ Вернуться", callback_data="wallet_back"))
    return builder.as_markup()
