from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards.reply import (
    BTN_ADD,
    BTN_ANALYTICS,
    BTN_BALANCE,
    BTN_HELP,
    BTN_HISTORY,
    BTN_SETTINGS,
    BTN_TRANSFER,
)
from src.bot.handlers.start import cmd_help, cmd_settings
from src.bot.handlers.transaction import cmd_add
from src.bot.handlers.balance import cmd_balance
from src.bot.handlers.history import cmd_history
from src.bot.handlers.transfer import cmd_transfer
from src.bot.handlers.analytics import cmd_analytics

router = Router()


@router.message(F.text == BTN_ADD)
async def on_btn_add(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await cmd_add(message, state, session)


@router.message(F.text == BTN_BALANCE)
async def on_btn_balance(message: Message, session: AsyncSession) -> None:
    await cmd_balance(message, session)


@router.message(F.text == BTN_HISTORY)
async def on_btn_history(message: Message, session: AsyncSession) -> None:
    await cmd_history(message, session)


@router.message(F.text == BTN_SETTINGS)
async def on_btn_settings(message: Message) -> None:
    await cmd_settings(message)


@router.message(F.text == BTN_HELP)
async def on_btn_help(message: Message) -> None:
    await cmd_help(message)


@router.message(F.text == BTN_TRANSFER)
async def on_btn_transfer(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await cmd_transfer(message, state, session)


@router.message(F.text == BTN_ANALYTICS)
async def on_btn_analytics(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await cmd_analytics(message, state, session)
