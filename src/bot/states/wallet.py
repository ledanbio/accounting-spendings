from aiogram.fsm.state import State, StatesGroup


class AddWallet(StatesGroup):
    entering_name = State()
    choosing_currency = State()
    choosing_emoji = State()
