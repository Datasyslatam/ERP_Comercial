"""Worker: evaluación periódica de alertas y registros de log válidos."""
import ast
import logging
from pathlib import Path

from sqlalchemy import event

from app.core.config import get_settings
from app.core.db import SessionLocal, engine
from app.worker import evaluate_all_alerts

BACKEND = Path(__file__).resolve().parents[1] / "backend" / "app"
# Atributos propios de logging.LogRecord: usarlos como clave en `extra` lanza KeyError al registrar.
RESERVED = set(vars(logging.LogRecord("x", logging.INFO, "x", 0, "x", None, None))) | {"message", "asctime"}


def test_db_connection_attempt_is_time_limited():
    # Sin límite, una base que no responde retiene al worker o a una petición del api hasta 130 s (default de psycopg).
    seen = {}

    def spy(dialect, record, cargs, cparams):
        seen.update(cparams)

    event.listen(engine, "do_connect", spy)
    try:
        engine.dispose()
        with engine.connect():
            pass
    finally:
        event.remove(engine, "do_connect", spy)
    assert seen["connect_timeout"] == get_settings().db_connect_timeout == 10


def test_alert_evaluation_logs_without_error(env, caplog, monkeypatch):
    # La configuración de logging de Alembic (al migrar la base de pruebas) deshabilita los loggers existentes.
    monkeypatch.setattr(logging.getLogger("erp.worker"), "disabled", False)
    caplog.set_level(logging.INFO, logger="erp.worker")
    evaluate_all_alerts(SessionLocal)
    records = [r for r in caplog.records if r.getMessage() == "alerts_evaluated"]
    assert records and hasattr(records[0], "alerts_created") and records[0].company == "TESTCO"


def test_log_extra_keys_do_not_collide_with_logrecord():
    offending = []
    for path in BACKEND.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call):
                continue
            for kw in node.keywords:
                if kw.arg == "extra" and isinstance(kw.value, ast.Dict):
                    for key in kw.value.keys:
                        if isinstance(key, ast.Constant) and key.value in RESERVED:
                            offending.append(f"{path.name}:{node.lineno} {key.value}")
    assert not offending, f"Claves reservadas de LogRecord en extra=: {offending}"
