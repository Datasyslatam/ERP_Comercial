"""Hash de contraseñas (Argon2id), tokens JWT de acceso y tokens de refresco opacos y revocables."""
import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import get_settings
from app.core.errors import BusinessRuleViolation, Unauthorized

_s = get_settings()
_hasher = PasswordHasher(time_cost=_s.argon2_time_cost, memory_cost=_s.argon2_memory_kib, parallelism=_s.argon2_parallelism)


def hash_password(raw: str) -> str:
    return _hasher.hash(raw)


def verify_password(raw: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    try:
        return _hasher.verify(hashed, raw)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def validate_password_policy(raw: str) -> None:
    s = get_settings()
    problems = []
    if len(raw) < s.password_min_length:
        problems.append(f"mínimo {s.password_min_length} caracteres")
    if not re.search(r"[A-Z]", raw) or not re.search(r"[a-z]", raw):
        problems.append("mayúsculas y minúsculas")
    if not re.search(r"\d", raw):
        problems.append("al menos un número")
    if not re.search(r"[^A-Za-z0-9]", raw):
        problems.append("al menos un símbolo")
    if problems:
        raise BusinessRuleViolation("La contraseña no cumple la política: " + ", ".join(problems))


def create_access_token(user_id: int, extra: dict | None = None) -> str:
    s = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=s.access_token_minutes)).timestamp()),
        "typ": "access",
        "iss": s.app_name,
        **(extra or {}),
    }
    return jwt.encode(payload, s.effective_jwt_secret, algorithm=s.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    s = get_settings()
    try:
        payload = jwt.decode(token, s.effective_jwt_secret, algorithms=[s.jwt_algorithm], issuer=s.app_name)
    except jwt.PyJWTError as exc:
        raise Unauthorized("Token inválido o expirado") from exc
    if payload.get("typ") != "access":
        raise Unauthorized("Tipo de token inválido")
    return payload


_jwks_client = None


def decode_oidc_token(token: str) -> dict:
    """Valida un token emitido por el proveedor OIDC corporativo (Keycloak, Entra ID, Auth0...)."""
    global _jwks_client
    s = get_settings()
    if _jwks_client is None:
        _jwks_client = jwt.PyJWKClient(s.oidc_jwks_url)
    try:
        key = _jwks_client.get_signing_key_from_jwt(token)
        return jwt.decode(token, key.key, algorithms=["RS256", "ES256"], audience=s.oidc_audience,
                          issuer=s.oidc_issuer)
    except jwt.PyJWTError as exc:
        raise Unauthorized("Token OIDC inválido") from exc


def new_refresh_token() -> tuple[str, str]:
    """Devuelve (token en claro para el cliente, hash a persistir)."""
    raw = secrets.token_urlsafe(48)
    return raw, hash_refresh_token(raw)


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
