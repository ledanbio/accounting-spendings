import datetime
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.category import Category
from src.database.models.transaction import Transaction
from src.services.exchange_rate_service import ExchangeRateService


class AnalyticsService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.fx = ExchangeRateService(session)
        self._rate_cache: dict[tuple[str, datetime.date], Decimal] = {}

    async def get_user_date_bounds(self, user_id: int) -> tuple[datetime.date, datetime.date] | None:
        stmt = select(
            func.min(Transaction.transaction_date),
            func.max(Transaction.transaction_date),
        ).where(Transaction.user_id == user_id)
        result = await self.session.execute(stmt)
        min_date, max_date = result.one()
        if min_date is None or max_date is None:
            return None
        return min_date, max_date

    async def build_overview(
        self,
        user_id: int,
        default_currency: str,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> dict:
        points = await self._timeseries(user_id, default_currency, start_date, end_date)
        totals = self._totals_from_points(points)
        prev_start, prev_end = self._previous_window(start_date, end_date)
        prev_points = await self._timeseries(user_id, default_currency, prev_start, prev_end)
        prev_totals = self._totals_from_points(prev_points)
        deltas = self._compute_deltas(totals, prev_totals)

        categories = await self._category_breakdown(user_id, default_currency, start_date, end_date)
        prev_categories = await self._category_breakdown(user_id, default_currency, prev_start, prev_end)
        recommendations = self._build_recommendations(
            totals=totals,
            prev_totals=prev_totals,
            categories=categories,
            prev_categories=prev_categories,
            deltas=deltas,
        )
        return {
            "points": points,
            "totals": totals,
            "prev_totals": prev_totals,
            "deltas": deltas,
            "recommendations": recommendations,
            "category_rows": categories,
        }

    async def build_category_analytics(
        self,
        user_id: int,
        default_currency: str,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> dict:
        categories = await self._category_breakdown(user_id, default_currency, start_date, end_date)
        prev_start, prev_end = self._previous_window(start_date, end_date)
        prev_categories = await self._category_breakdown(user_id, default_currency, prev_start, prev_end)
        income_rows = [r for r in categories if r["type"] == "income"]
        expense_rows = [r for r in categories if r["type"] == "expense"]

        recommendations = self._build_category_recommendations(expense_rows, income_rows, prev_categories)
        return {
            "income_rows": income_rows,
            "expense_rows": expense_rows,
            "recommendations": recommendations,
            "category_rows": categories,
        }

    async def _timeseries(
        self,
        user_id: int,
        default_currency: str,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> list[dict]:
        stmt = (
            select(
                Transaction.transaction_date,
                Transaction.type,
                Transaction.currency,
                func.sum(Transaction.amount).label("total"),
            )
            .where(
                Transaction.user_id == user_id,
                Transaction.transaction_date >= start_date,
                Transaction.transaction_date <= end_date,
            )
            .group_by(Transaction.transaction_date, Transaction.type, Transaction.currency)
            .order_by(Transaction.transaction_date.asc())
        )
        result = await self.session.execute(stmt)
        by_date: dict[datetime.date, dict[str, Decimal]] = defaultdict(
            lambda: {"income": Decimal("0"), "expense": Decimal("0")}
        )

        for dt, txn_type, currency, total in result.all():
            converted = await self._convert_cached(total, currency, default_currency, dt)
            by_date[dt][txn_type] += converted

        points: list[dict] = []
        cursor = start_date
        while cursor <= end_date:
            income = by_date[cursor]["income"].quantize(Decimal("0.01"))
            expense = by_date[cursor]["expense"].quantize(Decimal("0.01"))
            points.append(
                {
                    "date": cursor,
                    "label": cursor.strftime("%d.%m"),
                    "income": income,
                    "expense": expense,
                    "net": (income - expense).quantize(Decimal("0.01")),
                }
            )
            cursor += datetime.timedelta(days=1)
        return points

    async def _category_breakdown(
        self,
        user_id: int,
        default_currency: str,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> list[dict]:
        stmt = (
            select(
                Transaction.type,
                Transaction.currency,
                Transaction.transaction_date,
                Category.name,
                func.sum(Transaction.amount).label("total"),
            )
            .join(Category, Category.id == Transaction.category_id, isouter=True)
            .where(
                Transaction.user_id == user_id,
                Transaction.transaction_date >= start_date,
                Transaction.transaction_date <= end_date,
            )
            .group_by(
                Transaction.type,
                Transaction.currency,
                Transaction.transaction_date,
                Category.name,
            )
        )
        result = await self.session.execute(stmt)
        grouped: dict[tuple[str, str], Decimal] = defaultdict(lambda: Decimal("0"))
        for txn_type, currency, dt, category_name, total in result.all():
            name = category_name or "Без категории"
            converted = await self._convert_cached(total, currency, default_currency, dt)
            grouped[(name, txn_type)] += converted

        rows = [
            {
                "name": name,
                "type": txn_type,
                "total": amount.quantize(Decimal("0.01")),
            }
            for (name, txn_type), amount in grouped.items()
        ]
        rows.sort(key=lambda x: x["total"], reverse=True)
        return rows

    async def _convert_cached(
        self,
        amount: Decimal,
        from_currency: str,
        to_currency: str,
        on_date: datetime.date,
    ) -> Decimal:
        if from_currency == to_currency:
            return amount.quantize(Decimal("0.01"))
        from_key = (from_currency, on_date)
        to_key = (to_currency, on_date)
        if from_key not in self._rate_cache:
            self._rate_cache[from_key] = await self.fx.get_rate_byn(from_currency, on_date)
        if to_key not in self._rate_cache:
            self._rate_cache[to_key] = await self.fx.get_rate_byn(to_currency, on_date)
        byn_amount = amount * self._rate_cache[from_key]
        return (byn_amount / self._rate_cache[to_key]).quantize(Decimal("0.01"))

    @staticmethod
    def _totals_from_points(points: list[dict]) -> dict[str, Decimal]:
        income = sum((p["income"] for p in points), Decimal("0")).quantize(Decimal("0.01"))
        expense = sum((p["expense"] for p in points), Decimal("0")).quantize(Decimal("0.01"))
        return {
            "income": income,
            "expense": expense,
            "net": (income - expense).quantize(Decimal("0.01")),
        }

    @staticmethod
    def _previous_window(
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> tuple[datetime.date, datetime.date]:
        days = (end_date - start_date).days + 1
        prev_end = start_date - datetime.timedelta(days=1)
        prev_start = prev_end - datetime.timedelta(days=days - 1)
        return prev_start, prev_end

    @staticmethod
    def _pct_change(current: Decimal, previous: Decimal) -> Decimal:
        if previous == 0:
            return Decimal("0")
        return ((current - previous) / previous * Decimal("100")).quantize(Decimal("0.01"))

    def _compute_deltas(self, totals: dict[str, Decimal], prev_totals: dict[str, Decimal]) -> dict[str, Decimal]:
        return {
            "income_pct": self._pct_change(totals["income"], prev_totals["income"]),
            "expense_pct": self._pct_change(totals["expense"], prev_totals["expense"]),
            "net_pct": self._pct_change(totals["net"], prev_totals["net"]),
        }

    def _build_recommendations(
        self,
        totals: dict[str, Decimal],
        prev_totals: dict[str, Decimal],
        categories: list[dict],
        prev_categories: list[dict],
        deltas: dict[str, Decimal],
    ) -> list[str]:
        recommendations: list[str] = []

        if deltas["expense_pct"] > Decimal("15"):
            recommendations.append(
                f"Расходы выросли на {deltas['expense_pct']}% к предыдущему периоду. "
                "Проверьте переменные траты и лимиты по категориям."
            )
        elif deltas["expense_pct"] < Decimal("-10"):
            recommendations.append(
                f"Расходы снизились на {abs(deltas['expense_pct'])}%. Текущая динамика расходов позитивная."
            )

        if deltas["income_pct"] < Decimal("-10"):
            recommendations.append(
                f"Доходы снизились на {abs(deltas['income_pct'])}% относительно прошлого окна. "
                "Стоит заложить резерв и сократить необязательные траты."
            )
        elif deltas["income_pct"] > Decimal("10"):
            recommendations.append(
                f"Доходы выросли на {deltas['income_pct']}%. Рекомендуется часть прироста направить в накопления."
            )

        expense_rows = [r for r in categories if r["type"] == "expense"]
        if expense_rows and totals["expense"] > 0:
            top = expense_rows[0]
            share = (top["total"] / totals["expense"] * Decimal("100")).quantize(Decimal("0.01"))
            if share >= Decimal("35"):
                recommendations.append(
                    f"Категория '{top['name']}' занимает {share}% расходов. "
                    "Есть риск концентрации, рассмотрите бюджетный лимит на эту категорию."
                )

        current_by_cat = {(r["name"], r["type"]): r["total"] for r in categories}
        prev_by_cat = {(r["name"], r["type"]): r["total"] for r in prev_categories}
        spikes: list[tuple[str, Decimal]] = []
        for key, current_total in current_by_cat.items():
            if key[1] != "expense":
                continue
            prev_total = prev_by_cat.get(key, Decimal("0"))
            if prev_total <= 0:
                continue
            pct = self._pct_change(current_total, prev_total)
            if pct >= Decimal("25"):
                spikes.append((key[0], pct))
        spikes.sort(key=lambda x: x[1], reverse=True)
        for name, pct in spikes[:2]:
            recommendations.append(
                f"Расходы по категории '{name}' выросли на {pct}% к предыдущему периоду. "
                "Проверьте частоту и средний чек по этой категории."
            )

        if not recommendations:
            recommendations.append(
                "Существенных отклонений не обнаружено. Поддерживайте текущий ритм и регулярно пересматривайте лимиты."
            )
        return recommendations

    def _build_category_recommendations(
        self,
        expense_rows: list[dict],
        income_rows: list[dict],
        prev_categories: list[dict],
    ) -> list[str]:
        recommendations: list[str] = []
        if expense_rows:
            top_expense = expense_rows[0]
            recommendations.append(
                f"Главная расходная категория: '{top_expense['name']}' ({top_expense['total']})."
            )
        if income_rows:
            top_income = income_rows[0]
            recommendations.append(
                f"Основной источник дохода: '{top_income['name']}' ({top_income['total']})."
            )

        prev_map = {(r["name"], r["type"]): r["total"] for r in prev_categories}
        growth_hits: list[tuple[str, Decimal]] = []
        for row in expense_rows:
            prev_total = prev_map.get((row["name"], "expense"), Decimal("0"))
            if prev_total > 0:
                pct = self._pct_change(row["total"], prev_total)
                if pct >= Decimal("25"):
                    growth_hits.append((row["name"], pct))
        growth_hits.sort(key=lambda x: x[1], reverse=True)
        for name, pct in growth_hits[:2]:
            recommendations.append(
                f"Категория '{name}' ускорила рост расходов на {pct}%. "
                "Рекомендуется ввести лимит или сократить частоту покупок."
            )

        if not recommendations:
            recommendations.append(
                "По категориям нет выраженных аномалий. Можно использовать текущую структуру бюджета как базовую."
            )
        return recommendations
