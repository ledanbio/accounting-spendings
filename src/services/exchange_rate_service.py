import datetime
import logging
from decimal import Decimal

import aiohttp
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.exchange_rate import ExchangeRate

logger = logging.getLogger(__name__)

NBRB_RATES_URL = "https://api.nbrb.by/exrates/rates?periodicity=0&ondate={date}"

# BYN is the base currency — its rate is always 1.0
BYN_CURRENCY = "BYN"
# NBRB rates stored and used with 2 fractional digits to keep balances consistent
RATE_QUANT = Decimal("0.01")


class ExchangeRateService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def ensure_today_rates(self) -> None:
        """Fetch today's rates from NBRB if they are not already stored."""
        today = datetime.date.today()
        stmt = select(ExchangeRate).where(ExchangeRate.date == today).limit(1)
        result = await self.session.execute(stmt)
        if result.scalar_one_or_none() is not None:
            return
        await self._fetch_and_store(today)

    async def _fetch_and_store(self, date: datetime.date) -> None:
        url = NBRB_RATES_URL.format(date=date.isoformat())
        logger.info("Fetching NBRB exchange rates for %s", date)
        try:
            async with aiohttp.ClientSession() as http:
                async with http.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
        except Exception as exc:
            logger.error("Failed to fetch NBRB rates: %s", exc)
            return

        # Remove stale rates for this date before inserting fresh ones
        await self.session.execute(delete(ExchangeRate).where(ExchangeRate.date == date))

        for item in data:
            abbr: str = item.get("Cur_Abbreviation", "")
            official_rate = item.get("Cur_OfficialRate")
            scale = item.get("Cur_Scale", 1)
            if not abbr or official_rate is None or scale == 0:
                continue
            rate_byn = (Decimal(str(official_rate)) / Decimal(str(scale))).quantize(RATE_QUANT)
            self.session.add(ExchangeRate(currency=abbr, rate_byn=rate_byn, date=date))

        await self.session.commit()
        logger.info("Stored NBRB rates for %s (%d records)", date, len(data))

    async def get_rate_byn(self, currency: str, date: datetime.date | None = None) -> Decimal:
        """Return BYN per 1 unit of *currency*. BYN itself returns 1.0."""
        if currency == BYN_CURRENCY:
            return Decimal("1.00")
        target_date = date or datetime.date.today()
        stmt = select(ExchangeRate.rate_byn).where(
            ExchangeRate.currency == currency,
            ExchangeRate.date == target_date,
        )
        result = await self.session.execute(stmt)
        rate = result.scalar_one_or_none()
        if rate is None:
            # Fallback: fetch on demand
            await self._fetch_and_store(target_date)
            result = await self.session.execute(stmt)
            rate = result.scalar_one_or_none()
        if rate is None:
            raise ValueError(f"No exchange rate available for {currency} on {target_date}")
        return rate.quantize(RATE_QUANT)

    async def convert(
        self,
        amount: Decimal,
        from_currency: str,
        to_currency: str,
        date: datetime.date | None = None,
    ) -> tuple[Decimal, Decimal]:
        """Convert *amount* from *from_currency* to *to_currency* via BYN.

        Returns (converted_amount, effective_rate) where effective_rate = to_amount / from_amount.
        """
        if from_currency == to_currency:
            return amount, Decimal("1.00")
        from_rate = await self.get_rate_byn(from_currency, date)
        to_rate = await self.get_rate_byn(to_currency, date)
        byn_amount = amount * from_rate
        to_amount = (byn_amount / to_rate).quantize(Decimal("0.01"))
        effective_rate = (to_amount / amount).quantize(RATE_QUANT) if amount else Decimal("0.00")
        return to_amount, effective_rate
