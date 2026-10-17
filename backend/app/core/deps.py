"""Dependencias de FastAPI: autenticación, contexto de empresa y autorización por permiso."""
from dataclasses import dataclass, field

from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.context import update_context
from app.core.db import get_db
from app.core.errors import Forbidden, Unauthorized
from app.core.permissions import ALL_CODES
from app.core.security import decode_access_token, decode_oidc_token
from app.modules.iam.models import User, UserCompanyRole
from app.modules.org.models import Company, CompanyModule


@dataclass
class Principal:
    user: User
    company: Company
    permissions: set[str] = field(default_factory=set)
    role_ids: set[int] = field(default_factory=set)
    site_ids: set[int] | None = None  # None = todas las sedes

    @property
    def user_id(self) -> int:
        return self.user.id

    @property
    def company_id(self) -> int:
        return self.company.id

    def has(self, perm: str) -> bool:
        return perm in self.permissions

    def ensure_site(self, site_id: int | None) -> None:
        if site_id is not None and self.site_ids is not None and site_id not in self.site_ids:
            raise Forbidden("No tiene acceso a la sede indicada")


def _bearer(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "):
        raise Unauthorized("Credenciales no suministradas")
    return auth[7:].strip()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = _bearer(request)
    settings = get_settings()
    if settings.auth_mode == "oidc":
        claims = decode_oidc_token(token)
        user = db.scalar(select(User).where(User.external_subject == claims["sub"]))
    else:
        claims = decode_access_token(token)
        user = db.get(User, int(claims["sub"]))
    if user is None or not user.is_active:
        raise Unauthorized("Usuario inexistente o inactivo")
    update_context(user_id=user.id)
    return user


def get_principal(
    x_company_id: int = Header(..., alias="X-Company-Id", description="Empresa sobre la que se opera"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Principal:
    company = db.get(Company, x_company_id)
    if company is None or not company.is_active:
        raise Forbidden("Empresa inexistente o inactiva")
    if user.is_superadmin:
        update_context(company_id=company.id)
        return Principal(user=user, company=company, permissions=set(ALL_CODES))
    assignments = db.scalars(
        select(UserCompanyRole).where(UserCompanyRole.user_id == user.id, UserCompanyRole.company_id == company.id)
    ).all()
    if not assignments:
        raise Forbidden("No tiene acceso a esta empresa")
    perms: set[str] = set()
    sites: set[int] | None = set()
    for a in assignments:
        perms |= {p.code for p in a.role.permissions}
        if a.site_id is None:
            sites = None
        elif sites is not None:
            sites.add(a.site_id)
    update_context(company_id=company.id)
    return Principal(user=user, company=company, permissions=perms, role_ids={a.role_id for a in assignments},
                     site_ids=sites)


def require(*perms: str):
    """Exige todos los permisos indicados en la empresa activa."""
    unknown = set(perms) - ALL_CODES
    if unknown:
        raise RuntimeError(f"Permisos no registrados: {unknown}")

    def _dep(principal: Principal = Depends(get_principal)) -> Principal:
        missing = [p for p in perms if not principal.has(p)]
        if missing:
            raise Forbidden("Permiso insuficiente", details={"missing": missing})
        return principal

    return _dep


def require_module(module_code: str):
    """Bloquea endpoints de módulos desactivados para la empresa (p. ej. producción en comercializadoras)."""

    def _dep(principal: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> None:
        row = db.get(CompanyModule, (principal.company_id, module_code))
        if row is not None and not row.enabled:
            raise Forbidden(f"El módulo '{module_code}' no está activo para esta empresa")

    return _dep
