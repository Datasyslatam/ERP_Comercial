"""Recuperación de datos: respaldo con pg_dump y restauración con pg_restore en una base distinta.

Requiere los binarios de PostgreSQL (pg_dump, pg_restore, psql) en PATH o en PG_BIN; si no existen, la prueba
se marca como omitida (no como aprobada).
"""
import os
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import pytest
from helpers import confirmed_so, shipped_dispatch, stock_in
from sqlalchemy import create_engine, text


def _bin(name):
    pg_bin = os.environ.get("PG_BIN")
    if pg_bin:
        p = Path(pg_bin) / (name + (".exe" if os.name == "nt" else ""))
        return str(p) if p.exists() else None
    return shutil.which(name)


@pytest.mark.skipif(not (_bin("pg_dump") and _bin("pg_restore")), reason="Binarios de PostgreSQL no disponibles")
def test_backup_and_restore_roundtrip(env, tmp_path):
    stock_in(env, "A", qty=10, price=100)
    shipped_dispatch(env, confirmed_so(env, "A", qty=3))
    src = os.environ["TEST_DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
    u = urlparse(src)
    pg_env = {**os.environ, "PGPASSWORD": u.password or ""}
    conn = ["-h", u.hostname, "-p", str(u.port or 5432), "-U", u.username]
    dump = tmp_path / "erp.dump"
    subprocess.run([_bin("pg_dump"), *conn, "-Fc", "--no-owner", "-f", str(dump), u.path.lstrip("/")],
                   check=True, env=pg_env)
    restore_db = "erp_restore_check"
    admin = create_engine(src.replace("postgresql://", "postgresql+psycopg://").rsplit("/", 1)[0] + "/postgres",
                          isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f"drop database if exists {restore_db}"))
        c.execute(text(f"create database {restore_db}"))
    try:
        subprocess.run([_bin("pg_restore"), *conn, "--no-owner", "--exit-on-error", "-d", restore_db, str(dump)],
                       check=True, env=pg_env)
        q = text("""select (select count(*) from journal_entries), (select count(*) from stock_moves),
                           (select coalesce(sum(debit - credit), 0) from journal_lines),
                           (select count(*) from pg_trigger where tgname like 'trg_%')""")
        e_src = create_engine(src.replace("postgresql://", "postgresql+psycopg://"))
        e_dst = create_engine(src.replace("postgresql://", "postgresql+psycopg://").rsplit("/", 1)[0] + "/" + restore_db)
        with e_src.connect() as a, e_dst.connect() as b:
            assert a.execute(q).one() == b.execute(q).one()
            assert b.execute(text("select count(*) from pg_trigger where tgname like 'trg_%'")).scalar() >= 5
        e_dst.dispose()
        e_src.dispose()
    finally:
        with admin.connect() as c:
            c.execute(text(f"drop database if exists {restore_db} with (force)"))
        admin.dispose()
