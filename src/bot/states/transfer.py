from aiogram.fsm.state import State, StatesGroup


class AddTransfer(StatesGroup):
    choosing_from_wallet = State()
    choosing_to_wallet = State()
    entering_amount = State()
    confirming = State()
