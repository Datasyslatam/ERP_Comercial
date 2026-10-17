// Cliente HTTP: token de acceso en memoria, refresh token en sessionStorage (se borra al cerrar la pestaña),
// cabecera X-Company-Id y renovación automática ante un 401.

export type Json = any; // eslint-disable-line @typescript-eslint/no-explicit-any

export class ApiError extends Error {
  status: number;
  details: Json;
  constructor(status: number, message: string, details?: Json) {
    super(message);
    this.status = status;
    this.details = details;
  }
}

const BASE = (import.meta.env.VITE_API_URL ?? "") + "/api/v1";
let accessToken: string | null = null;
let companyId: number | null = null;
const RT_KEY = "erp.rt";

export function setCompany(id: number | null) {
  companyId = id;
}
export function getCompany() {
  return companyId;
}
export function hasSession() {
  return !!sessionStorage.getItem(RT_KEY);
}

export async function login(email: string, password: string) {
  const r = await fetch(`${BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const body = await r.json();
  if (!r.ok) throw new ApiError(r.status, body?.error?.message ?? "Error de autenticación");
  accessToken = body.access_token;
  sessionStorage.setItem(RT_KEY, body.refresh_token);
}

// Una sola renovación en vuelo: el servidor rota el refresh token y trata la reutilización como robo,
// así que peticiones concurrentes deben compartir la misma renovación.
let inflight: Promise<boolean> | null = null;

function refresh(): Promise<boolean> {
  if (!inflight) inflight = doRefresh().finally(() => { inflight = null; });
  return inflight;
}

async function doRefresh(): Promise<boolean> {
  const rt = sessionStorage.getItem(RT_KEY);
  if (!rt) return false;
  const r = await fetch(`${BASE}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: rt }),
  });
  if (!r.ok) {
    sessionStorage.removeItem(RT_KEY);
    return false;
  }
  const body = await r.json();
  accessToken = body.access_token;
  sessionStorage.setItem(RT_KEY, body.refresh_token);
  return true;
}

export async function logout() {
  const rt = sessionStorage.getItem(RT_KEY);
  sessionStorage.removeItem(RT_KEY);
  accessToken = null;
  if (rt) {
    await fetch(`${BASE}/auth/logout`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: rt }),
    }).catch(() => undefined);
  }
}

async function raw(method: string, path: string, body?: Json, retry = true): Promise<Response> {
  if (!accessToken && retry) await refresh();
  const headers: Record<string, string> = {};
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  if (companyId) headers["X-Company-Id"] = String(companyId);
  let payload: BodyInit | undefined;
  if (body instanceof FormData) payload = body;
  else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  const r = await fetch(`${BASE}${path}`, { method, headers, body: payload });
  if (r.status === 401 && retry && (await refresh())) return raw(method, path, body, false);
  return r;
}

export async function api<T = Json>(method: string, path: string, body?: Json): Promise<T> {
  const r = await raw(method, path, body);
  if (r.status === 204) return undefined as T;
  const ct = r.headers.get("content-type") ?? "";
  const data = ct.includes("json") ? await r.json() : await r.text();
  if (!r.ok) {
    const err = (data as Json)?.error;
    const fieldErrors = err?.details?.errors?.map((e: Json) => `${e.loc.slice(1).join(".")}: ${e.msg}`).join("; ");
    throw new ApiError(r.status, fieldErrors || err?.message || `Error ${r.status}`, err?.details);
  }
  return data as T;
}

export const get = <T = Json>(p: string) => api<T>("GET", p);
export const post = <T = Json>(p: string, b?: Json) => api<T>("POST", p, b ?? {});
export const put = <T = Json>(p: string, b?: Json) => api<T>("PUT", p, b);
export const patch = <T = Json>(p: string, b?: Json) => api<T>("PATCH", p, b);

/** Descarga un archivo autenticado (CSV, XML, plantillas). */
export async function download(path: string, filename: string) {
  const r = await raw("GET", path);
  if (!r.ok) throw new ApiError(r.status, "No se pudo descargar el archivo");
  const blob = await r.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function qs(params: Record<string, string | number | boolean | null | undefined>) {
  const s = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") s.set(k, String(v));
  });
  const out = s.toString();
  return out ? `?${out}` : "";
}
