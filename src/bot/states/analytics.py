from aiogram.fsm.state import State, StatesGroup


class AnalyticsFlow(StatesGroup):
    choosing_mode = State()
    choosing_period = State()
    choosing_custom_mode = State()
    entering_custom_dates = State()
    choosing_custom_month_start = State()
    choosing_custom_month_end = State()
    choosing_category_type = State()
