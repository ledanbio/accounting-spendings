import asyncio
import datetime
import logging
import sys

from src.bot.setup import create_bot, create_dispatcher
from src.database.session import async_session_maker
from src.services.exchange_rate_service import ExchangeRateService


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
        force=True,
    )
    logging.getLogger("aiogram").setLevel(logging.INFO)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)


async def _rate_refresh_loop() -> None:
    """Fetch today's NBRB rates on startup, then refresh daily at 01:00."""
    while True:
        try:
            async with async_session_maker() as session:
                await ExchangeRateService(session).ensure_today_rates()
        except Exception:
            logging.exception("Rate refresh failed")

        now = datetime.datetime.now()
        tomorrow_1am = (now + datetime.timedelta(days=1)).replace(
            hour=1, minute=0, second=0, microsecond=0
        )
        await asyncio.sleep((tomorrow_1am - now).total_seconds())


async def main() -> None:
    _configure_logging()
    logging.info("Initializing bot and dispatcher...")
    bot = create_bot()
    dp = create_dispatcher()

    # Start daily currency rate refresh in background
    asyncio.create_task(_rate_refresh_loop())

    logging.info("Starting long polling (Ctrl+C to stop)")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        _configure_logging()
        logging.exception("Bot stopped with error")
        raise
