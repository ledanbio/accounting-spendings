from decimal import Decimal

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards.inline import (
    transfer_source_keyboard,
    transfer_dest_keyboard,
    confirm_transfer_keyboard,
)
from src.bot.states.transfer import AddTransfer
from src.bot.utils.money import parse_money_amount
from src.services.transfer_service import TransferService
from src.services.user_service import UserService
from src.services.wallet_service import WalletService

router = Router()


async def _get_user_and_wallets(session: AsyncSession, tg_id: int):
    user = await UserService(session).get_by_telegram_id(tg_id)
    if not user:
        return None, []
    wallets = await WalletService(session).get_wallets(user.id)
    return user, wallets


@router.message(Command("transfer"))
async def cmd_transfer(message: Message, state: FSMContext, session: AsyncSession) -> None:
    user, wallets = await _get_user_and_wallets(session, message.from_user.id)
    if not user:
        await message.answer("Сначала введите /start")
        return
    if len(wallets) < 2:
        await message.answer("Для перевода нужно минимум 2 кошелька.\n\nДобавьте ещё кошелёк в /wallets.")
        return

    await state.set_state(AddTransfer.choosing_from_wallet)
    await message.answer(
        "💸 <b>Перевод между кошельками</b>\n\nОткуда переводим?",
        reply_markup=transfer_source_keyboard(wallets),
    )


@router.callback_query(AddTransfer.choosing_from_wallet, F.data.startswith("tr_from:"))
async def on_from_wallet_chosen(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    from_wallet_id = int(callback.data.split(":")[1])
    user, wallets = await _get_user_and_wallets(session, callback.from_user.id)
    if not user:
        await callback.message.edit_text("Ошибка: пользователь не найден.")
        await state.clear()
        await callback.answer()
        return

    from_wallet = next((w for w in wallets if w.id == from_wallet_id), None)
    if not from_wallet:
        await callback.answer("Кошелёк не найден.", show_alert=True)
        return

    await state.update_data(from_wallet_id=from_wallet_id, from_wallet_name=from_wallet.name, from_currency=from_wallet.currency)
    await state.set_state(AddTransfer.choosing_to_wallet)
    await callback.message.edit_text(
        f"💸 <b>Перевод</b>\n\nИз: {from_wallet.emoji or '💼'} {from_wallet.name} ({from_wallet.currency})\n\nКуда переводим?",
        reply_markup=transfer_dest_keyboard(wallets, exclude_id=from_wallet_id),
    )
    await callback.answer()


@router.callback_query(AddTransfer.choosing_to_wallet, F.data.startswith("tr_to:"))
async def on_to_wallet_chosen(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    to_wallet_id = int(callback.data.split(":")[1])
    _, wallets = await _get_user_and_wallets(session, callback.from_user.id)
    to_wallet = next((w for w in wallets if w.id == to_wallet_id), None)
    if not to_wallet:
        await callback.answer("Кошелёк не найден.", show_alert=True)
        return

    data = await state.get_data()
    await state.update_data(to_wallet_id=to_wallet_id, to_wallet_name=to_wallet.name, to_currency=to_wallet.currency)
    await state.set_state(AddTransfer.entering_amount)
    await callback.message.edit_text(
        f"💸 <b>Перевод</b>\n\n"
        f"Из: {data['from_wallet_name']} ({data['from_currency']})\n"
        f"Куда: {to_wallet.name} ({to_wallet.currency})\n\n"
        f"Введите сумму в <b>{data['from_currency']}</b>:"
    )
    await callback.answer()


@router.message(AddTransfer.entering_amount)
async def on_amount_entered(message: Message, state: FSMContext, session: AsyncSession) -> None:
    amount, err = parse_money_amount(message.text)
    if err:
        await message.answer(err)
        return

    data = await state.get_data()
    from_wallet_id: int = data["from_wallet_id"]
    to_wallet_id: int = data["to_wallet_id"]

    try:
        svc = TransferService(session)
        to_amount, rate = await svc.preview(from_wallet_id, to_wallet_id, amount)
    except Exception as exc:
        await message.answer(f"Ошибка получения курса: {exc}\n\nПопробуйте позже.")
        return

    await state.update_data(from_amount=str(amount), to_amount=str(to_amount), exchange_rate=str(rate))

    from_currency = data["from_currency"]
    to_currency = data["to_currency"]
    same_currency = from_currency == to_currency

    if same_currency:
        conversion_line = ""
    else:
        conversion_line = f"\nКурс: 1 {from_currency} = {rate:.2f} {to_currency}"

    await state.set_state(AddTransfer.confirming)
    await message.answer(
        f"💸 <b>Подтвердите перевод</b>\n\n"
        f"Из: <b>{data['from_wallet_name']}</b> → {amount} {from_currency}\n"
        f"Куда: <b>{data['to_wallet_name']}</b> ← {to_amount} {to_currency}"
        f"{conversion_line}",
        reply_markup=confirm_transfer_keyboard(),
    )


@router.callback_query(AddTransfer.confirming, F.data == "tr_confirm")
async def on_transfer_confirmed(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    user = await UserService(session).get_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.message.edit_text("Ошибка: пользователь не найден.")
        await state.clear()
        await callback.answer()
        return

    try:
        transfer = await TransferService(session).create(
            user_id=user.id,
            from_wallet_id=data["from_wallet_id"],
            to_wallet_id=data["to_wallet_id"],
            from_amount=Decimal(data["from_amount"]),
        )
    except Exception as exc:
        await callback.message.edit_text(f"Ошибка при создании перевода: {exc}")
        await state.clear()
        await callback.answer()
        return

    same = transfer.from_currency == transfer.to_currency
    rate_line = "" if same else f"\n📈 Курс: 1 {transfer.from_currency} = {transfer.exchange_rate:.2f} {transfer.to_currency}"

    await callback.message.edit_text(
        f"✅ <b>Перевод выполнен!</b>\n\n"
        f"💸 {transfer.from_amount} {transfer.from_currency} → {transfer.to_amount} {transfer.to_currency}"
        f"{rate_line}\n\n"
        f"Из: <b>{data['from_wallet_name']}</b>\n"
        f"Куда: <b>{data['to_wallet_name']}</b>"
    )
    await state.clear()
    await callback.answer()


@router.message(Command("transfers"))
async def cmd_transfers(message: Message, session: AsyncSession) -> None:
    user = await UserService(session).get_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("Сначала введите /start")
        return

    svc = TransferService(session)
    transfers = await svc.get_recent(user.id, limit=10)
    if not transfers:
        await message.answer("Переводов пока нет.")
        return

    lines = ["<b>🔄 Последние переводы:</b>\n"]
    for t in transfers:
        from_e = t.from_wallet.emoji or "💼"
        to_e = t.to_wallet.emoji or "💼"
        same = t.from_currency == t.to_currency
        if same:
            amount_str = f"{t.from_amount} {t.from_currency}"
        else:
            amount_str = f"{t.from_amount} {t.from_currency} → {t.to_amount} {t.to_currency}"
        lines.append(
            f"📅 {t.transfer_date.strftime('%d.%m.%Y')} — {from_e} {t.from_wallet.name} → {to_e} {t.to_wallet.name}\n"
            f"   💸 {amount_str}"
        )

    await message.answer("\n\n".join(lines))


# Cancel handlers for each FSM state
@router.callback_query(F.data == "cancel", AddTransfer.choosing_from_wallet)
@router.callback_query(F.data == "cancel", AddTransfer.choosing_to_wallet)
@router.callback_query(F.data == "cancel", AddTransfer.confirming)
async def on_cancel_transfer_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("Перевод отменён.")
    await callback.answer()


@router.message(F.text, AddTransfer.choosing_from_wallet)
@router.message(F.text, AddTransfer.choosing_to_wallet)
@router.message(F.text, AddTransfer.confirming)
async def on_cancel_transfer_message(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Перевод отменён.")
