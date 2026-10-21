import csv
import io
from datetime import date, datetime, time

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.db import get_db
from app.core.deps import Principal, get_current_user, require
from app.core.permissions import ALL_CODES
from app.modules.iam import admin, service
from app.modules.iam.models import AuditLog, LoginAttempt, User, UserCompanyRole
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
    """Perfil, empresas accesibles, permisos efectivos (roles vigentes) y módulos activos por empresa."""
    today = date.today()
    current = [a for a in user.assignments if a.is_current(today)]
    if user.is_superadmin:
        companies = db.scalars(select(Company).where(Company.is_active.is_(True))).all()
    else:
        ids = {a.company_id for a in current}
        companies = db.scalars(select(Company).where(Company.id.in_(ids), Company.is_active.is_(True))).all()
    out = []
    for c in companies:
        perms = set(ALL_CODES) if user.is_superadmin else {
            p.code for a in current if a.company_id == c.id for p in a.role.permissions
        }
        disabled = set(db.scalars(select(CompanyModule.module_code).where(
            CompanyModule.company_id == c.id, CompanyModule.enabled.is_(False))).all())
        out.append({"id": c.id, "code": c.code, "name": c.trade_name or c.legal_name, "country": c.country_code,
                    "currency": c.functional_currency, "permissions": sorted(perms),
                    "disabled_modules": sorted(disabled)})
    return {"id": user.id, "email": user.email, "full_name": user.full_name, "job_title": user.job_title,
            "is_superadmin": user.is_superadmin, "must_change_password": user.must_change_password,
            "sso": user.external_subject is not None and not user.password_hash, "companies": out}


# ---------------------------------------------------------------- administración de usuarios
class RoleGrantIn(BaseModel):
    role_code: str = Field(min_length=1, max_length=60)
    site_id: int | None = None
    expires_on: date | None = None
    note: str | None = Field(default=None, max_length=255)


class UserCreateIn(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=200)
    job_title: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=40)
    password: str | None = Field(default=None, max_length=200)
    external_subject: str | None = Field(default=None, max_length=255)
    roles: list[RoleGrantIn] = Field(default_factory=list, max_length=20)


class UserPatchIn(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    job_title: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=40)
    is_active: bool | None = None


class ResetPasswordIn(BaseModel):
    new_password: str | None = Field(default=None, max_length=200)


def _reloaded(db: Session, user: User, company_id: int) -> dict:
    db.commit()
    db.refresh(user)
    return admin.user_out(db, user, company_id)


@router.get("/admin/permissions")
def permission_catalog(_: Principal = Depends(require("admin.roles.read"))):
    """Catálogo de permisos agrupado por módulo y recurso (matriz de roles)."""
    return admin.permission_catalog()


@router.get("/admin/users")
def list_users(q: str | None = Query(None, max_length=100),
               status: str | None = Query(None, pattern="^(active|inactive|locked)$"), role_id: int | None = None,
               p: Principal = Depends(require("admin.users.read")), db: Session = Depends(get_db)):
    return admin.list_users(db, p, q, status, role_id)


@router.post("/admin/users", status_code=201)
def create_user(body: UserCreateIn, p: Principal = Depends(require("admin.users.create", "admin.users.admin")),
                db: Session = Depends(get_db)):
    """Crea el usuario con sus roles. Si el correo ya existe en otra empresa del grupo, lo vincula a esta.

    Sin contraseña ni SSO se genera una contraseña temporal que se devuelve una sola vez."""
    user, extra = admin.create_or_link_user(
        db, p, email=body.email, full_name=body.full_name, job_title=body.job_title, phone=body.phone,
        password=body.password, external_subject=body.external_subject,
        roles=[r.model_dump() for r in body.roles])
    return {**_reloaded(db, user, p.company_id), **extra}


@router.get("/admin/users/{user_id}")
def user_detail(user_id: int, p: Principal = Depends(require("admin.users.read")), db: Session = Depends(get_db)):
    """Ficha del usuario: roles, permisos efectivos, sesiones, accesos, historial y actividad en la empresa."""
    return admin.user_detail(db, p, admin.member(db, p, user_id))


@router.patch("/admin/users/{user_id}")
def update_user(user_id: int, body: UserPatchIn, p: Principal = Depends(require("admin.users.admin")),
                db: Session = Depends(get_db)):
    user = admin.member(db, p, user_id)
    admin.update_user(db, p, user, body.model_dump(exclude_unset=True, exclude_none=True))
    return _reloaded(db, user, p.company_id)


@router.post("/admin/users/{user_id}/roles")
def assign_role(user_id: int, body: RoleGrantIn, p: Principal = Depends(require("admin.users.admin")),
                db: Session = Depends(get_db)):
    # Solo usuarios ya vinculados a la empresa; los de otras empresas del grupo se vinculan por correo al crear.
    user = admin.member(db, p, user_id)
    admin.assign_role(db, p, user, **body.model_dump())
    return _reloaded(db, user, p.company_id)


@router.delete("/admin/users/{user_id}/roles/{assignment_id}", status_code=204)
def revoke_role(user_id: int, assignment_id: int, p: Principal = Depends(require("admin.users.admin")),
                db: Session = Depends(get_db)):
    admin.revoke_role(db, p, user_id, assignment_id)
    db.commit()


@router.post("/admin/users/{user_id}/reset-password")
def reset_password(user_id: int, body: ResetPasswordIn, p: Principal = Depends(require("admin.users.admin")),
                   db: Session = Depends(get_db)):
    """Asigna una contraseña temporal (generada si no se indica), cierra sesiones y exige cambio al ingresar."""
    user = admin.member(db, p, user_id)
    temporary = admin.reset_password(db, p, user, body.new_password)
    db.commit()
    return {"temporary_password": temporary, "must_change_password": True}


@router.post("/admin/users/{user_id}/unlock")
def unlock(user_id: int, p: Principal = Depends(require("admin.users.admin")), db: Session = Depends(get_db)):
    user = admin.member(db, p, user_id)
    admin.unlock(db, p, user)
    return _reloaded(db, user, p.company_id)


@router.post("/admin/users/{user_id}/revoke-sessions")
def revoke_sessions(user_id: int, p: Principal = Depends(require("admin.users.admin")),
                    db: Session = Depends(get_db)):
    user = admin.member(db, p, user_id)
    n = admin.close_sessions(db, p, user)
    db.commit()
    return {"revoked": n}


@router.get("/admin/access-review")
def access_review(p: Principal = Depends(require("admin.users.read")), db: Session = Depends(get_db)):
    """Revisión de accesos: una fila por usuario y rol (insumo de la revisión periódica)."""
    return admin.access_review(db, p)


@router.get("/admin/access-review/export.csv")
def access_review_export(p: Principal = Depends(require("admin.users.read", "admin.audit.export")),
                         db: Session = Depends(get_db)):
    rows = admin.access_review(db, p)
    log_action(db, "export", "users", None, f"Exportación de la revisión de accesos ({len(rows)} filas)")
    db.commit()
    return _csv(rows, ["full_name", "email", "job_title", "status", "role", "role_name", "site", "expires_on",
                       "is_current", "granted_by", "granted_at", "last_login_at"], "revision-accesos.csv")


# ---------------------------------------------------------------- roles
class RoleIn(BaseModel):
    code: str = Field(min_length=2, max_length=60, pattern=r"^[a-zA-Z][a-zA-Z0-9_]*$")
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    permissions: list[str] = Field(default_factory=list, max_length=len(ALL_CODES))
    copy_from_role_id: int | None = None


class RolePatchIn(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    permissions: list[str] | None = Field(default=None, max_length=len(ALL_CODES))


@router.get("/admin/roles")
def list_roles(p: Principal = Depends(require("admin.roles.read")), db: Session = Depends(get_db)):
    """Roles del sistema y roles propios de la empresa, con permisos y usuarios vigentes."""
    return admin.list_roles(db, p.company_id)


@router.get("/admin/roles/{role_id}")
def role_detail(role_id: int, p: Principal = Depends(require("admin.roles.read")), db: Session = Depends(get_db)):
    role = admin.get_role(db, p.company_id, role_id=role_id)
    return admin.role_out(db, role, p.company_id, detail=True)


@router.post("/admin/roles", status_code=201)
def create_role(body: RoleIn, p: Principal = Depends(require("admin.roles.admin")), db: Session = Depends(get_db)):
    perms = body.permissions
    if body.copy_from_role_id and not perms:
        perms = [x.code for x in admin.get_role(db, p.company_id, role_id=body.copy_from_role_id).permissions]
    role = admin.create_role(db, p, code=body.code, name=body.name, description=body.description, permissions=perms)
    db.commit()
    return admin.role_out(db, role, p.company_id, detail=True)


@router.patch("/admin/roles/{role_id}")
def update_role(role_id: int, body: RolePatchIn, p: Principal = Depends(require("admin.roles.admin")),
                db: Session = Depends(get_db)):
    role = admin.editable_role(db, p, role_id)
    admin.update_role(db, p, role, body.model_dump(exclude_unset=True, exclude_none=True))
    db.commit()
    db.refresh(role)
    return admin.role_out(db, role, p.company_id, detail=True)


@router.delete("/admin/roles/{role_id}", status_code=204)
def delete_role(role_id: int, p: Principal = Depends(require("admin.roles.admin")), db: Session = Depends(get_db)):
    admin.delete_role(db, p, admin.editable_role(db, p, role_id))
    db.commit()


# ---------------------------------------------------------------- auditoría
def _csv_cell(v):
    if v is None:
        return ""
    return v.isoformat() if isinstance(v, date | datetime) else v


def _csv(rows: list[dict], cols: list[str], filename: str) -> StreamingResponse:
    buf = io.StringIO()
    buf.write("﻿")  # BOM: Excel abre el archivo en UTF-8 (tildes y eñes)
    w = csv.writer(buf)
    w.writerow(cols)
    for r in rows:
        w.writerow([_csv_cell(r.get(c)) for c in cols])
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})


class AuditFilter(BaseModel):
    entity_type: str | None = None
    entity_id: str | None = None
    user_id: int | None = None
    action: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    q: str | None = Field(None, max_length=100)


def _audit_rows(db: Session, p: Principal, f: AuditFilter, limit: int, offset: int) -> tuple[int, list[dict]]:
    stmt = select(AuditLog).where(AuditLog.company_id == p.company_id)
    for col in ("entity_type", "entity_id", "user_id", "action"):
        if getattr(f, col):
            stmt = stmt.where(getattr(AuditLog, col) == getattr(f, col))
    if f.date_from:
        stmt = stmt.where(AuditLog.occurred_at >= datetime.combine(f.date_from, time.min))
    if f.date_to:
        stmt = stmt.where(AuditLog.occurred_at <= datetime.combine(f.date_to, time.max))
    if f.q:
        stmt = stmt.where(func.lower(AuditLog.summary).like(f"%{f.q.lower()}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(AuditLog.id.desc()).limit(limit).offset(offset)).all()
    ids = {r.user_id for r in rows if r.user_id}
    names = dict(db.execute(select(User.id, User.full_name).where(User.id.in_(ids))).all()) if ids else {}
    return total, [
        {"id": r.id, "at": r.occurred_at, "user_id": r.user_id, "user_name": names.get(r.user_id), "ip": r.ip,
         "request_id": r.request_id, "action": r.action, "entity_type": r.entity_type, "entity_id": r.entity_id,
         "summary": r.summary, "changes": r.changes}
        for r in rows]


@router.get("/admin/audit")
def audit_log(f: AuditFilter = Depends(), limit: int = Query(100, le=1000), offset: int = 0,
              p: Principal = Depends(require("admin.audit.read")), db: Session = Depends(get_db)):
    total, items = _audit_rows(db, p, f, limit, offset)
    return {"total": total, "items": items}


@router.get("/admin/audit/export.csv")
def audit_export(f: AuditFilter = Depends(), p: Principal = Depends(require("admin.audit.read", "admin.audit.export")),
                 db: Session = Depends(get_db)):
    _, items = _audit_rows(db, p, f, 50000, 0)
    log_action(db, "export", "audit_log", None, f"Exportación de la bitácora ({len(items)} registros)")
    db.commit()
    return _csv(items, ["at", "user_name", "user_id", "ip", "action", "entity_type", "entity_id", "summary",
                        "request_id"], "auditoria.csv")


@router.get("/admin/login-attempts")
def login_attempts(limit: int = Query(100, le=1000), success: bool | None = None,
                   email: str | None = Query(None, max_length=254),
                   p: Principal = Depends(require("admin.audit.read")), db: Session = Depends(get_db)):
    """Intentos de acceso de los usuarios de la empresa (los de usuarios inexistentes solo los ve el superadmin)."""
    stmt = select(LoginAttempt)
    if not p.user.is_superadmin:
        members = select(UserCompanyRole.user_id).where(UserCompanyRole.company_id == p.company_id)
        stmt = stmt.where(LoginAttempt.user_id.in_(members))
    if success is not None:
        stmt = stmt.where(LoginAttempt.success.is_(success))
    if email:
        stmt = stmt.where(func.lower(LoginAttempt.email).like(f"%{email.lower()}%"))
    rows = db.scalars(stmt.order_by(LoginAttempt.id.desc()).limit(limit)).all()
    return [{"at": r.created_at, "email": r.email, "ip": r.ip, "success": r.success, "reason": r.reason} for r in rows]
