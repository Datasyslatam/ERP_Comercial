"""Adaptadores de PRUEBAS (sandbox) — NO emiten documentos con validez fiscal.

Se usan mientras no se haya contratado/definido el proveedor tecnológico (DIAN) o la imprenta digital (SENIAT).
Ejecutan las validaciones previas reales, construyen el documento y calculan el identificador (CUFE con
ambiente de pruebas en Colombia), pero NO se comunican con ninguna autoridad tributaria. Todo resultado
queda marcado con environment='sandbox' y legal_validity=False, y el mensaje lo indica explícitamente.
"""
import hashlib

from integrations.einvoicing import dian, seniat
from integrations.einvoicing.base import EDocument, SubmissionResult

SANDBOX_NOTICE = ("SANDBOX: documento validado localmente por el adaptador de pruebas. "
                  "NO fue enviado a la autoridad tributaria y NO tiene validez fiscal.")


class SandboxDianAdapter:
    name = "sandbox_dian"
    country = "CO"
    environment = "sandbox"

    def __init__(self, software_pin: str = "SANDBOX-PIN") -> None:
        self.software_pin = software_pin

    def submit(self, doc: EDocument) -> SubmissionResult:
        errors = dian.validate(doc)
        if errors:
            return SubmissionResult(status="rejected", environment=self.environment, legal_validity=False,
                                    provider_code="SBX-REJ", message="; ".join(errors), errors=errors)
        key = doc.technical_key if doc.doc_type == "invoice" else self.software_pin
        uid = dian.compute_cufe(doc, environment_code="2", key=key)
        xml = dian.build_ubl(doc, uid, environment_code="2")
        return SubmissionResult(status="accepted", environment=self.environment, legal_validity=False,
                                provider_code="SBX-00", message=SANDBOX_NOTICE, fiscal_uid=uid,
                                tracking_id=f"sbx-{uid[:16]}", document=xml,
                                document_filename=f"{doc.full_number}.xml")

    def status(self, doc: EDocument, tracking_id: str | None) -> SubmissionResult:
        return self.submit(doc)


class SandboxSeniatAdapter:
    name = "sandbox_seniat"
    country = "VE"
    environment = "sandbox"

    def submit(self, doc: EDocument) -> SubmissionResult:
        errors = seniat.validate(doc)
        if errors:
            return SubmissionResult(status="rejected", environment=self.environment, legal_validity=False,
                                    provider_code="SBX-REJ", message="; ".join(errors), errors=errors)
        payload = seniat.build_payload(doc)
        # Número de control de PRUEBA, determinístico por documento (prefijo SBX para que nunca se confunda).
        control = f"SBX-{doc.prefix}-{doc.number:08d}"
        uid = hashlib.sha256(payload).hexdigest()
        return SubmissionResult(status="accepted", environment=self.environment, legal_validity=False,
                                provider_code="SBX-00", message=SANDBOX_NOTICE, fiscal_uid=uid,
                                control_number=control, tracking_id=f"sbx-{uid[:16]}", document=payload,
                                document_filename=f"{doc.full_number}.json")

    def status(self, doc: EDocument, tracking_id: str | None) -> SubmissionResult:
        return self.submit(doc)
