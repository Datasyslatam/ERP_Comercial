"""Despachador de la bandeja de salida (outbox): procesa eventos de integración con reintentos seguros.

Cada evento se toma con FOR UPDATE SKIP LOCKED (varios workers pueden correr en paralelo sin duplicar
trabajo) y se procesa en su propia transacción. Fallos temporales se reintentan con espera exponencial;
al agotar los intentos el evento queda 'failed' y se genera una alerta.
"""
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.modules.kpi.models import Alert
from app.modules.org.models import IntegrationEvent

log = logging.getLogger("erp.outbox")


def _handlers():
    from app.modules.documents.service import email_failed, process_email
    from app.modules.einvoicing.service import process_submission, submission_failed

    # tipo de evento → (manejador, registro del fallo fuera del savepoint revertido)
    return {"einvoice.submit": (process_submission, submission_failed),
            "document.email": (process_email, email_failed)}


def process_batch(session_factory, limit: int = 20) -> int:
    handlers = _handlers()
    processed = 0
    for _ in range(limit):
        with session_factory() as db:  # type: Session
            ev = db.scalar(select(IntegrationEvent)
                           .where(IntegrationEvent.status.in_(("pending", "retry")),
                                  IntegrationEvent.next_attempt_at <= datetime.now(UTC))
                           .order_by(IntegrationEvent.id).limit(1).with_for_update(skip_locked=True))
            if ev is None:
                break
            ev.attempts += 1
            handler, on_error = handlers.get(ev.event_type, (None, None))
            try:
                if handler is None:
                    raise RuntimeError(f"Sin manejador para {ev.event_type}")
                with db.begin_nested():
                    handler(db, ev)
                ev.status, ev.processed_at, ev.last_error = "done", datetime.now(UTC), None
            except Exception as exc:  # noqa: BLE001 - se registra y reintenta
                ev.last_error = f"{type(exc).__name__}: {exc}"[:2000]
                if on_error is not None:
                    on_error(db, ev, exc)
                if ev.attempts >= ev.max_attempts:
                    ev.status = "failed"
                    db.add(Alert(company_id=ev.company_id, source=f"integration:{ev.event_type}",
                                 dedupe_key=f"integration:{ev.id}", severity="critical",
                                 message=f"Integración fallida tras {ev.attempts} intentos: {ev.last_error[:300]}"))
                else:
                    ev.status = "retry"
                    ev.next_attempt_at = datetime.now(UTC) + timedelta(seconds=min(3600, 15 * 2 ** ev.attempts))
                log.warning("outbox_event_failed", extra={"event_id": ev.id, "attempts": ev.attempts,
                                                          "error": ev.last_error})
            db.commit()
            processed += 1
    return processed
