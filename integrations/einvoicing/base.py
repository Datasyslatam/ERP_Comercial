"""Contrato común de los adaptadores de facturación electrónica.

El ERP entrega un `EDocument` neutro y recibe un `SubmissionResult`. Cada proveedor tecnológico (DIAN vía
proveedor autorizado, imprenta digital SENIAT) se implementa como un adaptador que cumple `EInvoiceAdapter`.
Los estados devueltos son siempre los del ERP: pending, sent, accepted, rejected, error. El adaptador traduce
los estados oficiales del proveedor a estos valores y conserva el código original en `provider_code`.
"""
from dataclasses import dataclass, field
from datetime import date, time
from decimal import Decimal
from typing import Protocol


@dataclass
class EParty:
    id_type: str
    tax_id: str
    check_digit: str | None
    legal_name: str
    email: str | None = None
    address: str | None = None
    city: str | None = None
    city_code: str | None = None
    country_code: str = "CO"
    fiscal_regime: str | None = None


@dataclass
class ETax:
    code: str  # código electrónico (01 IVA, 04 INC, IVA/EX en VE...)
    name: str
    rate: Decimal
    base: Decimal
    amount: Decimal


@dataclass
class ELine:
    line_no: int
    sku: str
    description: str
    quantity: Decimal
    uom_code: str
    unit_price: Decimal
    discount_amount: Decimal
    line_subtotal: Decimal
    tax: ETax | None


@dataclass
class EDocument:
    internal_id: int
    doc_type: str  # invoice, credit_note, debit_note
    prefix: str
    number: int
    issue_date: date
    issue_time: time
    due_date: date
    currency: str
    exchange_rate: Decimal
    functional_currency: str
    issuer: EParty
    customer: EParty
    lines: list[ELine]
    taxes: list[ETax]
    subtotal: Decimal
    discount_total: Decimal
    tax_total: Decimal
    total: Decimal
    payment_form: str
    authorization_number: str
    authorization_range: tuple[int, int] | None = None
    authorization_valid: tuple[date, date] | None = None
    technical_key: str | None = None
    reference_uid: str | None = None
    reference_number: str | None = None
    reference_date: date | None = None
    correction_code: str | None = None
    correction_reason: str | None = None
    notes: str | None = None

    @property
    def full_number(self) -> str:
        return f"{self.prefix}{self.number}"


@dataclass
class SubmissionResult:
    status: str  # sent, accepted, rejected, error
    environment: str  # sandbox / production
    legal_validity: bool
    provider_code: str | None = None
    message: str | None = None
    fiscal_uid: str | None = None
    control_number: str | None = None
    tracking_id: str | None = None
    document: bytes | None = None
    document_filename: str | None = None
    errors: list[str] = field(default_factory=list)
    retryable: bool = False


class EInvoiceAdapter(Protocol):
    name: str
    country: str
    environment: str

    def submit(self, doc: EDocument) -> SubmissionResult:
        """Construye, firma (si aplica) y envía el documento. Debe ser idempotente por (prefix, number)."""

    def status(self, doc: EDocument, tracking_id: str | None) -> SubmissionResult:
        """Consulta el estado de un documento enviado previamente."""


class TransientProviderError(Exception):
    """Fallo temporal (red, timeout, 5xx) que admite reintento."""
