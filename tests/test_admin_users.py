"""Administración de usuarios y roles: altas, vínculos entre empresas, roles propios, vigencias, controles de
escalamiento de privilegios, último administrador y trazabilidad."""
from datetime import timedelta

from conftest import PASSWORD, TODAY, Api, build_company
from sqlalchemy import select, update

from app.core.db import SessionLocal
from app.modules.iam.models import Role, User, UserCompanyRole

NEW = "nuevo@pruebas.datasys.co"


def _uid(email: str) -> int:
    with SessionLocal() as db:
        return db.scalar(select(User.id).where(User.email == email))


def _login(client, email, password):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


def test_create_user_with_roles_and_forced_password_change(env, client):
    admin = env.api("admin1")
    u = admin.post("/admin/users", {"email": NEW, "full_name": "Nuevo Vendedor", "job_title": "Asesor comercial",
                                    "roles": [{"role_code": "vendedor", "site_id": env["site_id"]}]}, expect=201).json()
    temp = u["temporary_password"]
    assert temp and u["must_change_password"] and u["roles"][0]["role"] == "vendedor"
    assert u["roles"][0]["site_name"] and u["roles"][0]["granted_by"] == "admin1"

    tokens = _login(client, NEW, temp)
    headers = {"Authorization": f"Bearer {tokens['access_token']}", "X-Company-Id": str(env["company_id"])}
    me = client.get("/api/v1/auth/me", headers=headers).json()
    assert me["must_change_password"] is True
    r = client.get("/api/v1/sales/orders", headers=headers)
    assert r.status_code == 403 and r.json()["error"]["details"]["must_change_password"]

    assert client.post("/api/v1/auth/change-password", headers=headers,
                       json={"current_password": temp, "new_password": temp}).status_code == 422
    assert client.post("/api/v1/auth/change-password", headers=headers,
                       json={"current_password": temp, "new_password": PASSWORD}).status_code == 204
    api = Api(client, NEW, env["company_id"])
    api.get("/sales/orders")
    api.get("/accounting/periods", expect=403)


def test_user_without_role_is_rejected(env):
    r = env.api("admin1").post("/admin/users", {"email": NEW, "full_name": "Sin rol"}, expect=422)
    assert "al menos un rol" in r.json()["error"]["message"]


def test_link_existing_user_from_other_company(env, client):
    with SessionLocal() as db:
        other = build_company(db, "VE", code="OTRAVE")
        db.commit()
        other_id = other.id
    root = Api(client, "root@pruebas.datasys.co", other_id)
    root.post("/admin/users", {"email": "admin2@pruebas.datasys.co", "full_name": "Admin Dos",
                               "roles": [{"role_code": "auditor"}]}, expect=201)
    me = env.api("admin2").get("/auth/me")
    assert {c["code"] for c in me["companies"]} == {"TESTCO", "OTRAVE"}
    # El administrador de TESTCO ya no controla la cuenta: tiene acceso a otra empresa del grupo.
    admin = env.api("admin1")
    uid = _uid("admin2@pruebas.datasys.co")
    r = admin.post(f"/admin/users/{uid}/reset-password", {}, expect=403)
    assert "otras empresas" in r.json()["error"]["message"]
    admin.patch(f"/admin/users/{uid}", {"is_active": False}, expect=403)
    admin.patch(f"/admin/users/{uid}", {"job_title": "Jefe administrativo"})  # datos no sensibles sí
    root_co = Api(client, "root@pruebas.datasys.co", env["company_id"])
    assert root_co.post(f"/admin/users/{uid}/reset-password", {}, expect=200).json()["temporary_password"]


def test_cannot_grant_permissions_you_do_not_have(env):
    admin = env.api("admin1")
    role = admin.post("/admin/roles", {"code": "jefe_ventas", "name": "Jefe de ventas", "permissions": [
        "admin.users.read", "admin.users.create", "admin.users.admin", "sales.order.read", "sales.order.create",
        "sales.order.approve"]}, expect=201).json()
    assert role["editable"] and not role["is_system"]
    vend = _uid("vendedor@pruebas.datasys.co")
    admin.post(f"/admin/users/{vend}/roles", {"role_code": "jefe_ventas"})
    jefe = env.api("vendedor")
    comprador = _uid("comprador@pruebas.datasys.co")
    r = jefe.post(f"/admin/users/{comprador}/roles", {"role_code": "contador"}, expect=403)
    assert "accounting.journal.post" in r.json()["error"]["details"]["missing"]
    jefe.post(f"/admin/users/{comprador}/roles", {"role_code": "jefe_ventas"}, expect=200)
    jefe.post(f"/admin/users/{_uid('auditor@pruebas.datasys.co')}/roles", {"role_code": "jefe_ventas"})
    # Tampoco puede crear un rol con permisos ajenos (le falta admin.roles.admin de todos modos)
    jefe.post("/admin/roles", {"code": "x", "name": "x", "permissions": ["sales.order.read"]}, expect=403)


def test_last_admin_cannot_be_removed(env, client):
    admin1 = env.api("admin1")
    admin2_id = _uid("admin2@pruebas.datasys.co")
    admin1.patch(f"/admin/users/{admin2_id}", {"is_active": False})
    root = Api(client, "root@pruebas.datasys.co", env["company_id"])
    me_id = _uid("admin1@pruebas.datasys.co")
    detail = root.get(f"/admin/users/{me_id}")
    aid = detail["roles"][0]["assignment_id"]
    r = root._call("DELETE", f"/admin/users/{me_id}/roles/{aid}", 422)
    assert "sin ningún administrador" in r.json()["error"]["message"]
    root.patch(f"/admin/users/{me_id}", {"is_active": False}, expect=422)
    # Con otro administrador activo sí se puede
    admin1.patch(f"/admin/users/{admin2_id}", {"is_active": True})
    root._call("DELETE", f"/admin/users/{me_id}/roles/{aid}", 204)


def test_self_management_is_blocked(env):
    admin = env.api("admin1")
    me_id = _uid("admin1@pruebas.datasys.co")
    admin.post(f"/admin/users/{me_id}/roles", {"role_code": "contador"}, expect=422)
    admin.patch(f"/admin/users/{me_id}", {"is_active": False}, expect=422)
    aid = admin.get(f"/admin/users/{me_id}")["roles"][0]["assignment_id"]
    admin._call("DELETE", f"/admin/users/{me_id}/roles/{aid}", 422)


def test_temporary_role_expires(env):
    admin = env.api("admin1")
    vend = _uid("vendedor@pruebas.datasys.co")
    u = admin.post(f"/admin/users/{vend}/roles", {"role_code": "contador", "expires_on": str(TODAY),
                                                  "note": "Reemplazo por vacaciones"})
    assert any(r["role"] == "contador" and r["is_current"] for r in u["roles"])
    env.api("vendedor").get("/accounting/periods")
    admin.post(f"/admin/users/{vend}/roles", {"role_code": "contador"}, expect=409)
    admin.post(f"/admin/users/{vend}/roles", {"role_code": "auditor", "expires_on": str(TODAY - timedelta(days=1))},
               expect=422)
    with SessionLocal() as db:
        db.execute(update(UserCompanyRole).where(UserCompanyRole.user_id == vend, UserCompanyRole.expires_on.isnot(None))
                   .values(expires_on=TODAY - timedelta(days=1)))
        db.commit()
    v = env.api("vendedor")
    v.get("/accounting/periods", expect=403)
    assert "accounting.period.read" not in v.get("/auth/me")["companies"][0]["permissions"]
    # Reasignar un rol vencido renueva la asignación existente
    u = admin.post(f"/admin/users/{vend}/roles", {"role_code": "contador"})
    assert [r["is_current"] for r in u["roles"] if r["role"] == "contador"] == [True]


def test_site_and_duplicate_validation(env):
    with SessionLocal() as db:
        other = build_company(db, "VE", code="OTRAVE")
        db.commit()
        from app.modules.org.models import Site

        foreign_site = db.scalar(select(Site.id).where(Site.company_id == other.id))
    admin = env.api("admin1")
    vend = _uid("vendedor@pruebas.datasys.co")
    admin.post(f"/admin/users/{vend}/roles", {"role_code": "despachador", "site_id": foreign_site}, expect=422)
    admin.post(f"/admin/users/{vend}/roles", {"role_code": "vendedor"}, expect=409)
    admin.post(f"/admin/users/{vend}/roles", {"role_code": "no_existe"}, expect=404)


def test_custom_role_lifecycle_and_history(env):
    admin = env.api("admin1")
    roles = admin.get("/admin/roles")
    system = next(r for r in roles if r["code"] == "vendedor")
    assert system["is_system"] and system["users_count"] == 1
    admin.patch(f"/admin/roles/{system['id']}", {"name": "x"}, expect=422)
    admin.post("/admin/roles", {"code": "vendedor", "name": "dup", "permissions": ["sales.order.read"]}, expect=409)

    clone = admin.post("/admin/roles", {"code": "vendedor_senior", "name": "Vendedor sénior",
                                        "copy_from_role_id": system["id"]}, expect=201).json()
    assert set(clone["permissions"]) == set(system["permissions"])
    edited = admin.patch(f"/admin/roles/{clone['id']}", {"permissions": clone["permissions"] + ["sales.order.approve"]})
    assert "sales.order.approve" in edited["permissions"]
    assert edited["history"][0]["changes"]["added"] == ["sales.order.approve"]
    admin.patch(f"/admin/roles/{clone['id']}", {"permissions": ["no.existe.read"]}, expect=422)

    comprador = _uid("comprador@pruebas.datasys.co")
    u = admin.post(f"/admin/users/{comprador}/roles", {"role_code": "vendedor_senior"})
    admin._call("DELETE", f"/admin/roles/{clone['id']}", 422)
    aid = next(r["assignment_id"] for r in u["roles"] if r["role"] == "vendedor_senior")
    admin._call("DELETE", f"/admin/users/{comprador}/roles/{aid}", 204)
    admin._call("DELETE", f"/admin/roles/{clone['id']}", 204)
    with SessionLocal() as db:
        assert db.get(Role, clone["id"]) is None

    catalog = admin.get("/admin/permissions")
    sales = next(m for m in catalog if m["module"] == "sales")
    assert sales["label"] == "Ventas" and sales["resources"][0]["actions"][0]["label"] == "Consultar"


def test_custom_roles_are_isolated_per_company(env, client):
    with SessionLocal() as db:
        other = build_company(db, "VE", code="OTRAVE")
        db.commit()
        other_id = other.id
    env.api("admin1").post("/admin/roles", {"code": "propio", "name": "Propio", "permissions": ["kpi.dashboard.read"]},
                           expect=201)
    root = Api(client, "root@pruebas.datasys.co", other_id)
    assert "propio" not in {r["code"] for r in root.get("/admin/roles")}
    root.post("/admin/roles", {"code": "propio", "name": "Propio VE", "permissions": ["kpi.dashboard.read"]}, expect=201)


def test_reset_password_unlock_and_sessions(env, client):
    vend_api = env.api("vendedor")
    old_refresh = vend_api.tokens["refresh_token"]
    vend = _uid("vendedor@pruebas.datasys.co")
    admin = env.api("admin1")
    assert len(admin.get(f"/admin/users/{vend}")["sessions"]) == 1
    assert admin.post(f"/admin/users/{vend}/revoke-sessions")["revoked"] == 1
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh}).status_code == 401

    for _ in range(5):
        client.post("/api/v1/auth/login", json={"email": "vendedor@pruebas.datasys.co", "password": "mala"})
    assert admin.get("/admin/users?status=locked")[0]["id"] == vend
    assert admin.post(f"/admin/users/{vend}/unlock")["status"] == "active"
    env.api("vendedor")

    r = admin.post(f"/admin/users/{vend}/reset-password", {"new_password": "Temporal-Segura-99!"})
    assert r["temporary_password"] is None and r["must_change_password"]
    assert client.post("/api/v1/auth/login", json={"email": "vendedor@pruebas.datasys.co",
                                                   "password": PASSWORD}).status_code == 401
    _login(client, "vendedor@pruebas.datasys.co", "Temporal-Segura-99!")
    admin.post(f"/admin/users/{vend}/reset-password", {"new_password": "corta"}, expect=422)

    history = admin.get(f"/admin/users/{vend}")["history"]
    summaries = [h["summary"] for h in history]
    assert "Desbloqueo de la cuenta" in summaries and "Restablecimiento de contraseña por el administrador" in summaries
    assert history[0]["by_name"] == "admin1"


def test_deactivation_closes_sessions(env, client):
    vend_api = env.api("vendedor")
    vend = _uid("vendedor@pruebas.datasys.co")
    env.api("admin1").patch(f"/admin/users/{vend}", {"is_active": False})
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": vend_api.tokens["refresh_token"]}).status_code == 401
    assert client.get("/api/v1/auth/me", headers=vend_api.headers).status_code == 401


def test_user_search_and_access_review_export(env):
    admin = env.api("admin1")
    assert [u["email"] for u in admin.get("/admin/users?q=compra")] == ["comprador@pruebas.datasys.co"]
    vend_role = next(r["id"] for r in admin.get("/admin/roles") if r["code"] == "vendedor")
    assert len(admin.get(f"/admin/users?role_id={vend_role}")) == 1
    review = admin.get("/admin/access-review")
    assert {"full_name", "role", "site", "granted_by", "status"} <= set(review[0])
    r = admin._call("GET", "/admin/access-review/export.csv", 200)
    assert r.headers["content-type"].startswith("text/csv") and "vendedor@pruebas.datasys.co" in r.text
    env.api("vendedor")._call("GET", "/admin/access-review/export.csv", 403)


def test_audit_filters_and_export(env):
    admin = env.api("admin1")
    vend = _uid("vendedor@pruebas.datasys.co")
    admin.patch(f"/admin/users/{vend}", {"job_title": "Asesor"})
    data = admin.get(f"/admin/audit?entity_type=users&entity_id={vend}&date_from={TODAY}&date_to={TODAY}")
    assert data["total"] >= 1 and data["items"][0]["user_name"] == "admin1"
    assert admin.get("/admin/audit?q=actualización")["total"] >= 1
    r = env.api("auditor")._call("GET", "/admin/audit/export.csv?entity_type=users", 200)
    assert "Actualización de datos" in r.text
    env.api("comprador")._call("GET", "/admin/audit/export.csv", 403)
    assert admin.get("/admin/login-attempts?success=true")[0]["success"] is True
