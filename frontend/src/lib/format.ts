// Formato de cifras: los importes llegan como texto decimal desde la API (sin pérdida de precisión).

export function num(v: unknown): number | null {
  if (v === null || v === undefined || v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

export function fmtNumber(v: unknown, digits = 2): string {
  const n = num(v);
  if (n === null) return "—";
  return n.toLocaleString("es-CO", { minimumFractionDigits: 0, maximumFractionDigits: digits });
}

export function fmtMoney(v: unknown, currency?: string): string {
  const n = num(v);
  if (n === null) return "—";
  return `${n.toLocaleString("es-CO", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}${currency ? " " + currency : ""}`;
}

export function fmtDate(v: unknown): string {
  if (!v) return "—";
  const s = String(v);
  return s.length > 10 ? new Date(s).toLocaleString("es-CO") : s;
}

export const STATUS_LABELS: Record<string, string> = {
  draft: "Borrador", submitted: "Enviada", approved: "Aprobada", rejected: "Rechazada", cancelled: "Anulada",
  ordered: "Ordenada", partially_received: "Recibida parcial", received: "Recibida", closed: "Cerrada",
  posted: "Contabilizado", confirmed: "Confirmado", partially_dispatched: "Despachado parcial",
  dispatched: "Despachado", picking: "En preparación", picked: "Preparado", packed: "Empacado", shipped: "Enviado",
  delivered: "Entregado", partially_delivered: "Entrega parcial", issued: "Emitida", pending: "Pendiente",
  sent: "Enviada", accepted: "Aceptada", error: "Error", open: "Abierta", partial: "Parcial", paid: "Pagada",
  released: "Liberada", in_progress: "En proceso", completed: "Terminada", quarantine: "Cuarentena",
  blocked: "Bloqueado", analysis: "Análisis", action: "Acción", verification: "Verificación", reversed: "Reversado",
  ok: "En meta", warning: "Alerta", critical: "Crítico", no_target: "Sin meta", no_data: "Sin datos",
  validated: "Validado", imported: "Importado", partially_imported: "Importado parcial", failed: "Fallido",
  valid: "Válida", invalid: "Inválida", acknowledged: "Atendida", active: "Activo", inactive: "Inactivo",
  locked: "Bloqueado", expired: "Vencido", pending_password: "Cambio de clave pendiente", queued: "En cola",
};

export const label = (s: unknown) => STATUS_LABELS[String(s)] ?? String(s ?? "—");
