from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.database.models.category import Category
from src.database.models.wallet import Wallet

CURRENCIES = ["RUB", "USD", "EUR", "KZT", "BYN", "CNY"]


def transaction_type_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Расход", callback_data="txn_type:expense"),
        InlineKeyboardButton(text="Доход", callback_data="txn_type:income"),
    )
    builder.row(InlineKeyboardButton(text="Отмена", callback_data="cancel"))
    return builder.as_markup()


def categories_keyboard(categories: list[Category], show_emojis: bool = True) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for cat in categories:
        prefix = "📌 " if cat.is_default else ""
        emoji = cat.emoji if show_emojis and cat.emoji else ""
        text = f"{prefix}{emoji} {cat.name}".strip()
        builder.button(text=text, callback_data=f"cat:{cat.id}")
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="Отмена", callback_data="cancel"))
    return builder.as_markup()


def currency_keyboard(default_currency: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=f"{default_currency} (по умолчанию)",
        callback_data=f"cur:{default_currency}",
    )
    for cur in CURRENCIES:
        if cur != default_currency:
            builder.button(text=cur, callback_data=f"cur:{cur}")
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="Отмена", callback_data="cancel"))
    return builder.as_markup()


def skip_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Пропустить", callback_data="skip"),
        InlineKeyboardButton(text="Отмена", callback_data="cancel"),
    )
    return builder.as_markup()


def history_keyboard(offset: int, total: int, page_size: int = 10) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    buttons = []
    if offset > 0:
        buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"hist:{offset - page_size}"))
    if offset + page_size < total:
        buttons.append(InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"hist:{offset + page_size}"))
    if buttons:
        builder.row(*buttons)
    return builder.as_markup()


def settings_currency_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for cur in CURRENCIES:
        builder.button(text=cur, callback_data=f"setcur:{cur}")
    builder.adjust(3)
    builder.row(InlineKeyboardButton(text="Отмена", callback_data="cancel"))
    return builder.as_markup()


def manage_categories_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Добавить категорию", callback_data="cat_add"),
        InlineKeyboardButton(text="Удалить категорию", callback_data="cat_del"),
    )
    builder.row(InlineKeyboardButton(text="Назад", callback_data="cancel"))
    return builder.as_markup()


def category_type_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Расход", callback_data="cattype:expense"),
        InlineKeyboardButton(text="Доход", callback_data="cattype:income"),
    )
    builder.row(InlineKeyboardButton(text="Отмена", callback_data="cancel"))
    return builder.as_markup()


def deletable_categories_keyboard(categories: list[Category]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for cat in categories:
        builder.button(text=f"❌ {cat.name} ({cat.type})", callback_data=f"catdel:{cat.id}")
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="Отмена", callback_data="cancel"))
    return builder.as_markup()


def wallets_keyboard(wallets: list[Wallet]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for wallet in wallets:
        emoji = wallet.emoji or "💼"
        text = f"{emoji} {wallet.name} ({wallet.currency})"
        builder.button(text=text, callback_data=f"wallet:{wallet.id}")
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="Отмена", callback_data="cancel"))
    return builder.as_markup()


def wallet_stats_filter_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📈 Доход", callback_data="wallet_filter:income"),
        InlineKeyboardButton(text="📉 Расход", callback_data="wallet_filter:expense"),
    )
    builder.row(InlineKeyboardButton(text="↩️ Назад", callback_data="wallet_back"))
    return builder.as_markup()


def transfer_source_keyboard(wallets: list[Wallet]) -> InlineKeyboardMarkup:
    """Keyboard for picking the source wallet in a transfer."""
    builder = InlineKeyboardBuilder()
    for wallet in wallets:
        emoji = wallet.emoji or "💼"
        text = f"{emoji} {wallet.name} ({wallet.currency})"
        builder.button(text=text, callback_data=f"tr_from:{wallet.id}")
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
    return builder.as_markup()


def transfer_dest_keyboard(wallets: list[Wallet], exclude_id: int) -> InlineKeyboardMarkup:
    """Keyboard for picking the destination wallet in a transfer."""
    builder = InlineKeyboardBuilder()
    for wallet in wallets:
        if wallet.id == exclude_id:
            continue
        emoji = wallet.emoji or "💼"
        text = f"{emoji} {wallet.name} ({wallet.currency})"
        builder.button(text=text, callback_data=f"tr_to:{wallet.id}")
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
    return builder.as_markup()


def confirm_transfer_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data="tr_confirm"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"),
    )
    return builder.as_markup()


def analytics_mode_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Общая аналитика", callback_data="anl_mode:overview"),
    )
    builder.row(
        InlineKeyboardButton(text="По категориям", callback_data="anl_mode:categories"),
    )
    builder.row(InlineKeyboardButton(text="Отмена", callback_data="cancel"))
    return builder.as_markup()


def analytics_period_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Месяц", callback_data="anl_period:month"),
        InlineKeyboardButton(text="3 месяца", callback_data="anl_period:3m"),
    )
    builder.row(
        InlineKeyboardButton(text="Весь период", callback_data="anl_period:all"),
        InlineKeyboardButton(text="Выбранный период", callback_data="anl_period:custom"),
    )
    builder.row(InlineKeyboardButton(text="Отмена", callback_data="cancel"))
    return builder.as_markup()


def analytics_custom_period_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Ввести даты", callback_data="anl_custom:manual"))
    builder.row(InlineKeyboardButton(text="Выбрать месяцы", callback_data="anl_custom:months"))
    builder.row(InlineKeyboardButton(text="Назад", callback_data="anl_back:period"))
    return builder.as_markup()


def analytics_month_picker_keyboard(
    months: list[str],
    stage: str,
    page: int = 0,
    per_page: int = 12,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    start = page * per_page
    end = start + per_page
    page_months = months[start:end]
    for m in page_months:
        builder.button(text=m, callback_data=f"anl_pick:{stage}:{m}")
    builder.adjust(3)

    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(text="⬅️", callback_data=f"anl_page:{stage}:{page - 1}")
        )
    if end < len(months):
        nav_buttons.append(
            InlineKeyboardButton(text="➡️", callback_data=f"anl_page:{stage}:{page + 1}")
        )
    if nav_buttons:
        builder.row(*nav_buttons)
    builder.row(InlineKeyboardButton(text="Назад", callback_data="anl_back:custom"))
    return builder.as_markup()


def analytics_category_type_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Категории расходов", callback_data="anl_cat:expense"),
        InlineKeyboardButton(text="Категории доходов", callback_data="anl_cat:income"),
    )
    builder.row(InlineKeyboardButton(text="Назад", callback_data="anl_back:period"))
    return builder.as_markup()


def settings_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💱 Изменить валюту", callback_data="settings_currency"))
    builder.row(InlineKeyboardButton(text="😊 Управление смайликами", callback_data="settings_emoji"))
    builder.row(InlineKeyboardButton(text="💼 Управление кошельками", callback_data="settings_wallets"))
    builder.row(InlineKeyboardButton(text="Назад", callback_data="cancel"))
    return builder.as_markup()
