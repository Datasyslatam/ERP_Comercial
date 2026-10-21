import { FormEvent, ReactNode, useMemo, useState } from "react";
import { ActionButton, Alert, Badge, DataTable, Form, KeyValues, Modal, Page } from "../components/ui";
import { api, download, Json, patch, post, put, qs } from "../lib/api";
import { fmtDate, fmtMoney } from "../lib/format";
import { useFetch, useOptions } from "../lib/hooks";
import { useSession } from "../lib/session";

const today = () => new Date().toISOString().slice(0, 10);
const del = (path: string) => api("DELETE", path);

const ACTIONS = ["read", "create", "approve", "post", "void", "export", "admin"];
const ACTION_SHORT: Record<string, string> = {
  read: "Consultar", create: "Crear", approve: "Aprobar", post: "Contabilizar", void: "Anular", export: "Exportar", admin: "Administrar",
};
const LIMIT_DOCS: Record<string, string> = {
  purchase_requisition: "Solicitudes de compra", purchase_order: "Órdenes de compra",
  inventory_adjustment: "Ajustes de inventario", payment: "Pagos",
};
const AUDIT_ACTIONS: Record<string, string> = {
  create: "Creación", update: "Modificación", delete: "Eliminación", grant: "Asignación de rol", revoke: "Revocación de rol",
  link: "Vinculación", activate: "Activación", deactivate: "Desactivación", security: "Seguridad", permissions: "Permisos de rol",
  admin: "Administración", export: "Exportación", approve: "Aprobación", post: "Contabilización", void: "Anulación", lock: "Bloqueo",
};
const LOGIN_REASONS: Record<string, string> = {
  bad_password: "Contraseña incorrecta", locked: "Cuenta bloqueada", locked_now: "Bloqueo por intentos", inactive: "Usuario inactivo",
  unknown_user: "Usuario inexistente",
};

/** Catálogo de permisos con etiquetas (módulo · recurso · acción) para mostrar códigos de forma legible. */
function usePermissionCatalog() {
  const { can } = useSession();
  const { data } = useFetch<Json[]>(can("admin.roles.read") ? "/admin/permissions" : null);
  const labels = useMemo(() => {
    const m = new Map<string, { module: string; resource: string; action: string }>();
    for (const mod of data ?? []) for (const r of mod.resources) for (const a of r.actions) {
      m.set(a.code, { module: mod.label, resource: r.label, action: a.label });
    }
    return m;
  }, [data]);
  return { catalog: data, labels };
}

function Tabs({ tabs, current, onChange }: { tabs: [string, string][]; current: string; onChange: (k: string) => void }) {
  return (
    <div className="tabs" role="tablist">
      {tabs.map(([k, l]) => (
        <button key={k} role="tab" aria-selected={current === k} className={current === k ? "tab active" : "tab"}
                onClick={() => onChange(k)}>{l}</button>
      ))}
    </div>
  );
}

function RoleChips({ roles }: { roles: Json[] }) {
  if (!roles?.length) return <span className="muted">Sin roles</span>;
  return <span className="chips">{roles.map((r) => (
    <span key={r.assignment_id} className={`chip ${r.is_current ? "" : "chip-off"}`}
          title={[r.site_name && `Sede: ${r.site_name}`, r.expires_on && `Vence: ${r.expires_on}`].filter(Boolean).join(" · ")}>
      {r.role_name}{r.site_name ? ` · ${r.site_name}` : ""}{r.expires_on ? ` ⏱ ${r.expires_on}` : ""}
    </span>))}</span>;
}

/** Muestra una contraseña temporal una sola vez, con opción de copiarla. */
function SecretBox({ value, children }: { value: string; children?: ReactNode }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="alert alert-ok secret">
      <p>{children ?? "Contraseña temporal (se muestra una sola vez; el usuario deberá cambiarla al ingresar):"}</p>
      <div className="row"><code>{value}</code>
        <button className="secondary" onClick={() => navigator.clipboard?.writeText(value).then(() => setCopied(true))}>
          {copied ? "Copiada" : "Copiar"}</button></div>
    </div>
  );
}

// ------------------------------------------------------------------ usuarios
export function UsersPage() {
  const { can } = useSession();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [roleId, setRoleId] = useState("");
  const users = useFetch<Json[]>(`/admin/users${qs({ q, status, role_id: roleId })}`);
  const roles = useFetch<Json[]>(can("admin.roles.read") ? "/admin/roles" : null);
  const [creating, setCreating] = useState(false);
  const [current, setCurrent] = useState<number | null>(null);
  return (
    <Page title="Usuarios" subtitle="Altas, roles por empresa y sede, accesos temporales y control de cuentas" actions={<>
      {can("admin.audit.export") && <ActionButton className="secondary" onClick={() => download("/admin/access-review/export.csv", "revision-accesos.csv")}>
        Revisión de accesos (CSV)</ActionButton>}
      {can("admin.users.create") && can("admin.users.admin") && <button onClick={() => setCreating(true)}>Nuevo usuario</button>}</>}>
      <div className="filters">
        <label>Buscar<input placeholder="Nombre, correo o cargo" value={q} onChange={(e) => setQ(e.target.value)} /></label>
        <label>Estado<select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">Todos</option><option value="active">Activos</option><option value="inactive">Inactivos</option>
          <option value="locked">Bloqueados</option></select></label>
        <label>Rol<select value={roleId} onChange={(e) => setRoleId(e.target.value)}>
          <option value="">Todos</option>{(roles.data ?? []).map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}</select></label>
      </div>
      <Alert>{users.error}</Alert>
      <DataTable rows={users.data} onRowClick={(r) => setCurrent(r.id)} empty="No hay usuarios con esos criterios" columns={[
        { key: "full_name", title: "Nombre", render: (r) => <><strong>{r.full_name}</strong>{r.job_title && <div className="muted">{r.job_title}</div>}</> },
        { key: "email", title: "Correo" },
        { key: "roles", title: "Roles en la empresa", render: (r) => <RoleChips roles={r.roles} /> },
        { key: "last_login_at", title: "Último acceso", render: (r) => fmtDate(r.last_login_at) },
        { key: "status", title: "Estado", render: (r) => <span className="chips"><Badge value={r.status} />
          {r.must_change_password && <Badge value="pending_password" />}</span> }]} />
      {creating && <NewUserModal roles={roles.data ?? []} onClose={() => setCreating(false)} onDone={(id) => { users.reload(); setCreating(false); setCurrent(id); }} />}
      {current && <UserModal userId={current} roles={roles.data ?? []} onClose={() => setCurrent(null)} onChanged={users.reload} />}
    </Page>
  );
}

interface Grant { role_code: string; site_id: string; expires_on: string }

function GrantRows({ grants, setGrants, roles }: { grants: Grant[]; setGrants: (g: Grant[]) => void; roles: Json[] }) {
  const sites = useOptions("/sites", (x) => x.name);
  const set = (i: number, k: keyof Grant, v: string) => setGrants(grants.map((g, j) => (j === i ? { ...g, [k]: v } : g)));
  return (
    <div className="lines">
      <table><thead><tr><th>Rol</th><th>Sede</th><th>Vigente hasta</th><th /></tr></thead>
        <tbody>{grants.map((g, i) => (
          <tr key={i}>
            <td><select aria-label="Rol" required value={g.role_code} onChange={(e) => set(i, "role_code", e.target.value)}>
              <option value="">—</option>{roles.map((r) => <option key={r.id} value={r.code}>{r.name}{r.is_system ? "" : " (propio)"}</option>)}</select></td>
            <td><select aria-label="Sede" value={g.site_id} onChange={(e) => set(i, "site_id", e.target.value)}>
              <option value="">Todas las sedes</option>{sites.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}</select></td>
            <td><input aria-label="Vigente hasta" type="date" min={today()} value={g.expires_on} onChange={(e) => set(i, "expires_on", e.target.value)} /></td>
            <td>{grants.length > 1 && <button type="button" className="secondary" onClick={() => setGrants(grants.filter((_, j) => j !== i))}>Quitar</button>}</td>
          </tr>))}</tbody></table>
      <button type="button" className="secondary" onClick={() => setGrants([...grants, { role_code: "", site_id: "", expires_on: "" }])}>+ Rol</button>
    </div>
  );
}

const grantBody = (g: Grant) => ({ role_code: g.role_code, site_id: g.site_id ? Number(g.site_id) : null, expires_on: g.expires_on || null });

function NewUserModal({ roles, onClose, onDone }: { roles: Json[]; onClose: () => void; onDone: (id: number) => void }) {
  const [v, setV] = useState<Json>({ auth: "temporary" });
  const [grants, setGrants] = useState<Grant[]>([{ role_code: "", site_id: "", expires_on: "" }]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Json | null>(null);
  const set = (k: string) => (e: { target: { value: string } }) => setV({ ...v, [k]: e.target.value });

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const body: Json = { email: v.email, full_name: v.full_name, job_title: v.job_title || null, phone: v.phone || null,
        roles: grants.map(grantBody) };
      if (v.auth === "password") body.password = v.password;
      if (v.auth === "sso") body.external_subject = v.external_subject;
      const r = await post("/admin/users", body);
      if (r.temporary_password || r.linked_existing) setResult(r);
      else onDone(r.id);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (result) return (
    <Modal title="Usuario registrado" onClose={() => onDone(result.id)}>
      {result.linked_existing
        ? <Alert kind="info">{result.email} ya tenía cuenta en otra empresa del grupo: se vinculó a esta con los roles indicados y conserva su contraseña.</Alert>
        : <SecretBox value={result.temporary_password}>Entregue esta contraseña temporal a {result.full_name} por un canal seguro. Se muestra una sola vez y deberá cambiarla en su primer ingreso:</SecretBox>}
      <button onClick={() => onDone(result.id)}>Ver ficha del usuario</button>
    </Modal>
  );

  return (
    <Modal title="Nuevo usuario" onClose={onClose}>
      <form className="form" onSubmit={submit}>
        <div className="form-grid">
          <label><span>Nombre completo *</span><input required minLength={2} value={v.full_name ?? ""} onChange={set("full_name")} /></label>
          <label><span>Correo *</span><input type="email" required value={v.email ?? ""} onChange={set("email")} /></label>
          <label><span>Cargo</span><input value={v.job_title ?? ""} onChange={set("job_title")} /></label>
          <label><span>Teléfono</span><input value={v.phone ?? ""} onChange={set("phone")} /></label>
          <label><span>Acceso</span><select aria-label="Acceso" value={v.auth} onChange={set("auth")}>
            <option value="temporary">Generar contraseña temporal</option><option value="password">Definir contraseña temporal</option>
            <option value="sso">Inicio de sesión corporativo (SSO)</option></select></label>
          {v.auth === "password" && <label><span>Contraseña temporal *</span><input required value={v.password ?? ""} onChange={set("password")}
            placeholder="12+ caracteres, mayúscula, número y símbolo" /></label>}
          {v.auth === "sso" && <label><span>Identificador OIDC *</span><input required value={v.external_subject ?? ""} onChange={set("external_subject")} /></label>}
        </div>
        <h3>Roles en esta empresa</h3>
        <GrantRows grants={grants} setGrants={setGrants} roles={roles} />
        <p className="muted">Si el correo ya existe en otra empresa del grupo, el usuario se vincula a esta con los roles indicados.</p>
        <Alert>{error}</Alert>
        <div className="row"><button type="submit" disabled={busy}>{busy ? "Procesando…" : "Crear usuario"}</button>
          <button type="button" className="secondary" onClick={onClose}>Cancelar</button></div>
      </form>
    </Modal>
  );
}

function UserModal({ userId, roles, onClose, onChanged }: { userId: number; roles: Json[]; onClose: () => void; onChanged: () => void }) {
  const { can, me } = useSession();
  const { data: u, reload, error } = useFetch<Json>(`/admin/users/${userId}`);
  const [tab, setTab] = useState("profile");
  const [editing, setEditing] = useState(false);
  const [granting, setGranting] = useState(false);
  const [grants, setGrants] = useState<Grant[]>([{ role_code: "", site_id: "", expires_on: "" }]);
  const [secret, setSecret] = useState<string | null>(null);
  const [resetting, setResetting] = useState(false);
  const { labels } = usePermissionCatalog();
  const admin = can("admin.users.admin");
  const self = me?.id === userId;
  const refresh = () => { reload(); onChanged(); };
  if (!u) return <Modal title="Usuario" onClose={onClose}><Alert>{error}</Alert>{!error && <p className="muted">Cargando…</p>}</Modal>;
  const byModule = new Map<string, Json[]>();
  for (const p of u.permissions) {
    const l = labels.get(p.code);
    const key = l?.module ?? p.code.split(".")[0];
    byModule.set(key, [...(byModule.get(key) ?? []), { ...p, label: l ? `${l.resource} · ${l.action}` : p.code }]);
  }
  return (
    <Modal title={u.full_name} onClose={onClose}>
      <div className="row between">
        <span className="chips"><Badge value={u.status} />{u.must_change_password && <Badge value="pending_password" />}
          {u.sso && <span className="chip">SSO</span>}{u.other_companies > 0 && <span className="chip">También en {u.other_companies} empresa(s) más</span>}</span>
        {admin && !self && <span className="row">
          {u.status === "locked" && <ActionButton className="secondary" onClick={async () => { await post(`/admin/users/${userId}/unlock`); refresh(); }}>Desbloquear</ActionButton>}
          {!u.sso && <button className="secondary" onClick={() => setResetting(true)}>Restablecer contraseña</button>}
          <ActionButton className="secondary" confirm="¿Cerrar todas las sesiones abiertas de este usuario?"
            onClick={async () => { await post(`/admin/users/${userId}/revoke-sessions`); refresh(); }}>Cerrar sesiones</ActionButton>
          <ActionButton className={u.is_active ? "danger" : ""}
            confirm={u.is_active ? "¿Desactivar la cuenta? Se cerrarán sus sesiones y no podrá ingresar." : undefined}
            onClick={async () => { await patch(`/admin/users/${userId}`, { is_active: !u.is_active }); refresh(); }}>
            {u.is_active ? "Desactivar" : "Activar"}</ActionButton></span>}
      </div>
      {secret && <SecretBox value={secret} />}
      <Tabs current={tab} onChange={setTab} tabs={[["profile", "Datos"], ["roles", `Roles (${u.roles.length})`],
        ["perms", `Permisos efectivos (${u.permissions.length})`], ["security", "Sesiones y accesos"], ["trace", "Trazabilidad"]]} />

      {tab === "profile" && (editing
        ? <Form initial={{ full_name: u.full_name, email: u.email, job_title: u.job_title, phone: u.phone }} onCancel={() => setEditing(false)}
            fields={[{ name: "full_name", label: "Nombre", required: true }, { name: "email", label: "Correo", type: "email", required: true },
              { name: "job_title", label: "Cargo" }, { name: "phone", label: "Teléfono" }]}
            onSubmit={async (d) => { await patch(`/admin/users/${userId}`, d); setEditing(false); refresh(); }} />
        : <>
          <KeyValues data={u} keys={[["email", "Correo"], ["job_title", "Cargo"], ["phone", "Teléfono"],
            ["last_login_at", "Último acceso", fmtDate], ["password_changed_at", "Contraseña cambiada", fmtDate],
            ["locked_until", "Bloqueado hasta", fmtDate], ["created_at", "Creado", fmtDate]]} />
          {admin && <button className="secondary" onClick={() => setEditing(true)}>Editar datos</button>}
        </>)}

      {tab === "roles" && <>
        <DataTable rows={u.roles} columns={[{ key: "role_name", title: "Rol" }, { key: "site_name", title: "Sede", render: (r) => r.site_name ?? "Todas" },
          { key: "expires_on", title: "Vigencia", render: (r) => r.expires_on ? <span className="chips">hasta {r.expires_on} {!r.is_current && <Badge value="expired" />}</span> : "Indefinida" },
          { key: "granted_by", title: "Otorgado por", render: (r) => r.granted_by ? `${r.granted_by} · ${fmtDate(r.granted_at)}` : fmtDate(r.granted_at) },
          { key: "note", title: "Nota", render: (r) => r.note ?? "" },
          { key: "x", title: "", render: (r) => admin && !self && <ActionButton className="secondary" confirm={`¿Revocar el rol ${r.role_name}?`}
            onClick={async () => { await del(`/admin/users/${userId}/roles/${r.assignment_id}`); refresh(); }}>Revocar</ActionButton> }]} />
        {admin && !self && (granting
          ? <form className="form" onSubmit={async (e) => { e.preventDefault(); for (const g of grants) await post(`/admin/users/${userId}/roles`, grantBody(g)); setGranting(false); refresh(); }}>
              <GrantRows grants={grants} setGrants={setGrants} roles={roles} />
              <div className="row"><button type="submit">Asignar</button><button type="button" className="secondary" onClick={() => setGranting(false)}>Cancelar</button></div>
            </form>
          : <p><button onClick={() => { setGrants([{ role_code: "", site_id: "", expires_on: "" }]); setGranting(true); }}>Asignar rol</button></p>)}
        {self && <p className="muted">Sus propios roles los administra otro administrador (segregación de funciones).</p>}
      </>}

      {tab === "perms" && (u.permissions.length ? [...byModule.entries()].map(([mod, perms]) => (
        <details key={mod} className="perm-group" open={byModule.size <= 3}>
          <summary>{mod} <span className="muted">({perms.length})</span></summary>
          <ul>{perms.map((p) => <li key={p.code}>{p.label} <span className="muted">— {p.roles.join(", ")}</span></li>)}</ul>
        </details>)) : <p className="muted">Sin permisos vigentes en esta empresa.</p>)}

      {tab === "security" && <>
        <h3>Sesiones abiertas</h3>
        <DataTable rows={u.sessions} empty="Sin sesiones abiertas" columns={[{ key: "created_at", title: "Inicio", render: (r) => fmtDate(r.created_at) },
          { key: "expires_at", title: "Expira", render: (r) => fmtDate(r.expires_at) }, { key: "ip", title: "IP" },
          { key: "user_agent", title: "Navegador", render: (r) => <span className="muted">{(r.user_agent ?? "").slice(0, 60)}</span> }]} />
        <h3>Intentos de acceso recientes</h3>
        <DataTable rows={u.login_attempts} columns={[{ key: "at", title: "Fecha", render: (r) => fmtDate(r.at) }, { key: "ip", title: "IP" },
          { key: "success", title: "Resultado", render: (r) => <Badge value={r.success ? "ok" : "critical"} /> },
          { key: "reason", title: "Motivo", render: (r) => LOGIN_REASONS[r.reason] ?? "" }]} />
      </>}

      {tab === "trace" && <>
        <h3>Historial de la cuenta</h3>
        <DataTable rows={u.history} empty="Sin cambios registrados" columns={[{ key: "at", title: "Fecha", render: (r) => fmtDate(r.at) },
          { key: "action", title: "Acción", render: (r) => AUDIT_ACTIONS[r.action] ?? r.action }, { key: "summary", title: "Detalle", render: (r) => r.summary ?? changedKeys(r.changes) },
          { key: "by_name", title: "Realizado por", render: (r) => r.by_name ?? "Sistema" }]} />
        <h3>Actividad del usuario en la empresa</h3>
        <DataTable rows={u.activity} empty="Sin actividad registrada" columns={[{ key: "at", title: "Fecha", render: (r) => fmtDate(r.at) },
          { key: "action", title: "Acción", render: (r) => AUDIT_ACTIONS[r.action] ?? r.action }, { key: "entity_type", title: "Entidad" },
          { key: "entity_id", title: "Id" }, { key: "summary", title: "Detalle", render: (r) => r.summary ?? "" }]} />
      </>}

      {resetting && <Modal title={`Restablecer contraseña de ${u.full_name}`} onClose={() => setResetting(false)}>
        <p className="muted">Se cerrarán sus sesiones, se desbloqueará la cuenta y deberá cambiar la contraseña en su próximo ingreso.
          Deje el campo vacío para generar una contraseña aleatoria.</p>
        <Form submitLabel="Restablecer" fields={[{ name: "new_password", label: "Contraseña temporal (opcional)" }]}
          onSubmit={async (d) => { const r = await post(`/admin/users/${userId}/reset-password`, d); setResetting(false); setSecret(r.temporary_password); refresh(); }} />
      </Modal>}
    </Modal>
  );
}

function changedKeys(changes: Json) {
  return changes ? Object.keys(changes).filter((k) => k !== "updated_at").slice(0, 6).join(", ") : "";
}

// ------------------------------------------------------------------ roles y permisos
export function RolesPage() {
  const { can } = useSession();
  const roles = useFetch<Json[]>("/admin/roles");
  const [current, setCurrent] = useState<number | null>(null);
  const [creating, setCreating] = useState<Json | null>(null);
  return (
    <Page title="Roles y permisos" subtitle="Roles del sistema y roles propios de la empresa con su matriz de permisos"
          actions={can("admin.roles.admin") && <button onClick={() => setCreating({})}>Nuevo rol</button>}>
      <Alert>{roles.error}</Alert>
      <DataTable rows={roles.data} onRowClick={(r) => setCurrent(r.id)} columns={[
        { key: "name", title: "Rol", render: (r) => <><strong>{r.name}</strong>{r.description && <div className="muted">{r.description}</div>}</> },
        { key: "code", title: "Código", render: (r) => <code>{r.code}</code> },
        { key: "is_system", title: "Tipo", render: (r) => <span className="chip">{r.is_system ? "Sistema" : "Propio"}</span> },
        { key: "users_count", title: "Usuarios vigentes", align: "right" },
        { key: "permissions", title: "Permisos", align: "right", render: (r) => r.permissions.length }]} />
      {creating && <Modal title={creating.copy_from_role_id ? `Duplicar «${creating.name}»` : "Nuevo rol"} onClose={() => setCreating(null)}>
        <Form initial={creating.copy_from_role_id ? { copy_from_role_id: creating.copy_from_role_id, name: `${creating.name} (copia)` } : {}}
          fields={[{ name: "name", label: "Nombre", required: true }, { name: "code", label: "Código (letras, números y _)", required: true, placeholder: "jefe_bodega" },
            { name: "copy_from_role_id", label: "Partir de los permisos de", type: "select", options: (roles.data ?? []).map((r) => ({ value: r.id, label: r.name })) },
            { name: "description", label: "Descripción", type: "textarea" }]}
          onSubmit={async (d) => {
            const r = await post("/admin/roles", d); setCreating(null); roles.reload(); setCurrent(r.id);
          }} />
        <p className="muted">Después de crearlo podrá ajustar sus permisos en la matriz. Solo puede otorgar permisos que usted mismo tiene.</p>
      </Modal>}
      {current && <RoleModal roleId={current} onClose={() => setCurrent(null)} onChanged={roles.reload}
        onDuplicate={(r) => { setCurrent(null); setCreating({ copy_from_role_id: r.id, name: r.name }); }} />}
    </Page>
  );
}

function RoleModal({ roleId, onClose, onChanged, onDuplicate }: { roleId: number; onClose: () => void; onChanged: () => void; onDuplicate: (r: Json) => void }) {
  const { can, company } = useSession();
  const { data: role, reload, error } = useFetch<Json>(`/admin/roles/${roleId}`);
  const { catalog } = usePermissionCatalog();
  const [tab, setTab] = useState("perms");
  const [draft, setDraft] = useState<Set<string> | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [editingInfo, setEditingInfo] = useState(false);
  const editable = !!role?.editable && can("admin.roles.admin");
  if (!role) return <Modal title="Rol" onClose={onClose}><Alert>{error}</Alert>{!error && <p className="muted">Cargando…</p>}</Modal>;
  const selected: Set<string> = draft ?? new Set(role.permissions);
  const original = new Set<string>(role.permissions);
  const dirty = draft !== null && (draft.size !== original.size || [...draft].some((c) => !original.has(c)));
  const toggle = (codes: string[], on: boolean) => {
    const next = new Set(selected);
    codes.forEach((c) => (on ? next.add(c) : next.delete(c)));
    setDraft(next);
  };
  // No se puede otorgar lo que no se tiene: esas casillas quedan bloqueadas (pero sí se pueden quitar).
  const grantable = (code: string) => can(code) || selected.has(code);
  const refresh = () => { reload(); onChanged(); };
  return (
    <Modal title={role.name} onClose={onClose}>
      <div className="row between">
        <span className="chips"><code>{role.code}</code><span className="chip">{role.is_system ? "Rol del sistema" : "Rol propio de la empresa"}</span>
          <span className="chip">{role.permissions.length} permisos</span><span className="chip">{role.users_count} usuario(s) vigentes</span></span>
        <span className="row">
          {can("admin.roles.admin") && <button className="secondary" onClick={() => onDuplicate(role)}>Duplicar</button>}
          {editable && role.users.length === 0 && <ActionButton className="danger" confirm={`¿Eliminar el rol ${role.name}?`}
            onClick={async () => { await del(`/admin/roles/${roleId}`); onChanged(); onClose(); }}>Eliminar</ActionButton>}
        </span>
      </div>
      {role.description && <p className="muted">{role.description}</p>}
      {role.is_system && <Alert kind="info">Los roles del sistema no se modifican. Para adaptarlo, duplíquelo y edite la copia.</Alert>}
      {editable && (editingInfo
        ? <Form initial={{ name: role.name, description: role.description }} onCancel={() => setEditingInfo(false)}
            fields={[{ name: "name", label: "Nombre", required: true }, { name: "description", label: "Descripción", type: "textarea" }]}
            onSubmit={async (d) => { await patch(`/admin/roles/${roleId}`, d); setEditingInfo(false); refresh(); }} />
        : <p><button className="secondary" onClick={() => setEditingInfo(true)}>Editar nombre y descripción</button></p>)}
      <Tabs current={tab} onChange={setTab} tabs={[["perms", "Matriz de permisos"], ["users", `Usuarios (${role.users.length})`],
        ["limits", "Límites de aprobación"], ["trace", "Historial"]]} />

      {tab === "perms" && <>
        {editable && <div className="row sticky-actions">
          <button disabled={!dirty} onClick={async () => {
            setSaveError(null);
            try { await patch(`/admin/roles/${roleId}`, { permissions: [...selected] }); setDraft(null); refresh(); }
            catch (e) { setSaveError((e as Error).message); }
          }}>Guardar permisos</button>
          {dirty && <button className="secondary" onClick={() => setDraft(null)}>Descartar cambios</button>}
          {dirty && <span className="muted">{[...selected].filter((c) => !original.has(c)).length} por agregar · {[...original].filter((c) => !selected.has(c)).length} por quitar</span>}
        </div>}
        <Alert>{saveError}</Alert>
        {!catalog ? <p className="muted">Cargando catálogo…</p> : <div className="table-wrap"><table className="perm-matrix">
          <thead><tr><th>Módulo / recurso</th>{ACTIONS.map((a) => <th key={a} className="c">{ACTION_SHORT[a]}</th>)}</tr></thead>
          <tbody>{catalog.map((mod) => {
            const codes = mod.resources.flatMap((r: Json) => r.actions.map((a: Json) => a.code));
            const all = codes.every((c: string) => selected.has(c));
            return [
              <tr key={mod.module} className="perm-module"><td colSpan={ACTIONS.length + 1}>
                <label className="check">{editable && <input type="checkbox" checked={all} aria-label={`Todo ${mod.label}`}
                  onChange={(e) => toggle(codes.filter((c: string) => !e.target.checked || grantable(c)), e.target.checked)} />}<strong>{mod.label}</strong>
                  <span className="muted">{codes.filter((c: string) => selected.has(c)).length}/{codes.length}</span></label></td></tr>,
              ...mod.resources.map((r: Json) => (
                <tr key={`${mod.module}.${r.resource}`}><td className="perm-resource">{r.label}</td>
                  {ACTIONS.map((a) => {
                    const p = r.actions.find((x: Json) => x.action === a);
                    if (!p) return <td key={a} />;
                    return <td key={a} className="c"><input type="checkbox" checked={selected.has(p.code)} title={p.code}
                      aria-label={`${r.label} · ${p.label}`} disabled={!editable || !grantable(p.code)}
                      onChange={(e) => toggle([p.code], e.target.checked)} /></td>;
                  })}</tr>)),
            ];
          })}</tbody></table></div>}
      </>}

      {tab === "users" && <DataTable rows={role.users} empty="Ningún usuario tiene este rol" columns={[{ key: "full_name", title: "Usuario" }, { key: "email", title: "Correo" },
        { key: "expires_on", title: "Vigencia", render: (r) => r.expires_on ? <span className="chips">hasta {r.expires_on} {!r.is_current && <Badge value="expired" />}</span> : "Indefinida" },
        { key: "is_active", title: "Cuenta", render: (r) => <Badge value={r.is_active ? "active" : "inactive"} /> }]} />}

      {tab === "limits" && <>
        <p className="muted">Monto máximo que este rol puede aprobar por tipo de documento, en {company?.currency}. Sin límite configurado para un tipo de documento, la aprobación solo depende del permiso.</p>
        <DataTable rows={Object.keys(LIMIT_DOCS).map((k) => ({ id: k, document_type: k, max_amount: role.approval_limits.find((l: Json) => l.document_type === k)?.max_amount }))}
          columns={[{ key: "document_type", title: "Documento", render: (r) => LIMIT_DOCS[r.document_type] },
            { key: "max_amount", title: "Límite", align: "right", render: (r) => r.max_amount != null ? fmtMoney(r.max_amount, company?.currency) : "Sin límite" },
            { key: "x", title: "", render: (r) => can("admin.company.admin") && <LimitEditor roleCode={role.code} doc={r.document_type} value={r.max_amount} onSaved={refresh} /> }]} />
      </>}

      {tab === "trace" && <DataTable rows={role.history} empty="Sin cambios registrados" columns={[{ key: "at", title: "Fecha", render: (r) => fmtDate(r.at) },
        { key: "action", title: "Acción", render: (r) => AUDIT_ACTIONS[r.action] ?? r.action },
        { key: "summary", title: "Detalle", render: (r) => <>{r.summary}{r.changes?.added?.length > 0 && <div className="muted">+ {r.changes.added.join(", ")}</div>}
          {r.changes?.removed?.length > 0 && <div className="muted">− {r.changes.removed.join(", ")}</div>}</> }]} />}
    </Modal>
  );
}

function LimitEditor({ roleCode, doc, value, onSaved }: { roleCode: string; doc: string; value: unknown; onSaved: () => void }) {
  const [v, setV] = useState(value != null ? String(value) : "");
  return <span className="row">
    <input aria-label={`Límite ${LIMIT_DOCS[doc]}`} type="number" min="0" step="any" value={v} onChange={(e) => setV(e.target.value)} style={{ width: 140 }} />
    <ActionButton className="secondary" onClick={async () => { await put("/approval-limits", { role_code: roleCode, document_type: doc, max_amount: v || "0" }); onSaved(); }}>Guardar</ActionButton>
  </span>;
}

// ------------------------------------------------------------------ auditoría
export function AuditPage() {
  const { can } = useSession();
  const [f, setF] = useState<Json>({ date_from: "", date_to: "", entity_type: "", user_id: "", action: "", q: "" });
  const [loginFilter, setLoginFilter] = useState("");
  const query = qs(f);
  const { data, error } = useFetch<Json>(`/admin/audit${qs({ ...f, limit: 200 })}`);
  const users = useFetch<Json[]>(can("admin.users.read") ? "/admin/users" : null);
  const attempts = useFetch<Json[]>(`/admin/login-attempts${qs({ limit: 100, success: loginFilter })}`);
  const [detail, setDetail] = useState<Json | null>(null);
  const set = (k: string) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  return (
    <Page title="Auditoría" subtitle="Bitácora inmutable de cambios y acciones sensibles" actions={can("admin.audit.export") &&
      <ActionButton className="secondary" onClick={() => download(`/admin/audit/export.csv${query}`, "auditoria.csv")}>Exportar CSV</ActionButton>}>
      <div className="filters">
        <label>Desde<input type="date" value={f.date_from} onChange={set("date_from")} /></label>
        <label>Hasta<input type="date" value={f.date_to} onChange={set("date_to")} /></label>
        <label>Usuario<select value={f.user_id} onChange={set("user_id")}><option value="">Todos</option>
          {(users.data ?? []).map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}</select></label>
        <label>Acción<select value={f.action} onChange={set("action")}><option value="">Todas</option>
          {Object.entries(AUDIT_ACTIONS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
        <label>Entidad<input placeholder="p. ej. purchase_orders" value={f.entity_type} onChange={set("entity_type")} /></label>
        <label>Texto<input placeholder="Buscar en el detalle" value={f.q} onChange={set("q")} /></label>
      </div>
      <Alert>{error}</Alert>
      {data && <p className="muted">{data.total} registro(s){data.total > data.items.length ? `; se muestran los ${data.items.length} más recientes` : ""}.</p>}
      <DataTable rows={data?.items} onRowClick={setDetail} columns={[{ key: "at", title: "Fecha", render: (r) => fmtDate(r.at) },
        { key: "user_name", title: "Usuario", render: (r) => r.user_name ?? (r.user_id ? `#${r.user_id}` : "Sistema") },
        { key: "ip", title: "IP" }, { key: "action", title: "Acción", render: (r) => AUDIT_ACTIONS[r.action] ?? r.action },
        { key: "entity_type", title: "Entidad" }, { key: "entity_id", title: "Id" },
        { key: "summary", title: "Detalle", render: (r) => r.summary ?? changedKeys(r.changes) }]} />
      <h3>Intentos de acceso</h3>
      <div className="row"><select aria-label="Resultado" value={loginFilter} onChange={(e) => setLoginFilter(e.target.value)}>
        <option value="">Todos</option><option value="false">Fallidos</option><option value="true">Exitosos</option></select></div>
      <DataTable rows={attempts.data} columns={[{ key: "at", title: "Fecha", render: (r) => fmtDate(r.at) }, { key: "email", title: "Correo" },
        { key: "ip", title: "IP" }, { key: "success", title: "Resultado", render: (r) => <Badge value={r.success ? "ok" : "critical"} /> },
        { key: "reason", title: "Motivo", render: (r) => LOGIN_REASONS[r.reason] ?? r.reason ?? "" }]} />
      {detail && <Modal title={`${AUDIT_ACTIONS[detail.action] ?? detail.action} · ${detail.entity_type} ${detail.entity_id ?? ""}`} onClose={() => setDetail(null)}>
        <KeyValues data={detail} keys={[["at", "Fecha", fmtDate], ["user_name", "Usuario"], ["ip", "IP"], ["request_id", "Solicitud"], ["summary", "Detalle"]]} />
        {detail.changes && <div className="table-wrap"><table><thead><tr><th>Campo</th><th>Antes</th><th>Después</th></tr></thead>
          <tbody>{Object.entries(detail.changes).map(([k, v]) => (
            <tr key={k}><td>{k}</td>{Array.isArray(v) && v.length === 2
              ? <><td>{fmtValue(v[0])}</td><td>{fmtValue(v[1])}</td></> : <td colSpan={2}>{fmtValue(v)}</td>}</tr>))}</tbody></table></div>}
      </Modal>}
    </Page>
  );
}

function fmtValue(v: unknown) {
  if (v === null || v === undefined) return "—";
  return typeof v === "object" ? JSON.stringify(v) : String(v);
}

// ------------------------------------------------------------------ cambio de contraseña
export function ChangePasswordForm({ forced, onDone }: { forced?: boolean; onDone: () => void }) {
  const { me, login } = useSession();
  const [v, setV] = useState({ current: "", next: "", confirm: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (v.next !== v.confirm) return setError("La confirmación no coincide con la nueva contraseña");
    setBusy(true);
    setError(null);
    try {
      await post("/auth/change-password", { current_password: v.current, new_password: v.next });
      // El cambio revoca todas las sesiones, incluida esta: se ingresa de nuevo con la contraseña nueva.
      await login(me!.email, v.next);
      onDone();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form className="form" onSubmit={submit}>
      {forced && <Alert kind="warning">Su contraseña fue asignada por un administrador. Debe cambiarla para continuar.</Alert>}
      <div className="form-grid">
        <label><span>Contraseña actual *</span><input type="password" autoComplete="current-password" required value={v.current} onChange={(e) => setV({ ...v, current: e.target.value })} /></label>
        <label><span>Nueva contraseña *</span><input type="password" autoComplete="new-password" required value={v.next} onChange={(e) => setV({ ...v, next: e.target.value })} /></label>
        <label><span>Confirmar nueva contraseña *</span><input type="password" autoComplete="new-password" required value={v.confirm} onChange={(e) => setV({ ...v, confirm: e.target.value })} /></label>
      </div>
      <p className="muted">Mínimo 12 caracteres, con mayúsculas, minúsculas, un número y un símbolo. Al cambiarla se cierran sus otras sesiones.</p>
      <Alert>{error}</Alert>
      <button type="submit" disabled={busy}>{busy ? "Procesando…" : "Cambiar contraseña"}</button>
    </form>
  );
}
