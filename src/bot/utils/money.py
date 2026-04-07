from decimal import Decimal, InvalidOperation

_MONEY_QUANT = Decimal("0.01")


def parse_money_amount(text: str) -> tuple[Decimal | None, str | None]:
    """Parse a positive monetary amount with at most 2 fractional digits.

    Returns (amount, None) on success, or (None, error_message).
    """
    raw = text.strip().replace(",", ".")
    if not raw:
        return None, "Введите сумму."
    try:
        amount = Decimal(raw)
    except InvalidOperation:
        return None, "Некорректное число. Пример: 100 или 50.50"

    if amount <= 0:
        return None, "Сумма должна быть больше нуля."

    # Reject values that need rounding to fit cents (e.g. 1.234)
    if amount != amount.quantize(_MONEY_QUANT):
        return None, "Не более 2 знаков после запятой (копейки, центы)."

    return amount.quantize(_MONEY_QUANT), None
