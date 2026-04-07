from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

BTN_ADD = "Добавить"
BTN_BALANCE = "Баланс"
BTN_HISTORY = "История"
BTN_CATEGORIES = "Категории"
BTN_SETTINGS = "Настройки"
BTN_HELP = "Помощь"
BTN_TRANSFER = "Перевод"

MENU_BUTTONS = {BTN_ADD, BTN_BALANCE, BTN_HISTORY, BTN_CATEGORIES, BTN_SETTINGS, BTN_HELP, BTN_TRANSFER}


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_ADD), KeyboardButton(text=BTN_BALANCE)],
            [KeyboardButton(text=BTN_HISTORY), KeyboardButton(text=BTN_TRANSFER)],
            [KeyboardButton(text=BTN_CATEGORIES), KeyboardButton(text=BTN_SETTINGS)],
            [KeyboardButton(text=BTN_HELP)],
        ],
        resize_keyboard=True,
    )
