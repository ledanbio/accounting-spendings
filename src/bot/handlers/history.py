from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.user_service import UserService
from src.services.transaction_service import TransactionService
from src.bot.keyboards.inline import history_keyboard

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
        icon = "🔴" if txn.type == "expense" else "🟢"
        cat_name = txn.category.name if txn.category else "—"
        desc = f" — {txn.description}" if txn.description else ""
        lines.append(
            f"{icon} {txn.transaction_date} | {cat_name} | "
            f"{txn.amount} {txn.currency}{desc}"
        )

    text = "\n".join(lines)
    markup = history_keyboard(offset, total, PAGE_SIZE)

    if edit:
        await target.edit_text(text, reply_markup=markup)
    else:
        await target.answer(text, reply_markup=markup)
