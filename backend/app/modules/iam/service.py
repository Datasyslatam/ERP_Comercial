"""Autenticación local, sesiones con refresh token rotativo y administración de usuarios."""
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.config import get_settings
from app.core.context import get_context
from app.core.errors import BusinessRuleViolation, Conflict, Unauthorized
from app.core.security import (
    create_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    validate_password_policy,
    verify_password,
)
from app.modules.iam.models import LoginAttempt, RefreshToken, User

_DUMMY_HASH = hash_password("timing-equalizer-not-a-real-password")


def _record_attempt(db: Session, email: str, user: User | None, success: bool, reason: str | None) -> None:
    db.add(LoginAttempt(email=email[:254], user_id=user.id if user else None, ip=get_context().ip, success=success,
                        reason=reason))


def _issue_tokens(db: Session, user: User, user_agent: str | None) -> dict:
    s = get_settings()
    raw, hashed = new_refresh_token()
    db.add(RefreshToken(user_id=user.id, token_hash=hashed, expires_at=datetime.now(UTC) + timedelta(days=s.refresh_token_days),
                        created_ip=get_context().ip, user_agent=(user_agent or "")[:255]))
    return {"access_token": create_access_token(user.id), "refresh_token": raw, "token_type": "bearer",
            "expires_in": s.access_token_minutes * 60}


def login(db: Session, email: str, password: str, user_agent: str | None = None) -> dict:
    s = get_settings()
    if s.auth_mode != "local":
        raise BusinessRuleViolation("El inicio de sesión local está deshabilitado (AUTH_MODE=oidc)")
    email_n = email.strip().lower()
    user = db.scalar(select(User).where(func.lower(User.email) == email_n).with_for_update())
    now = datetime.now(UTC)
    if user is None:
        verify_password(password, _DUMMY_HASH)  # iguala tiempos para no revelar existencia del usuario
        _record_attempt(db, email_n, None, False, "unknown_user")
        db.commit()
        raise Unauthorized("Credenciales inválidas")
    if user.locked_until and user.locked_until > now:
        _record_attempt(db, email_n, user, False, "locked")
        db.commit()
        raise Unauthorized("Usuario bloqueado temporalmente por intentos fallidos")
    if not user.is_active or not verify_password(password, user.password_hash):
        user.failed_login_count += 1
        reason = "inactive" if not user.is_active else "bad_password"
        if user.failed_login_count >= s.max_failed_logins:
            user.locked_until = now + timedelta(minutes=s.lockout_minutes)
            user.failed_login_count = 0
            reason = "locked_now"
            log_action(db, "lock", "users", user.id, "Bloqueo por intentos fallidos")
        _record_attempt(db, email_n, user, False, reason)
        db.commit()
        raise Unauthorized("Credenciales inválidas")
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    _record_attempt(db, email_n, user, True, None)
    tokens = _issue_tokens(db, user, user_agent)
    db.commit()
    return tokens


def refresh(db: Session, raw_token: str, user_agent: str | None = None) -> dict:
    hashed = hash_refresh_token(raw_token)
    rt = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hashed).with_for_update())
    now = datetime.now(UTC)
    if rt is None:
        raise Unauthorized("Sesión inválida")
    if rt.revoked_at is not None:
        # Reutilización de un token ya rotado: posible robo. Se revocan todas las sesiones del usuario.
        db.execute(update(RefreshToken).where(RefreshToken.user_id == rt.user_id, RefreshToken.revoked_at.is_(None))
                   .values(revoked_at=now))
        log_action(db, "security", "users", rt.user_id, "Reutilización de refresh token: sesiones revocadas")
        db.commit()
        raise Unauthorized("Sesión revocada")
    if rt.expires_at <= now:
        raise Unauthorized("Sesión expirada")
    user = db.get(User, rt.user_id)
    if user is None or not user.is_active:
        raise Unauthorized("Usuario inactivo")
    rt.revoked_at = now
    tokens = _issue_tokens(db, user, user_agent)
    db.commit()
    return tokens


def logout(db: Session, raw_token: str) -> None:
    rt = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_token)))
    if rt and rt.revoked_at is None:
        rt.revoked_at = datetime.now(UTC)
        db.commit()


def create_user(db: Session, *, email: str, full_name: str, password: str | None, is_superadmin: bool = False,
                external_subject: str | None = None) -> User:
    if db.scalar(select(User).where(func.lower(User.email) == email.lower())):
        raise Conflict("Ya existe un usuario con ese correo")
    if password is not None:
        validate_password_policy(password)
    elif external_subject is None:
        raise BusinessRuleViolation("Debe indicar contraseña o identificador OIDC")
    user = User(email=email.strip(), full_name=full_name, is_superadmin=is_superadmin,
                password_hash=hash_password(password) if password else None, external_subject=external_subject,
                password_changed_at=datetime.now(UTC) if password else None)
    db.add(user)
    db.flush()
    return user


def change_password(db: Session, user: User, current: str, new: str) -> None:
    if not verify_password(current, user.password_hash):
        raise Unauthorized("Contraseña actual incorrecta")
    if current == new:
        raise BusinessRuleViolation("La nueva contraseña debe ser distinta de la actual")
    validate_password_policy(new)
    user.password_hash = hash_password(new)
    user.password_changed_at = datetime.now(UTC)
    user.must_change_password = False
    db.execute(update(RefreshToken).where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
               .values(revoked_at=datetime.now(UTC)))
    log_action(db, "security", "users", user.id, "Cambio de contraseña")
    db.commit()
