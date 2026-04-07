from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards.inline import (
    manage_categories_keyboard,
    category_type_keyboard,
    deletable_categories_keyboard,
)
from src.bot.states.transaction import AddCategory
from src.database.models.category import Category
from src.services.user_service import UserService
from src.services.category_service import CategoryService

router = Router()


@router.message(Command("categories"))
async def cmd_categories(message: Message, session: AsyncSession) -> None:
    user_svc = UserService(session)
    user = await user_svc.get_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("Сначала введите /start")
        return

    cat_svc = CategoryService(session)
    expense_cats = await cat_svc.get_categories(user.id, "expense")
    income_cats = await cat_svc.get_categories(user.id, "income")

    lines = ["<b>Категории расходов:</b>"]
    for c in expense_cats:
        prefix = "📌" if c.is_default else "👤"
        emoji = f"{c.emoji} " if c.emoji else ""
        lines.append(f"  {prefix} {emoji}{c.name}")

    lines.append("\n<b>Категории доходов:</b>")
    for c in income_cats:
        prefix = "📌" if c.is_default else "👤"
        emoji = f"{c.emoji} " if c.emoji else ""
        lines.append(f"  {prefix} {emoji}{c.name}")

    lines.append("\n📌 — предустановленная, 👤 — пользовательская")

    await message.answer(
        "\n".join(lines),
        reply_markup=manage_categories_keyboard(),
    )


@router.callback_query(F.data == "cat_add")
async def on_add_category(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddCategory.choosing_type)
    await callback.message.edit_text(
        "Выберите тип категории:",
        reply_markup=category_type_keyboard(),
    )
    await callback.answer()


@router.callback_query(AddCategory.choosing_type, F.data.startswith("cattype:"))
async def on_category_type_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    cat_type = callback.data.split(":")[1]
    await state.update_data(cat_type=cat_type)
    await state.set_state(AddCategory.entering_name)
    await callback.message.edit_text("Введите название новой категории:")
    await callback.answer()


@router.message(AddCategory.entering_name)
async def on_category_name_entered(
    message: Message, state: FSMContext
) -> None:
    name = message.text.strip()
    if not name or len(name) > 64:
        await message.answer("Название должно быть от 1 до 64 символов. Попробуйте ещё раз:")
        return

    await state.update_data(cat_name=name)

    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    emojis = ["🍕", "🚗", "🏠", "🎮", "💊", "👕", "📚", "🎭", "💼", "⚽", "📱", "✈️"]
    for emoji in emojis:
        builder.button(text=emoji, callback_data=f"catemoji:{emoji}")
    builder.adjust(6)
    builder.row(InlineKeyboardButton(text="Пропустить", callback_data="catemoji_skip"))
    builder.row(InlineKeyboardButton(text="Отмена", callback_data="cancel"))

    await state.set_state(AddCategory.choosing_emoji)
    await message.answer("Выберите смайлик для категории (опционально):", reply_markup=builder.as_markup())


@router.callback_query(AddCategory.choosing_emoji, F.data.startswith("catemoji:"))
async def on_category_emoji_chosen(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    emoji = callback.data.split(":")[1]
    await state.update_data(cat_emoji=emoji)
    await _save_category(callback, state, session)


@router.callback_query(AddCategory.choosing_emoji, F.data == "catemoji_skip")
async def on_category_emoji_skipped(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    await state.update_data(cat_emoji=None)
    await _save_category(callback, state, session)


async def _save_category(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    user_svc = UserService(session)
    user = await user_svc.get_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.message.edit_text("Сначала введите /start")
        await state.clear()
        await callback.answer()
        return

    cat_svc = CategoryService(session)
    category = await cat_svc.create(
        name=data["cat_name"],
        type_=data["cat_type"],
        user_id=user.id,
        emoji=data.get("cat_emoji"),
    )

    type_label = "расходов" if category.type == "expense" else "доходов"
    emoji = f"{category.emoji} " if category.emoji else ""
    await callback.message.edit_text(f"✅ Категория «{emoji}{category.name}» ({type_label}) добавлена!")
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "cat_del")
async def on_delete_category(callback: CallbackQuery, session: AsyncSession) -> None:
    user_svc = UserService(session)
    user = await user_svc.get_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.message.edit_text("Сначала введите /start")
        await callback.answer()
        return

    stmt = (
        select(Category)
        .where(Category.user_id == user.id, Category.is_default.is_(False))
        .order_by(Category.name)
    )
    result = await session.execute(stmt)
    custom_cats = list(result.scalars().all())

    if not custom_cats:
        await callback.message.edit_text("У вас нет пользовательских категорий для удаления.")
        await callback.answer()
        return

    await callback.message.edit_text(
        "Выберите категорию для удаления:",
        reply_markup=deletable_categories_keyboard(custom_cats),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("catdel:"))
async def on_category_delete_confirmed(
    callback: CallbackQuery, session: AsyncSession
) -> None:
    category_id = int(callback.data.split(":")[1])
    user_svc = UserService(session)
    user = await user_svc.get_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.message.edit_text("Сначала введите /start")
        await callback.answer()
        return

    cat_svc = CategoryService(session)
    deleted = await cat_svc.delete(category_id, user.id)
    if deleted:
        await callback.message.edit_text("✅ Категория удалена.")
    else:
        await callback.message.edit_text("Не удалось удалить категорию.")
    await callback.answer()


@router.callback_query(
    F.data == "cancel",
    AddCategory.choosing_type,
)
@router.callback_query(
    F.data == "cancel",
    AddCategory.entering_name,
)
@router.callback_query(
    F.data == "cancel",
    AddCategory.choosing_emoji,
)
async def on_cancel_add_category(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("Добавление категории отменено.")
    await callback.answer()
