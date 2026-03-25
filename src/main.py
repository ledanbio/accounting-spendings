import asyncio
import logging
import sys

from src.bot.setup import create_bot, create_dispatcher


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
        force=True,
    )
    logging.getLogger("aiogram").setLevel(logging.INFO)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)


async def main() -> None:
    _configure_logging()
    logging.info("Initializing bot and dispatcher...")
    bot = create_bot()
    dp = create_dispatcher()
    logging.info("Starting long polling (Ctrl+C to stop)")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        _configure_logging()
        logging.exception("Bot stopped with error")
        raise
