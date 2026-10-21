"""Administración de usuarios y roles por empresa con controles de seguridad y trazabilidad.

Reglas:
- Nadie otorga permisos que no tiene (al asignar un rol o al crear/editar un rol propio).
- La empresa nunca queda sin un administrador activo (permiso admin.users.admin vigente).
- Las acciones sobre la cuenta (correo, contraseña, activación) solo las hace un administrador de empresa si el
  usuario pertenece exclusivamente a su empresa; si tiene acceso a otras, solo el superadministrador.
- Toda acción administrativa queda en la bitácora sobre la entidad `users` o `roles`.
"""
import secrets
import string
from datetime import UTC, date, datetime

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.deps import Principal
from app.core.errors import BusinessRuleViolation, Conflict, Forbidden, NotFound
from app.core.permissions import _RESOURCES, ACTION_LABELS, ALL_CODES, MODULE_LABELS, RESOURCE_LABELS, ROLES
from app.core.security import hash_password, validate_password_policy
from app.modules.iam import service
from app.modules.iam.models import (
    ApprovalLimit,
    AuditLog,
    LoginAttempt,
    Permission,
    RefreshToken,
    Role,
    User,
    UserCompanyRole,
)
from app.modules.org.models import Site

ADMIN_PERMISSION = "admin.users.admin"


# ---------------------------------------------------------------- catálogo
def permission_catalog() -> list[dict]:
    """Permisos agrupados por módulo y recurso, con etiquetas en español para la matriz de roles."""
    return [{
        "module": module, "label": MODULE_LABELS[module],
        "resources": [{
            "resource": resource, "label": RESOURCE_LABELS.get(f"{module}.{resource}", resource),
            "actions": [{"code": f"{module}.{resource}.{a}", "action": a, "label": ACTION_LABELS[a]} for a in actions],
        } for resource, actions in resources.items()],
    } for module, resources in _RESOURCES.items()]


# ---------------------------------------------------------------- consultas base
def _today() -> date:
    return date.today()


def company_roles_stmt(company_id: int):
    return select(Role).where(or_(Role.company_id.is_(None), Role.company_id == company_id))


def get_role(db: Session, company_id: int, *, code: str | None = None, role_id: int | None = None) -> Role:
    stmt = company_roles_stmt(company_id)
    stmt = stmt.where(Role.code == code) if code is not None else stmt.where(Role.id == role_id)
    role = db.scalar(stmt)
    if role is None:
        raise NotFound("Rol inexistente")
    return role


def member(db: Session, p: Principal, user_id: int) -> User:
    """Usuario con al menos una asignación (vigente o vencida) en la empresa activa."""
    user = db.get(User, user_id)
    if user is None or not any(a.company_id == p.company_id for a in user.assignments):
        raise NotFound("Usuario no encontrado en esta empresa")
    return user


def other_companies(user: User, company_id: int) -> set[int]:
    return {a.company_id for a in user.assignments if a.company_id != company_id}


def ensure_account_control(p: Principal, user: User, action: str) -> None:
    """Acciones que afectan la cuenta en todas las empresas (correo, contraseña, activación)."""
    if p.user.is_superadmin:
        return
    if user.is_superadmin:
        raise Forbidden(f"Solo un superadministrador puede {action} de otro superadministrador")
    if other_companies(user, p.company_id):
        raise Forbidden(f"El usuario tiene acceso a otras empresas del grupo; solo el superadministrador puede "
                        f"{action}. Para quitarle el acceso a esta empresa revoque sus roles.")


def ensure_can_grant(p: Principal, codes: set[str]) -> None:
    missing = sorted(codes - p.permissions)
    if missing:
        raise Forbidden("No puede otorgar permisos que usted no tiene", details={"missing": missing})


def active_admins(db: Session, company_id: int) -> int:
    """Usuarios activos (no superadmin) con un rol vigente que permite administrar usuarios en la empresa."""
    today = _today()
    stmt = (select(func.count(func.distinct(User.id)))
            .select_from(UserCompanyRole)
            .join(User, User.id == UserCompanyRole.user_id)
            .join(Role, Role.id == UserCompanyRole.role_id)
            .join(Role.permissions)
            .where(UserCompanyRole.company_id == company_id, User.is_active.is_(True),
                   User.is_superadmin.is_(False), Permission.code == ADMIN_PERMISSION,
                   or_(UserCompanyRole.expires_on.is_(None), UserCompanyRole.expires_on >= today)))
    return db.scalar(stmt) or 0


class AdminGuard:
    """Verifica, después de aplicar un cambio, que la empresa conserve al menos un administrador."""

    def __init__(self, db: Session, company_id: int):
        self.db, self.company_id = db, company_id
        self.before = active_admins(db, company_id)

    def check(self) -> None:
        self.db.flush()
        if self.before > 0 and active_admins(self.db, self.company_id) == 0:
            raise BusinessRuleViolation("La empresa quedaría sin ningún administrador activo. Asigne primero el "
                                        "rol de administrador a otro usuario.")


def revoke_sessions(db: Session, user_id: int) -> int:
    res = db.execute(update(RefreshToken).where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
                     .values(revoked_at=datetime.now(UTC)))
    return res.rowcount or 0


def active_sessions(db: Session, user_id: int) -> list[RefreshToken]:
    return list(db.scalars(select(RefreshToken).where(
        RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None),
        RefreshToken.expires_at > datetime.now(UTC)).order_by(RefreshToken.id.desc())).all())


def temporary_password() -> str:
    """Contraseña aleatoria que cumple la política (se muestra una sola vez al administrador)."""
    alphabet = string.ascii_letters + string.digits
    while True:
        core = "".join(secrets.choice(alphabet) for _ in range(14))
        candidate = f"{core}{secrets.choice('!#$%&*+-?@')}{secrets.randbelow(10)}"
        try:
            validate_password_policy(candidate)
            return candidate
        except BusinessRuleViolation:
            continue


# ---------------------------------------------------------------- representación
def _is_locked(u: User) -> bool:
    return bool(u.locked_until and u.locked_until > datetime.now(UTC))


def status_of(u: User) -> str:
    return "inactive" if not u.is_active else "locked" if _is_locked(u) else "active"


def assignment_out(a: UserCompanyRole, sites: dict[int, str], names: dict[int, str]) -> dict:
    return {"assignment_id": a.id, "role_id": a.role_id, "role": a.role.code, "role_name": a.role.name,
            "site_id": a.site_id, "site_name": sites.get(a.site_id) if a.site_id else None,
            "expires_on": a.expires_on, "is_current": a.is_current(_today()), "granted_at": a.granted_at,
            "granted_by": names.get(a.granted_by_id) if a.granted_by_id else None, "note": a.note}


def _lookups(db: Session, company_id: int, users: list[User]) -> tuple[dict[int, str], dict[int, str]]:
    sites = dict(db.execute(select(Site.id, Site.name).where(Site.company_id == company_id)).all())
    grantors = {a.granted_by_id for u in users for a in u.assignments if a.granted_by_id}
    names = dict(db.execute(select(User.id, User.full_name).where(User.id.in_(grantors))).all()) if grantors else {}
    return sites, names


def user_out(db: Session, u: User, company_id: int, lookups=None) -> dict:
    sites, names = lookups or _lookups(db, company_id, [u])
    return {"id": u.id, "email": u.email, "full_name": u.full_name, "job_title": u.job_title, "phone": u.phone,
            "is_active": u.is_active, "is_superadmin": u.is_superadmin, "status": status_of(u),
            "locked_until": u.locked_until if _is_locked(u) else None, "last_login_at": u.last_login_at,
            "must_change_password": u.must_change_password, "password_changed_at": u.password_changed_at,
            "sso": u.external_subject is not None, "created_at": u.created_at,
            "other_companies": len(other_companies(u, company_id)),
            "roles": [assignment_out(a, sites, names) for a in u.assignments if a.company_id == company_id]}


def list_users(db: Session, p: Principal, q: str | None, status: str | None, role_id: int | None) -> list[dict]:
    stmt = select(User).join(UserCompanyRole, UserCompanyRole.user_id == User.id).where(
        UserCompanyRole.company_id == p.company_id)
    if role_id:
        stmt = stmt.where(UserCompanyRole.role_id == role_id)
    if q:
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(or_(func.lower(User.full_name).like(like), func.lower(User.email).like(like),
                              func.lower(User.job_title).like(like)))
    users = db.scalars(stmt.distinct().order_by(User.full_name)).all()
    if status:
        users = [u for u in users if status_of(u) == status]
    lookups = _lookups(db, p.company_id, users)
    return [user_out(db, u, p.company_id, lookups) for u in users]


def effective_permissions(user: User, company_id: int) -> list[dict]:
    """Permisos vigentes del usuario en la empresa con los roles que los otorgan."""
    if user.is_superadmin:
        return [{"code": c, "roles": ["superadministrador"]} for c in sorted(ALL_CODES)]
    sources: dict[str, list[str]] = {}
    for a in user.assignments:
        if a.company_id == company_id and a.is_current(_today()):
            for perm in a.role.permissions:
                sources.setdefault(perm.code, []).append(a.role.name)
    return [{"code": c, "roles": sorted(set(r))} for c, r in sorted(sources.items())]


def user_detail(db: Session, p: Principal, user: User) -> dict:
    out = user_out(db, user, p.company_id)
    out["permissions"] = effective_permissions(user, p.company_id)
    out["sessions"] = [{"id": s.id, "created_at": s.created_at, "expires_at": s.expires_at, "ip": s.created_ip,
                        "user_agent": s.user_agent} for s in active_sessions(db, user.id)]
    out["login_attempts"] = [
        {"at": r.created_at, "ip": r.ip, "success": r.success, "reason": r.reason}
        for r in db.scalars(select(LoginAttempt).where(LoginAttempt.user_id == user.id)
                            .order_by(LoginAttempt.id.desc()).limit(20))]
    out["history"] = [
        {"at": r.occurred_at, "action": r.action, "summary": r.summary, "by": r.user_id, "changes": r.changes}
        for r in db.scalars(select(AuditLog).where(AuditLog.company_id == p.company_id,
                                                   AuditLog.entity_type == "users",
                                                   AuditLog.entity_id == str(user.id))
                            .order_by(AuditLog.id.desc()).limit(50))]
    out["activity"] = [
        {"at": r.occurred_at, "action": r.action, "entity_type": r.entity_type, "entity_id": r.entity_id,
         "summary": r.summary}
        for r in db.scalars(select(AuditLog).where(AuditLog.company_id == p.company_id, AuditLog.user_id == user.id)
                            .order_by(AuditLog.id.desc()).limit(50))]
    authors = {h["by"] for h in out["history"] if h["by"]}
    names = dict(db.execute(select(User.id, User.full_name).where(User.id.in_(authors))).all()) if authors else {}
    for h in out["history"]:
        h["by_name"] = names.get(h["by"])
    return out


# ---------------------------------------------------------------- usuarios
def assign_role(db: Session, p: Principal, user: User, *, role_code: str, site_id: int | None = None,
                expires_on: date | None = None, note: str | None = None) -> UserCompanyRole:
    role = get_role(db, p.company_id, code=role_code)
    if user.id == p.user_id and not p.user.is_superadmin:
        raise BusinessRuleViolation("Un usuario no puede asignarse roles a sí mismo")
    if not user.is_active:
        raise BusinessRuleViolation("El usuario está inactivo; actívelo antes de asignarle roles")
    ensure_can_grant(p, {perm.code for perm in role.permissions})
    if site_id is not None:
        site = db.get(Site, site_id)
        if site is None or site.company_id != p.company_id:
            raise BusinessRuleViolation("La sede no pertenece a esta empresa")
    if expires_on is not None and expires_on < _today():
        raise BusinessRuleViolation("La fecha de vencimiento no puede estar en el pasado")
    dup = db.scalar(select(UserCompanyRole).where(
        UserCompanyRole.user_id == user.id, UserCompanyRole.company_id == p.company_id,
        UserCompanyRole.role_id == role.id,
        UserCompanyRole.site_id.is_(None) if site_id is None else UserCompanyRole.site_id == site_id))
    if dup is not None:
        if dup.is_current(_today()):
            raise Conflict("El usuario ya tiene ese rol en esa sede")
        # Reasignar un rol vencido renueva la vigencia en lugar de duplicar la asignación.
        dup.expires_on, dup.granted_by_id, dup.granted_at, dup.note = expires_on, p.user_id, datetime.now(UTC), note
        a = dup
    else:
        a = UserCompanyRole(user_id=user.id, company_id=p.company_id, role_id=role.id, site_id=site_id,
                            expires_on=expires_on, granted_by_id=p.user_id, note=note)
        db.add(a)
    scope = f" en sede {site_id}" if site_id else ""
    until = f" hasta {expires_on.isoformat()}" if expires_on else ""
    log_action(db, "grant", "users", user.id, f"Asignación de rol {role.code}{scope}{until}",
               {"role": role.code, "site_id": site_id, "expires_on": expires_on.isoformat() if expires_on else None})
    return a


def revoke_role(db: Session, p: Principal, user_id: int, assignment_id: int) -> None:
    a = db.get(UserCompanyRole, assignment_id)
    if a is None or a.user_id != user_id or a.company_id != p.company_id:
        raise NotFound("Asignación no encontrada")
    if user_id == p.user_id and not p.user.is_superadmin:
        raise BusinessRuleViolation("No puede revocar sus propios roles")
    guard = AdminGuard(db, p.company_id)
    code = a.role.code
    db.delete(a)
    guard.check()
    log_action(db, "revoke", "users", user_id, f"Revocación de rol {code}", {"role": code, "site_id": a.site_id})


def create_or_link_user(db: Session, p: Principal, *, email: str, full_name: str, job_title: str | None,
                        phone: str | None, password: str | None, external_subject: str | None,
                        roles: list[dict]) -> tuple[User, dict]:
    """Crea el usuario y le asigna sus roles; si el correo ya existe en el grupo lo vincula a esta empresa."""
    if not roles:
        raise BusinessRuleViolation("Asigne al menos un rol: un usuario sin rol no puede ingresar a la empresa")
    existing = db.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))
    extra: dict = {"linked_existing": False, "temporary_password": None}
    if existing is not None:
        if any(a.company_id == p.company_id for a in existing.assignments):
            raise Conflict("El usuario ya pertenece a esta empresa; edite sus roles desde su ficha")
        if existing.is_superadmin or not existing.is_active:
            raise Conflict("Ya existe una cuenta con ese correo que no puede vincularse; contacte al superadministrador")
        user = existing
        extra["linked_existing"] = True
        log_action(db, "link", "users", user.id, "Vinculación de usuario existente a la empresa")
    else:
        if password is None and external_subject is None:
            password = temporary_password()
            extra["temporary_password"] = password
        user = service.create_user(db, email=email, full_name=full_name, password=password,
                                   external_subject=external_subject)
        user.job_title, user.phone = job_title, phone
        # Quien recibe una contraseña asignada por otra persona debe cambiarla en su primer ingreso.
        user.must_change_password = password is not None
        log_action(db, "create", "users", user.id, f"Alta de usuario {user.email}")
    for r in roles:
        assign_role(db, p, user, role_code=r["role_code"], site_id=r.get("site_id"), expires_on=r.get("expires_on"),
                    note=r.get("note"))
    return user, extra


def update_user(db: Session, p: Principal, user: User, data: dict) -> None:
    changes = {}
    if "email" in data and data["email"].strip().lower() != user.email.lower():
        ensure_account_control(p, user, "cambiar el correo")
        if db.scalar(select(User).where(func.lower(User.email) == data["email"].strip().lower(), User.id != user.id)):
            raise Conflict("Ya existe un usuario con ese correo")
        changes["email"] = [user.email, data["email"].strip()]
        user.email = data["email"].strip()
    for key in ("full_name", "job_title", "phone"):
        if key in data and data[key] != getattr(user, key):
            changes[key] = [getattr(user, key), data[key]]
            setattr(user, key, data[key])
    if "is_active" in data and data["is_active"] != user.is_active:
        if user.id == p.user_id:
            raise BusinessRuleViolation("No puede desactivarse a sí mismo")
        ensure_account_control(p, user, "activar o desactivar la cuenta")
        guard = AdminGuard(db, p.company_id)
        user.is_active = data["is_active"]
        guard.check()
        changes["is_active"] = [not user.is_active, user.is_active]
        if not user.is_active:
            revoke_sessions(db, user.id)
        log_action(db, "activate" if user.is_active else "deactivate", "users", user.id,
                   "Activación de la cuenta" if user.is_active else "Desactivación de la cuenta y cierre de sesiones")
    if changes:
        log_action(db, "update", "users", user.id, "Actualización de datos: " + ", ".join(changes), changes)


def reset_password(db: Session, p: Principal, user: User, new_password: str | None) -> str | None:
    """Fija una contraseña temporal (generada si no se indica) que el usuario debe cambiar al ingresar."""
    if user.id == p.user_id:
        raise BusinessRuleViolation("Use «Cambiar contraseña» para su propia cuenta")
    if user.external_subject and not user.password_hash:
        raise BusinessRuleViolation("El usuario ingresa con el inicio de sesión corporativo (SSO)")
    ensure_account_control(p, user, "restablecer la contraseña")
    generated = new_password is None
    password = new_password or temporary_password()
    validate_password_policy(password)
    user.password_hash = hash_password(password)
    user.password_changed_at = datetime.now(UTC)
    user.must_change_password = True
    user.failed_login_count, user.locked_until = 0, None
    revoke_sessions(db, user.id)
    log_action(db, "security", "users", user.id, "Restablecimiento de contraseña por el administrador")
    return password if generated else None


def unlock(db: Session, p: Principal, user: User) -> None:
    if user.is_superadmin and not p.user.is_superadmin:
        raise Forbidden("Solo un superadministrador puede desbloquear a otro superadministrador")
    user.failed_login_count, user.locked_until = 0, None
    log_action(db, "security", "users", user.id, "Desbloqueo de la cuenta")


def close_sessions(db: Session, p: Principal, user: User) -> int:
    if user.is_superadmin and not p.user.is_superadmin:
        raise Forbidden("Solo un superadministrador puede cerrar las sesiones de otro superadministrador")
    n = revoke_sessions(db, user.id)
    log_action(db, "security", "users", user.id, f"Cierre forzado de {n} sesión(es)")
    return n


# ---------------------------------------------------------------- roles
def role_out(db: Session, role: Role, company_id: int, detail: bool = False) -> dict:
    today = _today()
    rows = db.scalars(select(UserCompanyRole).where(UserCompanyRole.company_id == company_id,
                                                    UserCompanyRole.role_id == role.id)).all()
    out = {"id": role.id, "code": role.code, "name": role.name, "description": role.description,
           "is_system": role.company_id is None, "editable": role.company_id is not None,
           "permissions": sorted(perm.code for perm in role.permissions),
           "users_count": len({a.user_id for a in rows if a.is_current(today)}),
           "created_at": role.created_at, "updated_at": role.updated_at}
    if detail:
        users = {u.id: u for u in db.scalars(select(User).where(User.id.in_({a.user_id for a in rows})))}
        out["users"] = [{"user_id": a.user_id, "full_name": users[a.user_id].full_name, "email": users[a.user_id].email,
                         "is_active": users[a.user_id].is_active, "site_id": a.site_id, "expires_on": a.expires_on,
                         "is_current": a.is_current(today)} for a in rows]
        out["approval_limits"] = [
            {"document_type": lim.document_type, "max_amount": lim.max_amount}
            for lim in db.scalars(select(ApprovalLimit).where(ApprovalLimit.company_id == company_id,
                                                              ApprovalLimit.role_id == role.id))]
        out["history"] = [
            {"at": r.occurred_at, "action": r.action, "summary": r.summary, "by": r.user_id, "changes": r.changes}
            for r in db.scalars(select(AuditLog).where(AuditLog.company_id == company_id,
                                                       AuditLog.entity_type == "roles",
                                                       AuditLog.entity_id == str(role.id))
                                .order_by(AuditLog.id.desc()).limit(50))]
    return out


def list_roles(db: Session, company_id: int) -> list[dict]:
    roles = db.scalars(company_roles_stmt(company_id).order_by(Role.company_id.is_(None).desc(), Role.name)).all()
    return [role_out(db, r, company_id) for r in roles]


def _permissions(db: Session, codes: list[str]) -> list[Permission]:
    unknown = set(codes) - ALL_CODES
    if unknown:
        raise BusinessRuleViolation("Permisos inexistentes", details={"unknown": sorted(unknown)})
    return list(db.scalars(select(Permission).where(Permission.code.in_(codes))).all())


def create_role(db: Session, p: Principal, *, code: str, name: str, description: str | None,
                permissions: list[str]) -> Role:
    code = code.strip().lower()
    if code in ROLES or db.scalar(company_roles_stmt(p.company_id).where(Role.code == code)):
        raise Conflict("Ya existe un rol con ese código")
    perms = _permissions(db, permissions)
    ensure_can_grant(p, set(permissions))
    role = Role(code=code, name=name, description=description, is_system=False, company_id=p.company_id,
                permissions=perms)
    db.add(role)
    db.flush()
    log_action(db, "create", "roles", role.id, f"Creación del rol {code} con {len(permissions)} permisos",
               {"permissions": sorted(permissions)})
    return role


def editable_role(db: Session, p: Principal, role_id: int) -> Role:
    role = get_role(db, p.company_id, role_id=role_id)
    if role.company_id is None:
        raise BusinessRuleViolation("Los roles del sistema no se modifican; duplíquelo para crear uno propio")
    return role


def update_role(db: Session, p: Principal, role: Role, data: dict) -> None:
    for key in ("name", "description"):
        if key in data:
            setattr(role, key, data[key])
    if "permissions" in data:
        new = set(data["permissions"])
        old = {perm.code for perm in role.permissions}
        # Solo se exige poseer los permisos que se agregan; quitar permisos siempre está permitido.
        perms = _permissions(db, sorted(new))
        ensure_can_grant(p, new - old)
        guard = AdminGuard(db, p.company_id)
        role.permissions = perms
        guard.check()
        added, removed = sorted(new - old), sorted(old - new)
        if added or removed:
            log_action(db, "permissions", "roles", role.id,
                       f"Permisos del rol {role.code}: +{len(added)} / -{len(removed)}",
                       {"added": added, "removed": removed})


def delete_role(db: Session, p: Principal, role: Role) -> None:
    if db.scalar(select(func.count()).select_from(UserCompanyRole).where(UserCompanyRole.role_id == role.id)):
        raise BusinessRuleViolation("El rol tiene usuarios asignados; revóquelos antes de eliminarlo")
    for lim in db.scalars(select(ApprovalLimit).where(ApprovalLimit.role_id == role.id)):
        db.delete(lim)
    log_action(db, "delete", "roles", role.id, f"Eliminación del rol {role.code}",
               {"permissions": sorted(perm.code for perm in role.permissions)})
    db.delete(role)


# ---------------------------------------------------------------- revisión de accesos
def access_review(db: Session, p: Principal) -> list[dict]:
    """Una fila por asignación: insumo de la revisión periódica de usuarios y roles."""
    rows = []
    for u in list_users(db, p, None, None, None):
        for r in u["roles"]:
            rows.append({"user_id": u["id"], "full_name": u["full_name"], "email": u["email"],
                         "job_title": u["job_title"], "status": u["status"], "last_login_at": u["last_login_at"],
                         "role": r["role"], "role_name": r["role_name"], "site": r["site_name"] or "Todas",
                         "expires_on": r["expires_on"], "is_current": r["is_current"],
                         "granted_by": r["granted_by"], "granted_at": r["granted_at"]})
    return rows
