"""Validación de identificaciones tributarias: NIT (Colombia, DIAN) y RIF (Venezuela, SENIAT)."""
import re

from app.core.errors import BusinessRuleViolation

_NIT_WEIGHTS = (3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71)
_RIF_LETTERS = {"V": 1, "E": 2, "J": 3, "P": 4, "G": 5, "C": 3}
_RIF_WEIGHTS = (3, 2, 7, 6, 5, 4, 3, 2)


def nit_check_digit(nit: str) -> str:
    digits = re.sub(r"\D", "", nit)
    if not digits or len(digits) > 15:
        raise BusinessRuleViolation("NIT inválido")
    total = sum(int(d) * w for d, w in zip(reversed(digits), _NIT_WEIGHTS, strict=False))
    r = total % 11
    return str(r if r in (0, 1) else 11 - r)


def rif_check_digit(rif_body: str) -> str:
    """rif_body: letra + 8 dígitos, p. ej. 'J00124134'."""
    m = re.fullmatch(r"([VEJPGC])(\d{8})", rif_body.upper())
    if not m:
        raise BusinessRuleViolation("RIF inválido: formato esperado letra + 8 dígitos")
    total = _RIF_LETTERS[m.group(1)] * 4 + sum(int(d) * w for d, w in zip(m.group(2), _RIF_WEIGHTS, strict=False))
    dv = 11 - (total % 11)
    return "0" if dv >= 10 else str(dv)


def validate_tax_id(id_type: str, tax_id: str, check_digit: str | None, country: str) -> None:
    id_type = (id_type or "").upper()
    if id_type == "NIT":
        if not re.fullmatch(r"\d{5,15}", tax_id or ""):
            raise BusinessRuleViolation("El NIT debe contener solo dígitos (sin dígito de verificación)")
        if check_digit is None:
            raise BusinessRuleViolation("El NIT exige dígito de verificación")
        expected = nit_check_digit(tax_id)
        if check_digit != expected:
            raise BusinessRuleViolation(f"Dígito de verificación del NIT incorrecto (esperado {expected})")
    elif id_type == "RIF":
        body = re.sub(r"[-\s]", "", tax_id or "").upper()
        if check_digit is None and len(body) == 10:
            body, check_digit = body[:9], body[9]
        expected = rif_check_digit(body)
        if check_digit != expected:
            raise BusinessRuleViolation(f"Dígito verificador del RIF incorrecto (esperado {expected})")
    elif id_type in ("CC", "CI", "CE"):
        if not re.fullmatch(r"\d{4,12}", tax_id or ""):
            raise BusinessRuleViolation("El documento de identidad debe contener solo dígitos")
    elif id_type not in ("PAS", "EXT"):
        raise BusinessRuleViolation(f"Tipo de identificación no soportado: {id_type}")
