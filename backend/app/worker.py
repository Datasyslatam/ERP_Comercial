"""Proceso de fondo: bandeja de salida de integraciones (facturación electrónica) y evaluación de alertas.

Ejecutar: python -m app.worker   (en Docker: servicio 'worker').
Varias réplicas pueden correr a la vez: los eventos se toman con FOR UPDATE SKIP LOCKED.
"""
import logging
import signal
import time
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.audit import register_audit_listener
from app.core.db import SessionLocal
from app.core.http import setup_logging
from app.core.outbox import process_batch
from app.modules.kpi.service import evaluate_alerts
from app.modules.org.models import Company

log = logging.getLogger("erp.worker")
_running = True


def _stop(*_):
    global _running
    _running = False


def run(poll_seconds: float = 5.0, alert_every_seconds: int = 3600) -> None:
    setup_logging()
    register_audit_listener()
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    last_alerts = 0.0
    log.info("worker_started")
    while _running:
        try:
            n = process_batch(SessionLocal)
            if time.monotonic() - last_alerts > alert_every_seconds:
                with SessionLocal() as db:
                    for company in db.scalars(select(Company).where(Company.is_active.is_(True))):
                        created = evaluate_alerts(db, company)
                        db.commit()
                        log.info("alerts_evaluated", extra={"company": company.code, "created": created})
                last_alerts = time.monotonic()
            if n == 0:
                time.sleep(poll_seconds)
        except Exception:  # noqa: BLE001 - el worker no debe morir por un fallo puntual
            log.exception("worker_iteration_failed", extra={"at": datetime.now(UTC).isoformat()})
            time.sleep(poll_seconds)
    log.info("worker_stopped")


if __name__ == "__main__":
    run()
