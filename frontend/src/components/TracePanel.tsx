import { useNavigate } from "react-router-dom";
import { Json } from "../lib/api";
import { fmtDate, fmtMoney } from "../lib/format";
import { useFetch } from "../lib/hooks";
import { Alert, Badge } from "./ui";

const FLOWS: Record<string, string> = { purchasing: "Compras", sales: "Ventas", accounting: "Tesorería y contabilidad" };

/** Cadena documental de un documento (origen, documentos derivados, pagos y comprobantes contables). */
export function TracePanel({ type, id }: { type: string; id: number | string }) {
  const { data, error } = useFetch<Json>(`/trace/${type}/${id}`);
  const nav = useNavigate();
  if (error) return <Alert>{error}</Alert>;
  if (!data) return <p className="muted">Cargando trazabilidad…</p>;
  const flows = Object.keys(FLOWS).filter((f) => data.nodes.some((n: Json) => n.flow === f));
  return (
    <div className="trace">
      {flows.map((f) => (
        <div key={f} className="trace-flow">
          <h4>{FLOWS[f]}</h4>
          <ol className="trace-steps">
            {data.nodes.filter((n: Json) => n.flow === f).map((n: Json) => (
              <li key={n.key} className={`trace-node ${n.is_start ? "current" : ""} ${n.allowed ? "" : "restricted"}`}>
                <button type="button" className="trace-card" disabled={!n.route || n.is_start}
                        onClick={() => n.route && nav(n.route)} title={n.allowed ? n.detail ?? "" : "Sin permiso para consultar este documento"}>
                  <span className="trace-label">{n.label}</span>
                  {n.allowed ? <>
                    <strong>{n.number}</strong>
                    <span className="muted">{fmtDate(n.date)}{n.party ? ` · ${n.party}` : ""}</span>
                    <span className="row">{n.status && <Badge value={n.status} />}
                      {n.amount != null && <span className="trace-amount">{fmtMoney(n.amount, n.currency ?? undefined)}</span>}</span>
                    {n.detail && <span className="muted trace-detail">{n.detail}</span>}
                  </> : <span className="muted">Sin acceso</span>}
                </button>
              </li>
            ))}
          </ol>
        </div>
      ))}
      {data.truncated && <p className="muted">La cadena es muy extensa; se muestran los primeros documentos.</p>}
    </div>
  );
}
