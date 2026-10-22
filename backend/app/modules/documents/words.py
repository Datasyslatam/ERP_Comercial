"""Valor en letras para recibos y comprobantes de egreso: 1.550.000,50 COP → «UN MILLÓN QUINIENTOS CINCUENTA MIL
PESOS CON 50/100»."""
from decimal import ROUND_HALF_UP, Decimal

_UNITS = ("", "UNO", "DOS", "TRES", "CUATRO", "CINCO", "SEIS", "SIETE", "OCHO", "NUEVE", "DIEZ", "ONCE", "DOCE",
          "TRECE", "CATORCE", "QUINCE", "DIECISÉIS", "DIECISIETE", "DIECIOCHO", "DIECINUEVE", "VEINTE", "VEINTIUNO",
          "VEINTIDÓS", "VEINTITRÉS", "VEINTICUATRO", "VEINTICINCO", "VEINTISÉIS", "VEINTISIETE", "VEINTIOCHO",
          "VEINTINUEVE")
_TENS = ("", "", "", "TREINTA", "CUARENTA", "CINCUENTA", "SESENTA", "SETENTA", "OCHENTA", "NOVENTA")
_HUNDREDS = ("", "CIENTO", "DOSCIENTOS", "TRESCIENTOS", "CUATROCIENTOS", "QUINIENTOS", "SEISCIENTOS", "SETECIENTOS",
             "OCHOCIENTOS", "NOVECIENTOS")
CURRENCY_NAMES = {"COP": ("PESO", "PESOS"), "VES": ("BOLÍVAR", "BOLÍVARES"), "USD": ("DÓLAR", "DÓLARES"),
                  "EUR": ("EURO", "EUROS")}


def _below_thousand(n: int) -> str:
    if n == 0:
        return ""
    if n == 100:
        return "CIEN"
    h, rest = divmod(n, 100)
    parts = [_HUNDREDS[h]] if h else []
    if rest < 30:
        parts.append(_UNITS[rest])
    else:
        t, u = divmod(rest, 10)
        parts.append(_TENS[t] + (f" Y {_UNITS[u]}" if u else ""))
    return " ".join(p for p in parts if p)


def integer_in_words(n: int) -> str:
    if n == 0:
        return "CERO"
    out = []
    for value, singular, plural in ((10 ** 12, "UN BILLÓN", "BILLONES"), (10 ** 6, "UN MILLÓN", "MILLONES"),
                                    (10 ** 3, "MIL", "MIL")):
        q, n = divmod(n, value)
        if q:
            if q == 1:
                out.append(singular)
            else:
                out.append(f"{integer_in_words(q)} {plural}")
    if n:
        out.append(_below_thousand(n))
    text = " ".join(out)
    # «uno» se apocopa ante el sustantivo: «veintiún mil», «treinta y un millones»
    return text.replace("VEINTIUNO MIL", "VEINTIÚN MIL").replace("UNO MIL", "UN MIL") \
        .replace("UNO MILLONES", "UN MILLONES").replace("VEINTIUNO MILLONES", "VEINTIÚN MILLONES")


def amount_in_words(amount: Decimal, currency: str) -> str:
    value = Decimal(amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    integer = int(abs(value))
    cents = int((abs(value) - integer) * 100)
    singular, plural = CURRENCY_NAMES.get(currency, (currency, currency))
    words = integer_in_words(integer)
    if words.endswith("VEINTIUNO"):
        words = words[:-9] + "VEINTIÚN"
    elif words.endswith("UNO"):
        words = words[:-3] + "UN"
    name = singular if integer == 1 else plural
    # «un millón de pesos»: con millones exactos se usa «de»
    of = " DE" if integer and integer % 1_000_000 == 0 else ""
    return f"{'MENOS ' if value < 0 else ''}{words}{of} {name} CON {cents:02d}/100"
