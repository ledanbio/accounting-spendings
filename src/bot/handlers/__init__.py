from aiogram import Dispatcher

from src.bot.handlers.start import router as start_router
from src.bot.handlers.transaction import router as transaction_router
from src.bot.handlers.category import router as category_router
from src.bot.handlers.balance import router as balance_router
from src.bot.handlers.history import router as history_router
from src.bot.handlers.menu import router as menu_router


def register_routers(dp: Dispatcher) -> None:
    dp.include_routers(
        start_router,
        transaction_router,
        category_router,
        balance_router,
        history_router,
        menu_router,
    )
