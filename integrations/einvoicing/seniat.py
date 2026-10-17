"""Venezuela (SENIAT): validaciones y documento para imprenta digital autorizada.

En Venezuela los documentos fiscales digitales se emiten a través de una imprenta digital autorizada por el
SENIAT, que asigna el número de control. El formato de intercambio depende de cada imprenta (JSON/XML propio),
por lo que aquí se construye una representación neutra en JSON con los datos fiscales exigibles: RIF de
emisor y receptor, número de documento, montos en bolívares y, cuando la operación es en divisas, la
equivalencia con la tasa oficial del BCV. El adaptador real de la imprenta debe transformar esta estructura.
"""
import json
from decimal import Decimal

from integrations.einvoicing.base import EDocument

DOC_TYPES = {"invoice": "01", "debit_note": "02", "credit_note": "03"}


def _ves(v: Decimal, rate: Decimal) -> str:
    return f"{(Decimal(v) * Decimal(rate)).quantize(Decimal('0.01'))}"


def validate(doc: EDocument) -> list[str]:
    errors = []
    if doc.issuer.id_type != "RIF":
        errors.append("El emisor debe identificarse con RIF")
    if doc.customer.id_type not in ("RIF", "CI", "PAS", "EXT"):
        errors.append(f"Tipo de identificación del receptor no soportado: {doc.customer.id_type}")
    if not doc.customer.legal_name or not doc.customer.address:
        errors.append("El receptor requiere razón social y domicilio fiscal")
    if doc.functional_currency != "VES":
        errors.append("La moneda funcional de una empresa venezolana debe ser VES")
    if doc.currency != "VES" and (not doc.exchange_rate or doc.exchange_rate <= 0):
        errors.append("Operación en divisas sin tasa de cambio oficial")
    if doc.doc_type != "invoice" and not doc.reference_number:
        errors.append("Las notas deben indicar la factura afectada")
    if not doc.lines:
        errors.append("El documento no tiene líneas")
    if sum((ln.line_subtotal for ln in doc.lines), Decimal("0")) != doc.subtotal:
        errors.append("La suma de líneas no coincide con el subtotal")
    if doc.subtotal + doc.tax_total != doc.total:
        errors.append("Los totales del documento no son consistentes")
    return errors


def build_payload(doc: EDocument) -> bytes:
    rate = doc.exchange_rate if doc.currency != "VES" else Decimal("1")
    payload = {
        "tipo_documento": DOC_TYPES[doc.doc_type],
        "serie": doc.prefix,
        "numero_documento": doc.number,
        "fecha_emision": doc.issue_date.isoformat(),
        "hora_emision": doc.issue_time.strftime("%H:%M:%S"),
        "emisor": {"rif": f"{doc.issuer.tax_id}{doc.issuer.check_digit or ''}", "razon_social": doc.issuer.legal_name,
                   "domicilio": doc.issuer.address},
        "receptor": {"tipo_id": doc.customer.id_type,
                     "id": f"{doc.customer.tax_id}{doc.customer.check_digit or ''}",
                     "razon_social": doc.customer.legal_name, "domicilio": doc.customer.address,
                     "correo": doc.customer.email},
        "moneda_operacion": doc.currency,
        "tasa_bcv": str(rate),
        "items": [{"linea": ln.line_no, "codigo": ln.sku, "descripcion": ln.description,
                   "cantidad": str(ln.quantity), "unidad": ln.uom_code, "precio_unitario": str(ln.unit_price),
                   "descuento": str(ln.discount_amount), "base": str(ln.line_subtotal),
                   "base_bs": _ves(ln.line_subtotal, rate),
                   "alicuota": str(ln.tax.rate) if ln.tax else "0", "exento": not ln.tax or ln.tax.rate == 0}
                  for ln in doc.lines],
        "impuestos": [{"codigo": t.code, "alicuota": str(t.rate), "base_bs": _ves(t.base, rate),
                       "monto_bs": _ves(t.amount, rate)} for t in doc.taxes],
        "totales": {"subtotal": str(doc.subtotal), "impuestos": str(doc.tax_total), "total": str(doc.total),
                    "subtotal_bs": _ves(doc.subtotal, rate), "impuestos_bs": _ves(doc.tax_total, rate),
                    "total_bs": _ves(doc.total, rate)},
        "documento_afectado": {"numero": doc.reference_number, "fecha": doc.reference_date.isoformat()
                               if doc.reference_date else None} if doc.doc_type != "invoice" else None,
        "condicion_pago": "contado" if doc.payment_form == "cash" else "credito",
        "fecha_vencimiento": doc.due_date.isoformat(),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
