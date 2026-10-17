"""Aritmética monetaria con Decimal y redondeo bancario controlado."""
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
ZERO = Decimal("0")


def D(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value is None:
        return ZERO
    return Decimal(str(value))


def money(value) -> Decimal:
    return D(value).quantize(CENT, rounding=ROUND_HALF_UP)


def qty(value) -> Decimal:
    return D(value).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def to_functional(amount, rate) -> Decimal:
    return money(D(amount) * D(rate))
