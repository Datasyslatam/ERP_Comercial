"""Políticas de control interno: segregación de funciones y límites de aprobación."""
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import Principal
from app.core.errors import Forbidden
from app.modules.iam.models import ApprovalLimit


def enforce_sod(principal: Principal, policy_key: str, creator_id: int | None, action: str) -> None:
    """Impide que quien creó un documento lo apruebe/contabilice, salvo que la empresa lo permita."""
    if creator_id is None or creator_id != principal.user_id:
        return
    if principal.company.setting(policy_key):
        return
    raise Forbidden(f"Segregación de funciones: no puede {action} un documento que usted mismo creó")


def enforce_approval_limit(db: Session, principal: Principal, document_type: str, amount: Decimal) -> None:
    limits = db.scalars(select(ApprovalLimit).where(ApprovalLimit.company_id == principal.company_id,
                                                    ApprovalLimit.document_type == document_type)).all()
    if not limits or principal.user.is_superadmin:
        return  # sin política configurada para este tipo de documento
    mine = [lim.max_amount for lim in limits if lim.role_id in principal.role_ids]
    if not mine:
        raise Forbidden(f"Su rol no tiene atribución de aprobación para {document_type}")
    if amount > max(mine):
        raise Forbidden(f"El monto {amount} excede su límite de aprobación ({max(mine)})",
                        details={"limit": str(max(mine)), "amount": str(amount)})
