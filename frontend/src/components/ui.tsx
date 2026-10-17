import { FormEvent, ReactNode, useState } from "react";
import { Json } from "../lib/api";
import { label } from "../lib/format";

export function Page({ title, actions, children, subtitle }: {
  title: string; subtitle?: string; actions?: ReactNode; children: ReactNode;
}) {
  return (
    <section className="page">
      <header className="page-head">
        <div>
          <h1>{title}</h1>
          {subtitle && <p className="muted">{subtitle}</p>}
        </div>
        <div className="row">{actions}</div>
      </header>
      {children}
    </section>
  );
}

export function Badge({ value }: { value: unknown }) {
  const v = String(value ?? "");
  return <span className={`badge badge-${v}`}>{label(v)}</span>;
}

export function Alert({ kind = "error", children }: { kind?: "error" | "info" | "warning" | "ok"; children: ReactNode }) {
  if (!children) return null;
  return <div className={`alert alert-${kind}`} role={kind === "error" ? "alert" : "status"}>{children}</div>;
}

export interface Column<T = Json> {
  key: string;
  title: string;
  render?: (row: T) => ReactNode;
  align?: "right" | "left";
}

export function DataTable({ columns, rows, onRowClick, empty = "Sin registros" }: {
  columns: Column[]; rows: Json[] | undefined | null; onRowClick?: (r: Json) => void; empty?: string;
}) {
  if (!rows) return <p className="muted">Cargando…</p>;
  if (!rows.length) return <p className="muted">{empty}</p>;
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>{columns.map((c) => <th key={c.key} className={c.align === "right" ? "num" : ""}>{c.title}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.id ?? i} onClick={onRowClick ? () => onRowClick(r) : undefined}
                className={onRowClick ? "clickable" : ""}>
              {columns.map((c) => (
                <td key={c.key} className={c.align === "right" ? "num" : ""}>
                  {c.render ? c.render(r) : String(r[c.key] ?? "—")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export type FieldType = "text" | "number" | "date" | "select" | "checkbox" | "textarea" | "email";

export interface Field {
  name: string;
  label: string;
  type?: FieldType;
  required?: boolean;
  options?: { value: string | number; label: string }[];
  step?: string;
  placeholder?: string;
}

/** Formulario controlado; envía solo los campos con valor y convierte selects numéricos. */
export function Form({ fields, initial, onSubmit, submitLabel = "Guardar", onCancel }: {
  fields: Field[]; initial?: Json; onSubmit: (data: Json) => Promise<void>; submitLabel?: string;
  onCancel?: () => void;
}) {
  const [values, setValues] = useState<Json>(initial ?? {});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: string, v: unknown) => setValues((s: Json) => ({ ...s, [k]: v }));

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const out: Json = {};
    for (const f of fields) {
      const v = values[f.name];
      if (f.type === "checkbox") out[f.name] = !!v;
      else if (v !== undefined && v !== "" && v !== null) {
        out[f.name] = f.type === "select" && f.options?.length && typeof f.options[0].value === "number" ? Number(v) : v;
      }
    }
    try {
      await onSubmit(out);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="form" onSubmit={submit}>
      <div className="form-grid">
        {fields.map((f) => (
          <label key={f.name} className={f.type === "textarea" ? "span-2" : f.type === "checkbox" ? "check" : ""}>
            {f.type === "checkbox" ? (
              <>
                <input type="checkbox" checked={!!values[f.name]} onChange={(e) => set(f.name, e.target.checked)} />
                {f.label}
              </>
            ) : (
              <>
                <span>{f.label}{f.required && " *"}</span>
                {f.type === "select" ? (
                  <select required={f.required} value={values[f.name] ?? ""} onChange={(e) => set(f.name, e.target.value)}>
                    <option value="">—</option>
                    {f.options?.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                ) : f.type === "textarea" ? (
                  <textarea required={f.required} value={values[f.name] ?? ""} onChange={(e) => set(f.name, e.target.value)} />
                ) : (
                  <input type={f.type ?? "text"} step={f.step ?? (f.type === "number" ? "any" : undefined)}
                         required={f.required} placeholder={f.placeholder} value={values[f.name] ?? ""}
                         onChange={(e) => set(f.name, e.target.value)} />
                )}
              </>
            )}
          </label>
        ))}
      </div>
      <Alert>{error}</Alert>
      <div className="row">
        <button type="submit" disabled={busy}>{busy ? "Procesando…" : submitLabel}</button>
        {onCancel && <button type="button" className="secondary" onClick={onCancel}>Cancelar</button>}
      </div>
    </form>
  );
}

/** Botón que ejecuta una acción de negocio y muestra el error devuelto por la API. */
export function ActionButton({ children, onClick, confirm: confirmMsg, className }: {
  children: ReactNode; onClick: () => Promise<unknown>; confirm?: string; className?: string;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return (
    <span className="action">
      <button className={className} disabled={busy} onClick={async () => {
        if (confirmMsg && !window.confirm(confirmMsg)) return;
        setBusy(true);
        setError(null);
        try {
          await onClick();
        } catch (e) {
          setError((e as Error).message);
        } finally {
          setBusy(false);
        }
      }}>{busy ? "…" : children}</button>
      {error && <span className="error-inline" role="alert">{error}</span>}
    </span>
  );
}

export function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  return (
    <div className="modal-bg" onClick={onClose}>
      <div className="modal" role="dialog" aria-label={title} onClick={(e) => e.stopPropagation()}>
        <header className="row between"><h2>{title}</h2><button className="secondary" onClick={onClose}>✕</button></header>
        {children}
      </div>
    </div>
  );
}

export function KeyValues({ data, keys }: { data: Json; keys: [string, string, ((v: Json) => ReactNode)?][] }) {
  return (
    <dl className="kv">
      {keys.map(([k, title, render]) => (
        <div key={k}><dt>{title}</dt><dd>{render ? render(data?.[k]) : String(data?.[k] ?? "—")}</dd></div>
      ))}
    </dl>
  );
}
