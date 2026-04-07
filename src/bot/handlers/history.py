from decimal import Decimal

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.user import User
from src.services.exchange_rate_service import ExchangeRateService
from src.services.user_service import UserService
from src.services.transaction_service import TransactionService
from src.services.wallet_service import WalletService
from src.bot.keyboards.inline import wallets_keyboard

router = Router()

PAGE_SIZE = 10


async def _totals_in_default_currency(
    session: AsyncSession,
    user: User,
    transactions: list,
) -> tuple[Decimal, Decimal, set[str]]:
    """Sum income/expense for *transactions* converted to user.default_currency via BYN."""
    fx = ExchangeRateService(session)
    try:
        await fx.ensure_today_rates()
    except Exception:
        pass

    total_income = Decimal("0")
    total_expense = Decimal("0")
    skipped: set[str] = set()

    for txn in transactions:
        try:
            converted, _ = await fx.convert(txn.amount, txn.currency, user.default_currency)
        except Exception:
            skipped.add(txn.currency)
            continue
        if txn.type == "income":
            total_income += converted
        else:
            total_expense += converted

    return total_income, total_expense, skipped


def _format_history_totals(
    total_income: Decimal,
    total_expense: Decimal,
    default_currency: str,
    skipped: set[str],
) -> str:
    line = (
        f"\n<b>Итого (в {default_currency}):</b> "
        f"Доход: +{total_income} | Расход: -{total_expense}"
    )
    if skipped:
        line += f"\n<i>Не удалось конвертировать: {', '.join(sorted(skipped))}</i>"
    return line


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


@router.callback_query(F.data == "hist_months")
async def on_history_months(callback: CallbackQuery, session: AsyncSession) -> None:
    user_svc = UserService(session)
    user = await user_svc.get_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.message.edit_text("Сначала введите /start")
        await callback.answer()
        return

    txn_svc = TransactionService(session)
    months = await txn_svc.get_available_months(user.id, limit=24)

    if not months:
        await callback.message.edit_text("У вас пока нет транзакций.")
        await callback.answer()
        return

    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    for m in months:
        builder.button(text=m, callback_data=f"histm:{m}:0")
    builder.adjust(3)
    builder.row(InlineKeyboardButton(text="↩️ Назад", callback_data="hist_back"))

    await callback.message.edit_text(
        "<b>📅 Выберите месяц</b>",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data == "hist_back")
async def on_history_back(callback: CallbackQuery, session: AsyncSession) -> None:
    await _send_history(callback.message, session, callback.from_user.id, offset=0, edit=True)
    await callback.answer()


@router.callback_query(F.data.startswith("histm:"))
async def on_history_month_page(callback: CallbackQuery, session: AsyncSession) -> None:
    # histm:YYYY-MM:offset
    _, month, offset_s = callback.data.split(":")
    offset = int(offset_s)
    await _send_month_history(
        callback.message,
        session,
        callback.from_user.id,
        month=month,
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

    for txn in transactions:
        icon = "📈" if txn.type == "income" else "📉"
        cat_name = txn.category.name if txn.category else "—"
        desc = f" — {txn.description}" if txn.description else ""
        wallet_name = f" [{txn.wallet.name}]" if txn.wallet else ""
        lines.append(
            f"{icon} {txn.transaction_date} | {cat_name} | "
            f"{txn.amount} {txn.currency}{desc}{wallet_name}"
        )

    ti, te, skipped = await _totals_in_default_currency(session, user, transactions)
    lines.append(_format_history_totals(ti, te, user.default_currency, skipped))

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

    builder.row(InlineKeyboardButton(text="📅 По месяцам", callback_data="hist_months"))
    builder.row(InlineKeyboardButton(text="💼 По кошелькам", callback_data="wallet_stats"))

    markup = builder.as_markup()

    if edit:
        await target.edit_text(text, reply_markup=markup)
    else:
        await target.answer(text, reply_markup=markup)


async def _send_month_history(
    target: Message,
    session: AsyncSession,
    telegram_id: int,
    month: str,
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
    total = await txn_svc.count_month(user.id, month)

    if total == 0:
        text = f"За <b>{month}</b> транзакций нет."
        if edit:
            await target.edit_text(text)
        else:
            await target.answer(text)
        return

    transactions = await txn_svc.get_month_history(user.id, month, limit=PAGE_SIZE, offset=offset)

    lines = [f"<b>История за {month}</b> ({offset + 1}–{offset + len(transactions)} из {total}):\n"]

    for txn in transactions:
        icon = "📈" if txn.type == "income" else "📉"
        cat_name = txn.category.name if txn.category else "—"
        desc = f" — {txn.description}" if txn.description else ""
        wallet_name = f" [{txn.wallet.name}]" if txn.wallet else ""
        lines.append(
            f"{icon} {txn.transaction_date} | {cat_name} | "
            f"{txn.amount} {txn.currency}{desc}{wallet_name}"
        )

    ti, te, skipped = await _totals_in_default_currency(session, user, transactions)
    lines.append(_format_history_totals(ti, te, user.default_currency, skipped))
    text = "\n".join(lines)

    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    nav = []
    if offset > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"histm:{month}:{offset - PAGE_SIZE}"))
    if offset + PAGE_SIZE < total:
        nav.append(InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"histm:{month}:{offset + PAGE_SIZE}"))
    if nav:
        builder.row(*nav)

    builder.row(InlineKeyboardButton(text="📅 Выбрать месяц", callback_data="hist_months"))
    builder.row(InlineKeyboardButton(text="↩️ К общей истории", callback_data="hist_back"))

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
    user_svc = UserService(session)
    user = await user_svc.get_by_id(wallet.user_id)
    if not user:
        text = "Пользователь не найден."
        if edit:
            await target.edit_text(text)
        else:
            await target.answer(text)
        return

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

    for txn in transactions:
        icon = "📈" if txn.type == "income" else "📉"
        cat_name = txn.category.name if txn.category else "—"
        desc = f" — {txn.description}" if txn.description else ""
        lines.append(
            f"{icon} {txn.transaction_date} | {cat_name} | {txn.amount} {txn.currency}{desc}"
        )

    ti, te, skipped = await _totals_in_default_currency(session, user, transactions)
    lines.append(_format_history_totals(ti, te, user.default_currency, skipped))

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
