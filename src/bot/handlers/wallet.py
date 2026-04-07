from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.user_service import UserService
from src.services.wallet_service import WalletService
from src.bot.states.wallet import AddWallet
from src.bot.keyboards.reply import main_menu_keyboard

router = Router()


def wallets_management_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Добавить кошелек", callback_data="wallet_add"),
    )
    builder.row(InlineKeyboardButton(text="Назад", callback_data="cancel"))
    return builder.as_markup()


@router.message(Command("wallets"))
async def cmd_wallets(message: Message, session: AsyncSession) -> None:
    user_svc = UserService(session)
    user = await user_svc.get_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("Сначала введите /start")
        return

    wallet_svc = WalletService(session)
    wallets = await wallet_svc.get_wallets(user.id)

    if not wallets:
        await message.answer(
            "У вас нет кошельков.\n\n"
            "Создайте первый кошелек, чтобы начать отслеживать расходы.",
            reply_markup=wallets_management_keyboard(),
        )
        return

    lines = ["<b>💼 Ваши кошельки:</b>\n"]
    for i, wallet in enumerate(wallets, 1):
        emoji = wallet.emoji or "💼"
        lines.append(f"{i}. {emoji} <b>{wallet.name}</b> ({wallet.currency})")

    lines.append("\n<i>Архивированные кошельки не показываются.</i>")

    await message.answer("\n".join(lines), reply_markup=wallets_management_keyboard())


@router.callback_query(F.data == "wallet_add")
async def on_wallet_add(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddWallet.entering_name)
    await callback.message.edit_text(
        "Введите название кошелька (например, 'Основная карта', 'Наличные'):"
    )
    await callback.answer()


@router.message(AddWallet.entering_name)
async def on_wallet_name_from_callback(message: Message, state: FSMContext) -> None:
    """Handle wallet name input from callback."""
    wallet_name = message.text.strip()
    if not wallet_name or len(wallet_name) > 128:
        await message.answer("Введите название от 1 до 128 символов:")
        return

    await state.update_data(wallet_name=wallet_name)

    from src.bot.keyboards.inline import CURRENCIES

    builder = InlineKeyboardBuilder()
    for cur in CURRENCIES:
        builder.button(text=cur, callback_data=f"wallet_cur:{cur}")
    builder.adjust(3)
    builder.row(InlineKeyboardButton(text="Отмена", callback_data="cancel"))

    await state.set_state(AddWallet.choosing_currency)
    await message.answer("Выберите валюту кошелька:", reply_markup=builder.as_markup())


@router.callback_query(AddWallet.choosing_currency, F.data.startswith("wallet_cur:"))
async def on_wallet_currency_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    currency = callback.data.split(":")[1]
    await state.update_data(wallet_currency=currency)

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💳 Карта", callback_data="wallet_emoji:💳"),
        InlineKeyboardButton(text="💰 Наличные", callback_data="wallet_emoji:💰"),
    )
    builder.row(
        InlineKeyboardButton(text="🏦 Счет", callback_data="wallet_emoji:🏦"),
        InlineKeyboardButton(text="📱 Телефон", callback_data="wallet_emoji:📱"),
    )
    builder.row(
        InlineKeyboardButton(text="💎 Другое", callback_data="wallet_emoji:💎"),
        InlineKeyboardButton(text="Пропустить", callback_data="wallet_emoji_skip"),
    )
    builder.row(InlineKeyboardButton(text="Отмена", callback_data="cancel"))

    await state.set_state(AddWallet.choosing_emoji)
    await callback.message.edit_text("Выберите смайлик для кошелька (опционально):", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(AddWallet.choosing_emoji, F.data.startswith("wallet_emoji:"))
async def on_wallet_emoji_chosen(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    emoji = callback.data.split(":")[1]
    await state.update_data(wallet_emoji=emoji)
    await _save_wallet(callback, state, session)


@router.callback_query(AddWallet.choosing_emoji, F.data == "wallet_emoji_skip")
async def on_wallet_emoji_skipped(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.update_data(wallet_emoji=None)
    await _save_wallet(callback, state, session)


async def _save_wallet(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()

    user_svc = UserService(session)
    user = await user_svc.get_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.message.edit_text("Сначала введите /start")
        await state.clear()
        await callback.answer()
        return

    wallet_svc = WalletService(session)
    wallet = await wallet_svc.create(
        user_id=user.id,
        name=data["wallet_name"],
        currency=data["wallet_currency"],
        emoji=data.get("wallet_emoji"),
    )

    emoji = wallet.emoji or "💼"
    await callback.message.edit_text(
        f"✅ Кошелек создан!\n\n"
        f"{emoji} <b>{wallet.name}</b>\n"
        f"Валюта: {wallet.currency}"
    )
    # Reply keyboard (menu) can't be reliably restored via edit_text after inline flows,
    # so we send a separate message to ensure the main menu buttons stay visible.
    await callback.message.answer(
        "Используй кнопки меню или /help для списка команд.",
        reply_markup=main_menu_keyboard(),
    )
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "cancel", AddWallet.entering_name)
@router.callback_query(F.data == "cancel", AddWallet.choosing_currency)
@router.callback_query(F.data == "cancel", AddWallet.choosing_emoji)
async def on_cancel_wallet(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("Создание кошелька отменено.")
    await callback.answer()
