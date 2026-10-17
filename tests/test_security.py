"""Autenticación, sesiones, permisos, aislamiento multiempresa, segregación de funciones y cabeceras."""
from conftest import PASSWORD, build_company
from sqlalchemy import select

from app.core.db import SessionLocal
from app.modules.iam.models import AuditLog, LoginAttempt


def test_login_and_me(env, client):
    api = env.api("admin1")
    me = api.get("/auth/me")
    assert me["email"] == "admin1@pruebas.datasys.co"
    assert me["companies"][0]["country"] == "CO"
    assert "purchasing.order.approve" in me["companies"][0]["permissions"]
    assert "operations" in me["companies"][0]["disabled_modules"]  # sector comercial


def test_bad_password_is_recorded_and_locks_account(env, client):
    for _ in range(5):
        r = client.post("/api/v1/auth/login", json={"email": "vendedor@pruebas.datasys.co", "password": "mala"})
        assert r.status_code == 401
    r = client.post("/api/v1/auth/login", json={"email": "vendedor@pruebas.datasys.co", "password": PASSWORD})
    assert r.status_code == 401 and "bloqueado" in r.json()["error"]["message"]
    with SessionLocal() as db:
        reasons = [a.reason for a in db.scalars(select(LoginAttempt).order_by(LoginAttempt.id))]
    assert reasons.count("bad_password") == 4 and "locked_now" in reasons and reasons[-1] == "locked"


def test_unknown_user_same_error(client, env):
    r = client.post("/api/v1/auth/login", json={"email": "nadie@pruebas.datasys.co", "password": "x"})
    assert r.status_code == 401 and r.json()["error"]["message"] == "Credenciales inválidas"


def test_refresh_rotation_and_reuse_detection(env, client):
    api = env.api("admin1")
    old = api.tokens["refresh_token"]
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": old})
    assert r.status_code == 200
    new = r.json()["refresh_token"]
    assert new != old
    # Reutilizar el token rotado revoca todas las sesiones
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": old}).status_code == 401
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": new}).status_code == 401


def test_requires_token_and_company(env, client):
    assert client.get("/api/v1/masters/items").status_code in (401, 404)
    assert client.get("/api/v1/items", headers={"X-Company-Id": str(env["company_id"])}).status_code == 401
    api = env.api("admin1")
    r = client.get("/api/v1/items", headers={"Authorization": api.headers["Authorization"]})
    assert r.status_code == 422  # falta X-Company-Id


def test_permission_denied(env):
    vendedor = env.api("vendedor")
    r = vendedor.get("/accounting/reports/trial-balance?start=2026-01-01&end=2026-12-31", expect=403)
    assert "accounting.reports.read" in r.json()["error"]["details"]["missing"]
    auditor = env.api("auditor")
    auditor.get("/items")  # lectura permitida
    auditor.post("/items", {"sku": "X", "name": "X", "item_type": "merchandise", "base_uom_id": env["uom_id"]}, expect=403)


def test_company_isolation(env, client):
    with SessionLocal() as db:
        other = build_company(db, "VE", code="OTRA")
        db.commit()
        other_id = other.id
    api = env.api("admin1")
    r = client.get("/api/v1/items", headers={**api.headers, "X-Company-Id": str(other_id)})
    assert r.status_code == 403
    # Referencias cruzadas entre empresas se rechazan aunque el usuario sea administrador
    with SessionLocal() as db:
        from app.modules.masters.models import ItemCategory

        cat = ItemCategory(company_id=other_id, code="X", name="Otra empresa")
        db.add(cat)
        db.commit()
        foreign_cat = cat.id
    r = api.post("/items", {"sku": "Z1", "name": "Z", "item_type": "merchandise", "base_uom_id": env["uom_id"],
                            "category_id": foreign_cat}, expect=422)
    assert "otra empresa" in r.json()["error"]["message"]


def test_segregation_of_duties_self_approval(env):
    a = env.api("admin1")
    req = a.post("/purchasing/requisitions", {"site_id": env["site_id"], "lines": [
        {"item_id": env["items"]["A"], "quantity": "2", "estimated_unit_price": "10"}]})
    a.post(f"/purchasing/requisitions/{req['id']}/submit")
    r = a.post(f"/purchasing/requisitions/{req['id']}/decision", {"approve": True}, expect=403)
    assert "Segregación" in r.json()["error"]["message"]
    env.api("admin2").post(f"/purchasing/requisitions/{req['id']}/decision", {"approve": True})


def test_approval_limit(env):
    admin = env.api("admin1")
    admin.put("/approval-limits", {"role_code": "aprobador_compras", "document_type": "purchase_requisition",
                                   "max_amount": "100"})
    c = env.api("comprador")
    req = c.post("/purchasing/requisitions", {"site_id": env["site_id"], "lines": [
        {"item_id": env["items"]["A"], "quantity": "10", "estimated_unit_price": "50"}]})
    c.post(f"/purchasing/requisitions/{req['id']}/submit")
    r = env.api("aprobador").post(f"/purchasing/requisitions/{req['id']}/decision", {"approve": True}, expect=403)
    assert "límite" in r.json()["error"]["message"]


def test_password_policy(env):
    r = env.api("admin1").post("/admin/users", {"email": "nuevo@pruebas.datasys.co", "full_name": "Nuevo",
                                                "password": "corta"}, expect=422)
    assert "política" in r.json()["error"]["message"]


def test_security_headers_and_request_id(env, client):
    r = client.get("/health/live")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["X-Request-Id"]


def test_rate_limit(env, client, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "login_rate_limit_per_minute", 3)
    codes = [client.post("/api/v1/auth/login", json={"email": "x@pruebas.datasys.co", "password": "x"}).status_code
             for _ in range(5)]
    assert codes[:3] == [401, 401, 401] and codes[-1] == 429


def test_audit_trail_records_changes_and_actions(env):
    api = env.api("admin1")
    item = api.post("/items", {"sku": "AUD-1", "name": "Auditado", "item_type": "merchandise", "base_uom_id": env["uom_id"]})
    api.patch(f"/items/{item['id']}", {"name": "Auditado 2"})
    log = api.get(f"/admin/audit?entity_type=items&entity_id={item['id']}")
    actions = [x["action"] for x in log["items"]]
    assert "create" in actions and "update" in actions
    upd = next(x for x in log["items"] if x["action"] == "update")
    assert upd["changes"]["name"] == ["Auditado", "Auditado 2"]
    with SessionLocal() as db:
        row = db.scalar(select(AuditLog).where(AuditLog.entity_type == "items", AuditLog.entity_id == str(item["id"]),
                                               AuditLog.action == "create"))
        assert row.user_id is not None and row.ip is not None


def test_audit_log_is_append_only(env):
    import pytest
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    env.api("admin1").post("/items", {"sku": "AUD-2", "name": "x", "item_type": "merchandise", "base_uom_id": env["uom_id"]})
    with SessionLocal() as db, pytest.raises(DBAPIError):
        db.execute(text("delete from audit_log"))
        db.commit()
