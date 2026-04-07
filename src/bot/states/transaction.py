from aiogram.fsm.state import State, StatesGroup


class AddTransaction(StatesGroup):
    choosing_type = State()
    choosing_wallet = State()
    choosing_category = State()
    entering_amount = State()
    choosing_currency = State()
    entering_description = State()


class AddCategory(StatesGroup):
    choosing_type = State()
    entering_name = State()
    choosing_emoji = State()
