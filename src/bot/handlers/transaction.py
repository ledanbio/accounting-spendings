from decimal import Decimal, InvalidOperation

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards.inline import (
    transaction_type_keyboard,
    categories_keyboard,
    currency_keyboard,
    skip_keyboard,
)
from src.bot.states.transaction import AddTransaction
from src.services.user_service import UserService
from src.services.category_service import CategoryService
from src.services.transaction_service import TransactionService

router = Router()


@router.message(Command("add"))
async def cmd_add(message: Message, state: FSMContext) -> None:
    await state.set_state(AddTransaction.choosing_type)
    await message.answer(
        "Выберите тип операции:",
        reply_markup=transaction_type_keyboard(),
    )


@router.callback_query(AddTransaction.choosing_type, F.data.startswith("txn_type:"))
async def on_type_chosen(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    txn_type = callback.data.split(":")[1]
    await state.update_data(txn_type=txn_type)

    user_svc = UserService(session)
    user = await user_svc.get_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.message.edit_text("Сначала введите /start")
        await state.clear()
        await callback.answer()
        return

    await state.update_data(user_id=user.id, default_currency=user.default_currency)

    cat_svc = CategoryService(session)
    categories = await cat_svc.get_categories(user.id, txn_type)

    label = "расхода" if txn_type == "expense" else "дохода"
    await callback.message.edit_text(
        f"Выберите категорию {label}:",
        reply_markup=categories_keyboard(categories),
    )
    await state.set_state(AddTransaction.choosing_category)
    await callback.answer()


@router.callback_query(AddTransaction.choosing_category, F.data.startswith("cat:"))
async def on_category_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    category_id = int(callback.data.split(":")[1])
    await state.update_data(category_id=category_id)
    await callback.message.edit_text("Введите сумму:")
    await state.set_state(AddTransaction.entering_amount)
    await callback.answer()


@router.message(AddTransaction.entering_amount)
async def on_amount_entered(message: Message, state: FSMContext) -> None:
    try:
        amount = Decimal(message.text.replace(",", "."))
        if amount <= 0:
            raise ValueError
    except (InvalidOperation, ValueError):
        await message.answer("Введите корректную положительную сумму:")
        return

    await state.update_data(amount=str(amount))
    data = await state.get_data()
    await message.answer(
        "Выберите валюту:",
        reply_markup=currency_keyboard(data["default_currency"]),
    )
    await state.set_state(AddTransaction.choosing_currency)


@router.callback_query(AddTransaction.choosing_currency, F.data.startswith("cur:"))
async def on_currency_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    currency = callback.data.split(":")[1]
    await state.update_data(currency=currency)
    await callback.message.edit_text(
        "Добавьте описание (или нажмите «Пропустить»):",
        reply_markup=skip_keyboard(),
    )
    await state.set_state(AddTransaction.entering_description)
    await callback.answer()


@router.callback_query(AddTransaction.entering_description, F.data == "skip")
async def on_description_skipped(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    await _save_transaction(callback.message, state, session, description=None)
    await callback.answer()


@router.message(AddTransaction.entering_description)
async def on_description_entered(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    await _save_transaction(message, state, session, description=message.text)


async def _save_transaction(
    target: Message,
    state: FSMContext,
    session: AsyncSession,
    description: str | None,
) -> None:
    data = await state.get_data()
    svc = TransactionService(session)
    cat_svc = CategoryService(session)

    txn = await svc.create(
        user_id=data["user_id"],
        category_id=data["category_id"],
        amount=Decimal(data["amount"]),
        currency=data["currency"],
        type_=data["txn_type"],
        description=description,
    )

    category = await cat_svc.get_by_id(txn.category_id)
    type_label = "Расход" if txn.type == "expense" else "Доход"

    await target.answer(
        f"✅ <b>{type_label} записан!</b>\n\n"
        f"Категория: {category.name if category else '—'}\n"
        f"Сумма: {txn.amount} {txn.currency}\n"
        f"Описание: {txn.description or '—'}\n"
        f"Дата: {txn.transaction_date}"
    )
    await state.clear()


@router.callback_query(
    F.data == "cancel",
    AddTransaction.choosing_type,
)
@router.callback_query(
    F.data == "cancel",
    AddTransaction.choosing_category,
)
@router.callback_query(
    F.data == "cancel",
    AddTransaction.choosing_currency,
)
@router.callback_query(
    F.data == "cancel",
    AddTransaction.entering_description,
)
async def on_cancel_transaction(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("Добавление отменено.")
    await callback.answer()
