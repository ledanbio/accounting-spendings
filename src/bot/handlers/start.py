from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.user_service import UserService
from src.bot.keyboards.inline import settings_currency_keyboard

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession) -> None:
    svc = UserService(session)
    user = await svc.get_or_create(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
    )
    await message.answer(
        f"Привет, <b>{user.first_name}</b>!\n\n"
        "Я помогу вести учёт расходов и доходов.\n"
        f"Валюта по умолчанию: <b>{user.default_currency}</b>\n\n"
        "Используй /help чтобы увидеть список команд."
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "<b>Доступные команды:</b>\n\n"
        "/add — добавить доход или расход\n"
        "/balance — текущий баланс\n"
        "/history — история транзакций\n"
        "/categories — управление категориями\n"
        "/settings — настройки (валюта)\n"
        "/help — эта справка"
    )


@router.message(Command("settings"))
async def cmd_settings(message: Message) -> None:
    await message.answer(
        "Выберите валюту по умолчанию:",
        reply_markup=settings_currency_keyboard(),
    )


@router.callback_query(F.data.startswith("setcur:"))
async def on_set_currency(callback: CallbackQuery, session: AsyncSession) -> None:
    currency = callback.data.split(":")[1]
    svc = UserService(session)
    user = await svc.get_by_telegram_id(callback.from_user.id)
    if user:
        await svc.update_currency(user.id, currency)
        await callback.message.edit_text(
            f"Валюта по умолчанию изменена на <b>{currency}</b>"
        )
    await callback.answer()


@router.callback_query(F.data == "cancel")
async def on_cancel(callback: CallbackQuery) -> None:
    await callback.message.edit_text("Действие отменено.")
    await callback.answer()
