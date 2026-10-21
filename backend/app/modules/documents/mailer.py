"""Envío de correo: SMTP en staging/producción; en desarrollo y pruebas, archivo .eml en el almacenamiento.

El backend `file` escribe el mensaje completo (con adjuntos) en STORAGE_PATH/mail para revisarlo sin enviar
nada a destinatarios reales.
"""
import smtplib
import ssl
import uuid
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from pathlib import Path

from app.core.config import get_settings
from app.core.errors import BusinessRuleViolation


def ensure_configured() -> None:
    s = get_settings()
    if s.email_backend == "smtp":
        if not (s.smtp_host and s.mail_from):
            raise BusinessRuleViolation("El correo no está configurado: defina SMTP_HOST y MAIL_FROM")
    elif s.environment in ("staging", "production"):
        raise BusinessRuleViolation("El envío de correo no está configurado en este ambiente (EMAIL_BACKEND=smtp)")


def build(*, sender_name: str, to: list[str], cc: list[str], reply_to: str | None, subject: str, body: str,
          attachments: list[tuple[str, str, bytes]]) -> EmailMessage:
    s = get_settings()
    msg = EmailMessage()
    msg["From"] = formataddr((sender_name, s.mail_from or "erp@localhost"))
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    if reply_to:
        msg["Reply-To"] = reply_to
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain=(s.mail_from.split("@")[-1] if "@" in s.mail_from else "erp.local"))
    msg.set_content(body)
    for filename, content_type, data in attachments:
        maintype, subtype = content_type.split("/", 1)
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)
    return msg


def send(msg: EmailMessage, company_id: int) -> str:
    """Entrega el mensaje y devuelve su Message-ID."""
    s = get_settings()
    if s.email_backend == "file":
        folder = Path(s.storage_path).resolve() / "mail" / str(company_id)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{uuid.uuid4().hex}.eml").write_bytes(bytes(msg))
        return msg["Message-ID"]
    ensure_configured()
    if s.smtp_ssl:
        server = smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, timeout=30, context=ssl.create_default_context())
    else:
        server = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=30)
    with server:
        if not s.smtp_ssl and s.smtp_starttls:
            server.starttls(context=ssl.create_default_context())
        if s.smtp_user:
            server.login(s.smtp_user, s.smtp_password)
        server.send_message(msg)
    return msg["Message-ID"]
