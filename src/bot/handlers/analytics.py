import datetime
import re

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards.inline import (
    analytics_category_type_keyboard,
    analytics_custom_period_keyboard,
    analytics_mode_keyboard,
    analytics_month_picker_keyboard,
    analytics_period_keyboard,
)
from src.bot.states.analytics import AnalyticsFlow
from src.services.analytics_service import AnalyticsService
from src.services.chart_service import ChartService
from src.services.transaction_service import TransactionService
from src.services.user_service import UserService

router = Router()

DATE_RANGE_RE = re.compile(r"^\s*(\d{2}\.\d{2}\.\d{4})\s*-\s*(\d{2}\.\d{2}\.\d{4})\s*$")


@router.message(Command("analytics"))
async def cmd_analytics(message: Message, state: FSMContext, session: AsyncSession) -> None:
    user = await UserService(session).get_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("Сначала введите /start")
        return
    bounds = await AnalyticsService(session).get_user_date_bounds(user.id)
    if bounds is None:
        await message.answer("Недостаточно данных для аналитики. Добавьте несколько транзакций.")
        return

    await state.clear()
    await state.set_state(AnalyticsFlow.choosing_mode)
    await message.answer(
        "<b>Аналитика</b>\n\nВыберите тип аналитики:",
        reply_markup=analytics_mode_keyboard(),
    )


@router.callback_query(AnalyticsFlow.choosing_mode, F.data.startswith("anl_mode:"))
async def on_analytics_mode(callback: CallbackQuery, state: FSMContext) -> None:
    mode = callback.data.split(":")[1]
    await state.update_data(mode=mode)
    await state.set_state(AnalyticsFlow.choosing_period)
    await callback.message.edit_text(
        "<b>Аналитика</b>\n\nВыберите период:",
        reply_markup=analytics_period_keyboard(),
    )
    await callback.answer()


@router.callback_query(AnalyticsFlow.choosing_period, F.data.startswith("anl_period:"))
async def on_analytics_period(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    period = callback.data.split(":")[1]
    await state.update_data(period=period)
    if period == "custom":
        await state.set_state(AnalyticsFlow.choosing_custom_mode)
        await callback.message.edit_text(
            "Выберите способ задания периода:",
            reply_markup=analytics_custom_period_keyboard(),
        )
        await callback.answer()
        return

    user = await UserService(session).get_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.message.edit_text("Сначала введите /start")
        await state.clear()
        await callback.answer()
        return
    bounds = await AnalyticsService(session).get_user_date_bounds(user.id)
    if bounds is None:
        await callback.message.edit_text("Недостаточно данных для аналитики.")
        await state.clear()
        await callback.answer()
        return

    start_date, end_date = _resolve_preset_period(period, bounds)
    await state.update_data(start_date=start_date.isoformat(), end_date=end_date.isoformat())
    await _continue_after_period(callback, state, session)
    await callback.answer()


@router.callback_query(AnalyticsFlow.choosing_custom_mode, F.data == "anl_custom:manual")
async def on_custom_mode_manual(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AnalyticsFlow.entering_custom_dates)
    await callback.message.edit_text(
        "Введите диапазон дат в формате:\n"
        "<code>DD.MM.YYYY - DD.MM.YYYY</code>"
    )
    await callback.answer()


@router.callback_query(AnalyticsFlow.choosing_custom_mode, F.data == "anl_custom:months")
async def on_custom_mode_months(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    user = await UserService(session).get_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.message.edit_text("Сначала введите /start")
        await state.clear()
        await callback.answer()
        return

    months = await TransactionService(session).get_available_months(user.id, limit=120)
    if not months:
        await callback.message.edit_text("Нет данных для выбора месяцев.")
        await callback.answer()
        return

    await state.update_data(months=months)
    await state.set_state(AnalyticsFlow.choosing_custom_month_start)
    await callback.message.edit_text(
        "Выберите начальный месяц периода:",
        reply_markup=analytics_month_picker_keyboard(months, stage="start", page=0),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("anl_page:"))
async def on_analytics_month_page(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    months = data.get("months", [])
    if not months:
        await callback.answer("Список месяцев пуст.", show_alert=True)
        return
    _, stage, page_s = callback.data.split(":")
    page = max(0, int(page_s))
    await callback.message.edit_reply_markup(
        reply_markup=analytics_month_picker_keyboard(months, stage=stage, page=page),
    )
    await callback.answer()


@router.callback_query(AnalyticsFlow.choosing_custom_month_start, F.data.startswith("anl_pick:start:"))
async def on_custom_month_start_pick(callback: CallbackQuery, state: FSMContext) -> None:
    month = callback.data.split(":")[2]
    data = await state.get_data()
    months = data.get("months", [])
    await state.update_data(custom_start_month=month)
    await state.set_state(AnalyticsFlow.choosing_custom_month_end)
    await callback.message.edit_text(
        f"Начало: <b>{month}</b>\nВыберите конечный месяц:",
        reply_markup=analytics_month_picker_keyboard(months, stage="end", page=0),
    )
    await callback.answer()


@router.callback_query(AnalyticsFlow.choosing_custom_month_end, F.data.startswith("anl_pick:end:"))
async def on_custom_month_end_pick(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    end_month = callback.data.split(":")[2]
    data = await state.get_data()
    start_month = data.get("custom_start_month")
    if not start_month:
        await callback.answer("Сначала выберите начальный месяц.", show_alert=True)
        return

    start = datetime.date.fromisoformat(f"{start_month}-01")
    end_start = datetime.date.fromisoformat(f"{end_month}-01")
    if end_start < start:
        await callback.answer("Конечный месяц не может быть раньше начального.", show_alert=True)
        return

    start_date = start
    end_date = _end_of_month(end_start)
    await state.update_data(start_date=start_date.isoformat(), end_date=end_date.isoformat())
    await _continue_after_period(callback, state, session)
    await callback.answer()


@router.message(AnalyticsFlow.entering_custom_dates)
async def on_custom_dates_entered(message: Message, state: FSMContext, session: AsyncSession) -> None:
    match = DATE_RANGE_RE.match(message.text or "")
    if not match:
        await message.answer("Неверный формат. Используйте: <code>DD.MM.YYYY - DD.MM.YYYY</code>")
        return
    left, right = match.groups()
    try:
        start_date = datetime.datetime.strptime(left, "%d.%m.%Y").date()
        end_date = datetime.datetime.strptime(right, "%d.%m.%Y").date()
    except ValueError:
        await message.answer("Одна из дат некорректна.")
        return
    if end_date < start_date:
        await message.answer("Конечная дата не может быть раньше начальной.")
        return
    if (end_date - start_date).days > 3660:
        await message.answer("Слишком большой диапазон. Укажите период до 10 лет.")
        return

    await state.update_data(start_date=start_date.isoformat(), end_date=end_date.isoformat())
    await _continue_after_period(message, state, session)


@router.callback_query(AnalyticsFlow.choosing_custom_mode, F.data == "anl_back:period")
@router.callback_query(AnalyticsFlow.choosing_category_type, F.data == "anl_back:period")
@router.callback_query(AnalyticsFlow.choosing_custom_month_start, F.data == "anl_back:custom")
@router.callback_query(AnalyticsFlow.choosing_custom_month_end, F.data == "anl_back:custom")
async def on_custom_back(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data == "anl_back:period":
        await state.set_state(AnalyticsFlow.choosing_period)
        await callback.message.edit_text("Выберите период:", reply_markup=analytics_period_keyboard())
    else:
        await state.set_state(AnalyticsFlow.choosing_custom_mode)
        await callback.message.edit_text(
            "Выберите способ задания периода:",
            reply_markup=analytics_custom_period_keyboard(),
        )
    await callback.answer()


@router.callback_query(
    F.data == "cancel",
    AnalyticsFlow.choosing_mode,
)
@router.callback_query(F.data == "cancel", AnalyticsFlow.choosing_period)
@router.callback_query(F.data == "cancel", AnalyticsFlow.choosing_custom_mode)
@router.callback_query(F.data == "cancel", AnalyticsFlow.choosing_custom_month_start)
@router.callback_query(F.data == "cancel", AnalyticsFlow.choosing_custom_month_end)
@router.callback_query(F.data == "cancel", AnalyticsFlow.choosing_category_type)
async def on_analytics_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("Аналитика отменена.")
    await callback.answer()


@router.callback_query(AnalyticsFlow.choosing_category_type, F.data.startswith("anl_cat:"))
async def on_category_type_picked(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    cat_type = callback.data.split(":")[1]
    await state.update_data(category_type=cat_type)
    await _send_analytics_report(callback.message, callback.from_user.id, state, session)
    await state.clear()
    await callback.answer()


async def _continue_after_period(target: Message | CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    mode = data.get("mode")
    if mode == "categories":
        await state.set_state(AnalyticsFlow.choosing_category_type)
        msg = target.message if isinstance(target, CallbackQuery) else target
        if isinstance(target, CallbackQuery):
            await msg.edit_text("Выберите тип категорий:", reply_markup=analytics_category_type_keyboard())
        else:
            await msg.answer("Выберите тип категорий:", reply_markup=analytics_category_type_keyboard())
        return

    if isinstance(target, CallbackQuery):
        msg = target.message
        await msg.edit_text("Готовлю аналитический отчёт...")
        await _send_analytics_report(msg, target.from_user.id, state, session)
    else:
        await target.answer("Готовлю аналитический отчёт...")
        await _send_analytics_report(target, target.from_user.id, state, session)
    await state.clear()


async def _send_analytics_report(
    target: Message,
    telegram_id: int,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    user = await UserService(session).get_by_telegram_id(telegram_id)
    if not user:
        await target.answer("Сначала введите /start")
        return
    data = await state.get_data()
    start_date = datetime.date.fromisoformat(data["start_date"])
    end_date = datetime.date.fromisoformat(data["end_date"])
    mode = data.get("mode", "overview")

    analytics = AnalyticsService(session)
    charts = ChartService()
    period_label = f"{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}"

    if mode == "categories":
        result = await analytics.build_category_analytics(
            user_id=user.id,
            default_currency=user.default_currency,
            start_date=start_date,
            end_date=end_date,
        )
        cat_type = data.get("category_type", "expense")
        rows = result["category_rows"]
        if not any(r["type"] == cat_type for r in rows):
            await target.answer("Нет данных по выбранному типу категорий за этот период.")
            return
        chart = charts.build_category_chart(
            rows=rows,
            currency=user.default_currency,
            title=f"Аналитика по категориям ({period_label})",
            txn_type=cat_type,
        )
        caption = _build_category_caption(result["recommendations"], user.default_currency, cat_type)
    else:
        result = await analytics.build_overview(
            user_id=user.id,
            default_currency=user.default_currency,
            start_date=start_date,
            end_date=end_date,
        )
        totals = result["totals"]
        if totals["income"] == 0 and totals["expense"] == 0:
            await target.answer("Нет данных для выбранного периода.")
            return
        chart = charts.build_overview_chart(
            points=result["points"],
            currency=user.default_currency,
            title=f"Доходы/расходы ({period_label})",
        )
        caption = _build_overview_caption(
            totals=totals,
            deltas=result["deltas"],
            recommendations=result["recommendations"],
            currency=user.default_currency,
        )

    photo = BufferedInputFile(chart, filename="analytics.png")
    await target.answer_photo(photo=photo, caption=caption)


def _resolve_preset_period(
    period: str,
    bounds: tuple[datetime.date, datetime.date],
) -> tuple[datetime.date, datetime.date]:
    today = datetime.date.today()
    first_this_month = today.replace(day=1)
    if period == "month":
        return first_this_month, today
    if period == "3m":
        start_month = _shift_month(first_this_month, -2)
        return start_month, today
    if period == "all":
        return bounds[0], bounds[1]
    return first_this_month, today


def _shift_month(base: datetime.date, delta_months: int) -> datetime.date:
    y = base.year
    m = base.month + delta_months
    while m <= 0:
        m += 12
        y -= 1
    while m > 12:
        m -= 12
        y += 1
    return datetime.date(y, m, 1)


def _end_of_month(dt: datetime.date) -> datetime.date:
    if dt.month == 12:
        return datetime.date(dt.year, 12, 31)
    return datetime.date(dt.year, dt.month + 1, 1) - datetime.timedelta(days=1)


def _build_overview_caption(
    totals: dict,
    deltas: dict,
    recommendations: list[str],
    currency: str,
) -> str:
    lines = [
        "<b>Аналитика доходов и расходов</b>",
        "",
        f"Доход: +{totals['income']} {currency}",
        f"Расход: -{totals['expense']} {currency}",
        f"Сальдо: {totals['net']} {currency}",
        "",
        "<b>Динамика к предыдущему периоду:</b>",
        f"Доход: {deltas['income_pct']}%",
        f"Расход: {deltas['expense_pct']}%",
        f"Сальдо: {deltas['net_pct']}%",
        "",
        "<b>Рекомендации:</b>",
    ]
    lines.extend([f"- {item}" for item in recommendations[:5]])
    return "\n".join(lines)


def _build_category_caption(recommendations: list[str], currency: str, cat_type: str) -> str:
    title = "Категории расходов" if cat_type == "expense" else "Категории доходов"
    lines = [
        f"<b>{title}</b>",
        f"Суммы приведены к {currency}.",
        "",
        "<b>Комментарий:</b>",
    ]
    lines.extend([f"- {item}" for item in recommendations[:5]])
    return "\n".join(lines)
