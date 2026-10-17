"""Almacenamiento de archivos adjuntos en disco (volumen persistente) con integridad SHA-256."""
import hashlib
import os
import re
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import BusinessRuleViolation, NotFound
from app.modules.org.models import Attachment

ALLOWED_TYPES = {
    "application/pdf", "image/png", "image/jpeg", "image/webp", "text/csv", "application/xml", "text/xml",
    "application/json", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "text/plain",
}


def _root() -> Path:
    root = Path(get_settings().storage_path).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def save_attachment(db: Session, *, company_id: int, entity_type: str, entity_id: int, filename: str,
                    content_type: str, data: bytes, user_id: int | None, description: str | None = None) -> Attachment:
    if content_type not in ALLOWED_TYPES:
        raise BusinessRuleViolation(f"Tipo de archivo no permitido: {content_type}")
    if len(data) > get_settings().max_upload_mb * 1024 * 1024:
        raise BusinessRuleViolation("El archivo excede el tamaño máximo permitido")
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", os.path.basename(filename))[:120] or "archivo"
    key = f"{company_id}/{entity_type}/{uuid.uuid4().hex}_{safe_name}"
    path = _root() / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    att = Attachment(company_id=company_id, entity_type=entity_type, entity_id=entity_id, filename=safe_name,
                     content_type=content_type, size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                     storage_key=key, description=description, uploaded_by_id=user_id)
    db.add(att)
    db.flush()
    return att


def read_attachment(att: Attachment) -> bytes:
    path = (_root() / att.storage_key).resolve()
    if _root() not in path.parents or not path.exists():
        raise NotFound("Archivo no disponible en el almacenamiento")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != att.sha256:
        raise BusinessRuleViolation("El archivo almacenado no coincide con su huella de integridad")
    return data
