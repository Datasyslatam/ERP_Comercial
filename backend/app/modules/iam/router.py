from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.db import get_db
from app.core.deps import Principal, get_current_user, require
from app.core.errors import BusinessRuleViolation, NotFound
from app.modules.iam import service
from app.modules.iam.models import AuditLog, LoginAttempt, Role, User, UserCompanyRole
from app.modules.org.models import Company, CompanyModule

router = APIRouter(tags=["Autenticación y administración"])


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=200)


class RefreshIn(BaseModel):
    refresh_token: str = Field(min_length=20, max_length=200)


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int


@router.post("/auth/login", response_model=TokenOut)
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    return service.login(db, body.email, body.password, request.headers.get("user-agent"))


@router.post("/auth/refresh", response_model=TokenOut)
def refresh(body: RefreshIn, request: Request, db: Session = Depends(get_db)):
    return service.refresh(db, body.refresh_token, request.headers.get("user-agent"))


@router.post("/auth/logout", status_code=204)
def logout(body: RefreshIn, db: Session = Depends(get_db)):
    service.logout(db, body.refresh_token)


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=1, max_length=200)


@router.post("/auth/change-password", status_code=204)
def change_password(body: PasswordChangeIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    service.change_password(db, user, body.current_password, body.new_password)


@router.get("/auth/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Perfil, empresas accesibles, permisos efectivos y módulos activos por empresa."""
    if user.is_superadmin:
        companies = db.scalars(select(Company).where(Company.is_active.is_(True))).all()
    else:
        ids = {a.company_id for a in user.assignments}
        companies = db.scalars(select(Company).where(Company.id.in_(ids), Company.is_active.is_(True))).all()
    out = []
    from app.core.permissions import ALL_CODES

    for c in companies:
        perms = set(ALL_CODES) if user.is_superadmin else {
            p.code for a in user.assignments if a.company_id == c.id for p in a.role.permissions
        }
        disabled = set(db.scalars(select(CompanyModule.module_code).where(
            CompanyModule.company_id == c.id, CompanyModule.enabled.is_(False))).all())
        out.append({"id": c.id, "code": c.code, "name": c.trade_name or c.legal_name, "country": c.country_code,
                    "currency": c.functional_currency, "permissions": sorted(perms),
                    "disabled_modules": sorted(disabled)})
    return {"id": user.id, "email": user.email, "full_name": user.full_name, "is_superadmin": user.is_superadmin,
            "companies": out}


# ---------------------------------------------------------------- administración de usuarios
class UserCreateIn(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=200)
    password: str | None = Field(default=None, max_length=200)
    external_subject: str | None = Field(default=None, max_length=255)


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    is_active: bool
    is_superadmin: bool
    last_login_at: datetime | None
    roles: list[dict] = []


def _user_out(u: User, company_id: int) -> dict:
    return {"id": u.id, "email": u.email, "full_name": u.full_name, "is_active": u.is_active,
            "is_superadmin": u.is_superadmin, "last_login_at": u.last_login_at,
            "roles": [{"assignment_id": a.id, "role": a.role.code, "site_id": a.site_id}
                      for a in u.assignments if a.company_id == company_id]}


@router.get("/admin/users", response_model=list[UserOut])
def list_users(p: Principal = Depends(require("admin.users.read")), db: Session = Depends(get_db)):
    users = db.scalars(select(User).join(UserCompanyRole).where(UserCompanyRole.company_id == p.company_id)
                       .distinct().order_by(User.id)).all()
    return [_user_out(u, p.company_id) for u in users]


@router.post("/admin/users", response_model=UserOut, status_code=201)
def create_user(body: UserCreateIn, p: Principal = Depends(require("admin.users.create")),
                db: Session = Depends(get_db)):
    u = service.create_user(db, email=body.email, full_name=body.full_name, password=body.password,
                            external_subject=body.external_subject)
    db.commit()
    return _user_out(u, p.company_id)


class AssignIn(BaseModel):
    role_code: str
    site_id: int | None = None


@router.post("/admin/users/{user_id}/roles", response_model=UserOut)
def assign_role(user_id: int, body: AssignIn, p: Principal = Depends(require("admin.users.admin")),
                db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    role = db.scalar(select(Role).where(Role.code == body.role_code))
    if user is None or role is None:
        raise NotFound("Usuario o rol inexistente")
    if user.id == p.user_id and not p.user.is_superadmin:
        raise BusinessRuleViolation("Un usuario no puede asignarse roles a sí mismo")
    db.add(UserCompanyRole(user_id=user.id, company_id=p.company_id, role_id=role.id, site_id=body.site_id))
    log_action(db, "admin", "users", user.id, f"Asignación de rol {role.code}")
    db.commit()
    db.refresh(user)
    return _user_out(user, p.company_id)


@router.delete("/admin/users/{user_id}/roles/{assignment_id}", status_code=204)
def revoke_role(user_id: int, assignment_id: int, p: Principal = Depends(require("admin.users.admin")),
                db: Session = Depends(get_db)):
    a = db.get(UserCompanyRole, assignment_id)
    if a is None or a.user_id != user_id or a.company_id != p.company_id:
        raise NotFound("Asignación no encontrada")
    db.delete(a)
    log_action(db, "admin", "users", user_id, f"Revocación de rol {a.role.code}")
    db.commit()


class ActiveIn(BaseModel):
    is_active: bool


@router.patch("/admin/users/{user_id}", response_model=UserOut)
def set_active(user_id: int, body: ActiveIn, p: Principal = Depends(require("admin.users.admin")),
               db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None or not any(a.company_id == p.company_id for a in user.assignments):
        raise NotFound("Usuario no encontrado")
    if user.id == p.user_id:
        raise BusinessRuleViolation("No puede desactivarse a sí mismo")
    user.is_active = body.is_active
    db.commit()
    return _user_out(user, p.company_id)


@router.get("/admin/roles")
def list_roles(_: Principal = Depends(require("admin.roles.read")), db: Session = Depends(get_db)):
    return [{"code": r.code, "name": r.name, "permissions": sorted(p.code for p in r.permissions)}
            for r in db.scalars(select(Role).order_by(Role.code))]


@router.get("/admin/audit")
def audit_log(entity_type: str | None = None, entity_id: str | None = None, user_id: int | None = None,
              action: str | None = None, limit: int = Query(100, le=1000), offset: int = 0,
              p: Principal = Depends(require("admin.audit.read")), db: Session = Depends(get_db)):
    stmt = select(AuditLog).where(AuditLog.company_id == p.company_id)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(AuditLog.id.desc()).limit(limit).offset(offset)).all()
    return {"total": total, "items": [
        {"id": r.id, "at": r.occurred_at, "user_id": r.user_id, "ip": r.ip, "action": r.action,
         "entity_type": r.entity_type, "entity_id": r.entity_id, "summary": r.summary, "changes": r.changes}
        for r in rows]}


@router.get("/admin/login-attempts")
def login_attempts(limit: int = Query(100, le=1000), p: Principal = Depends(require("admin.audit.read")),
                   db: Session = Depends(get_db)):
    """Intentos de acceso de los usuarios de la empresa (los de usuarios inexistentes solo los ve el superadmin)."""
    stmt = select(LoginAttempt)
    if not p.user.is_superadmin:
        members = select(UserCompanyRole.user_id).where(UserCompanyRole.company_id == p.company_id)
        stmt = stmt.where(LoginAttempt.user_id.in_(members))
    rows = db.scalars(stmt.order_by(LoginAttempt.id.desc()).limit(limit)).all()
    return [{"at": r.created_at, "email": r.email, "ip": r.ip, "success": r.success, "reason": r.reason} for r in rows]
