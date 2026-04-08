import io
from decimal import Decimal

import matplotlib

matplotlib.use("Agg")

from matplotlib import pyplot as plt


class ChartService:
    def build_overview_chart(
        self,
        points: list[dict],
        currency: str,
        title: str,
    ) -> bytes:
        labels = [p["label"] for p in points]
        incomes = [float(p["income"]) for p in points]
        expenses = [float(p["expense"]) for p in points]

        fig, (ax_line, ax_bar) = plt.subplots(2, 1, figsize=(12, 8), constrained_layout=True)
        fig.suptitle(title)

        ax_line.plot(labels, incomes, color="#2E8B57", linewidth=2, label="Доход")
        ax_line.plot(labels, expenses, color="#C0392B", linewidth=2, label="Расход")
        ax_line.set_ylabel(currency)
        ax_line.legend()
        ax_line.grid(alpha=0.25)
        ax_line.tick_params(axis="x", rotation=35)

        idx = list(range(len(labels)))
        width = 0.4
        ax_bar.bar([i - width / 2 for i in idx], incomes, width=width, color="#6FCF97", label="Доход")
        ax_bar.bar([i + width / 2 for i in idx], expenses, width=width, color="#EB5757", label="Расход")
        ax_bar.set_xticks(idx, labels)
        ax_bar.set_ylabel(currency)
        ax_bar.legend()
        ax_bar.grid(axis="y", alpha=0.25)
        ax_bar.tick_params(axis="x", rotation=35)

        return self._save_to_png(fig)

    def build_category_chart(
        self,
        rows: list[dict],
        currency: str,
        title: str,
        txn_type: str,
    ) -> bytes:
        filtered = [r for r in rows if r["type"] == txn_type]
        filtered.sort(key=lambda x: x["total"], reverse=True)

        top = filtered[:7]
        if len(filtered) > 7:
            other_total = sum((r["total"] for r in filtered[7:]), Decimal("0")).quantize(Decimal("0.01"))
            top.append({"name": "Прочее", "total": other_total, "type": txn_type})

        labels = [r["name"] for r in top]
        values = [float(r["total"]) for r in top]
        color = "#EB5757" if txn_type == "expense" else "#2E8B57"

        fig, ax = plt.subplots(figsize=(10, 6), constrained_layout=True)
        ax.barh(labels, values, color=color)
        ax.invert_yaxis()
        ax.set_title(title)
        ax.set_xlabel(currency)
        ax.grid(axis="x", alpha=0.25)

        return self._save_to_png(fig)

    @staticmethod
    def _save_to_png(fig) -> bytes:
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=160)
        plt.close(fig)
        buf.seek(0)
        return buf.read()
