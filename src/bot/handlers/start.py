from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
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
        "/analytics — графики и рекомендации\n"
        "/categories — управление категориями\n"
        "/wallets — управление кошельками\n"
        "/settings — настройки\n"
        "/help — эта справка"
    )


@router.message(Command("settings"))
async def cmd_settings(message: Message) -> None:
    from src.bot.keyboards.inline import settings_menu_keyboard
    await message.answer(
        "⚙️ <b>Настройки</b>",
        reply_markup=settings_menu_keyboard(),
    )


@router.callback_query(F.data == "settings_currency")
async def on_settings_currency(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "Выберите валюту по умолчанию:",
        reply_markup=settings_currency_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "settings_emoji")
async def on_settings_emoji(callback: CallbackQuery, session: AsyncSession) -> None:
    user_svc = UserService(session)
    user = await user_svc.get_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.message.edit_text("Сначала введите /start")
        await callback.answer()
        return

    status = "✅ Включены" if user.emoji_enabled else "❌ Отключены"
    next_action = "Отключить" if user.emoji_enabled else "Включить"

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text=f"{next_action} смайлики",
        callback_data="emoji_toggle"
    ))
    builder.row(InlineKeyboardButton(text="↩️ Назад", callback_data="settings_back"))

    await callback.message.edit_text(
        f"😊 <b>Управление смайликами</b>\n\n"
        f"Смайлики помогают визуально различать категории, кошельки и типы операций.\n\n"
        f"Статус: {status}",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data == "emoji_toggle")
async def on_emoji_toggle(callback: CallbackQuery, session: AsyncSession) -> None:
    user_svc = UserService(session)
    user = await user_svc.get_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.message.edit_text("Сначала введите /start")
        await callback.answer()
        return

    user = await user_svc.toggle_emoji(user.id)
    status = "✅ Включены" if user.emoji_enabled else "❌ Отключены"
    next_action = "Отключить" if user.emoji_enabled else "Включить"

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text=f"{next_action} смайлики",
        callback_data="emoji_toggle"
    ))
    builder.row(InlineKeyboardButton(text="↩️ Назад", callback_data="settings_back"))

    await callback.message.edit_text(
        f"😊 <b>Управление смайликами</b>\n\n"
        f"Смайлики помогают визуально различать категории, кошельки и типы операций.\n\n"
        f"Статус: {status}",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data == "settings_wallets")
async def on_settings_wallets(callback: CallbackQuery, session: AsyncSession) -> None:
    from src.services.wallet_service import WalletService
    
    user_svc = UserService(session)
    user = await user_svc.get_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.message.edit_text("Сначала введите /start")
        await callback.answer()
        return

    wallet_svc = WalletService(session)
    wallets = await wallet_svc.get_wallets(user.id)

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Добавить кошелек", callback_data="wallet_add"))
    
    if wallets:
        builder.row(InlineKeyboardButton(text="📋 Просмотр кошельков", callback_data="wallet_list"))
    
    builder.row(InlineKeyboardButton(text="↩️ Назад", callback_data="settings_back"))

    text = "💼 <b>Управление кошельками</b>\n\n"
    if wallets:
        text += f"У вас {len(wallets)} кошелек(ов).\n\n"
    else:
        text += "У вас нет кошельков.\n\n"
    
    text += "Что вы хотите сделать?"

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "wallet_list")
async def on_wallet_list(callback: CallbackQuery, session: AsyncSession) -> None:
    from src.services.wallet_service import WalletService
    
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

    lines = ["<b>💼 Ваши кошельки:</b>\n"]
    for i, wallet in enumerate(wallets, 1):
        emoji = wallet.emoji or "💼"
        lines.append(f"{i}. {emoji} <b>{wallet.name}</b> ({wallet.currency})")

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="↩️ Назад", callback_data="settings_wallets"))

    await callback.message.edit_text("\n".join(lines), reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "settings_back")
async def on_settings_back(callback: CallbackQuery) -> None:
    from src.bot.keyboards.inline import settings_menu_keyboard
    await callback.message.edit_text(
        "⚙️ <b>Настройки</b>",
        reply_markup=settings_menu_keyboard(),
    )
    await callback.answer()


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
async def on_onboard_wallet(callback: CallbackQuery, state: FSMContext) -> None:
    """Start wallet creation during onboarding."""
    from src.bot.handlers.wallet import on_wallet_add
    
    await on_wallet_add(callback, state)


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
