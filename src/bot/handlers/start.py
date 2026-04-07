from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.user_service import UserService
from src.services.wallet_service import WalletService
from src.bot.keyboards.inline import settings_currency_keyboard
from src.bot.keyboards.reply import main_menu_keyboard

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession) -> None:
    user_svc = UserService(session)
    user = await user_svc.get_or_create(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
    )

    wallet_svc = WalletService(session)
    wallets = await wallet_svc.get_wallets(user.id)

    if not wallets:
        # First time user - show onboarding
        await message.answer(
            f"👋 Привет, <b>{user.first_name}</b>!\n\n"
            "Я помогу вести учёт расходов и доходов.\n"
            "Давайте начнём с создания первого кошелька!",
        )

        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="💼 Создать кошелек", callback_data="onboard_wallet"))
        builder.row(InlineKeyboardButton(text="Пропустить", callback_data="onboard_skip"))

        await message.answer(
            "Хотите создать кошелек прямо сейчас?",
            reply_markup=builder.as_markup(),
        )
    else:
        # Returning user
        await message.answer(
            f"Привет, <b>{user.first_name}</b>!\n\n"
            "Я помогу вести учёт расходов и доходов.\n"
            f"Валюта по умолчанию: <b>{user.default_currency}</b>\n\n"
            "Используй кнопки меню или /help для списка команд.",
            reply_markup=main_menu_keyboard(),
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


@router.callback_query(F.data == "onboard_wallet")
async def on_onboard_wallet(callback: CallbackQuery, session: AsyncSession) -> None:
    """Start wallet creation during onboarding."""
    from src.bot.states.wallet import AddWallet
    from aiogram.fsm.context import FSMContext

    # Get the state object from the context
    state = callback.bot.get('_state_storage')

    await callback.message.edit_text("Введите название кошелька (например, 'Основная карта'):")

    # Import FSM context and set state
    from aiogram.fsm.context import FSMContext

    # We'll use a workaround for now - just direct to wallet command
    await callback.message.answer(
        "Используйте команду /wallets для создания кошелька.\n"
        "Или просто добавьте первую транзакцию командой /add, "
        "система попросит создать кошелек автоматически.",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "onboard_skip")
async def on_onboard_skip(callback: CallbackQuery) -> None:
    """Skip wallet creation during onboarding."""
    await callback.message.edit_text(
        "Хорошо! Когда будете готовы создать кошелек, используйте команду /wallets"
    )
    await callback.message.answer(
        "Используй кнопки меню или /help для списка команд.",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "cancel")
async def on_cancel(callback: CallbackQuery) -> None:
    await callback.message.edit_text("Действие отменено.")
    await callback.answer()
