import { useState } from "react";
import { TracePanel } from "../components/TracePanel";
import { Badge, DataTable, Page } from "../components/ui";
import { Json } from "../lib/api";
import { fmtDate, fmtMoney } from "../lib/format";
import { useFetch } from "../lib/hooks";

/** Búsqueda de cualquier documento por número y su cadena completa entre módulos. */
export function TracePage() {
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState<Json | null>(null);
  const term = q.trim();
  const { data } = useFetch<Json[]>(term.length >= 2 ? `/trace/search?q=${encodeURIComponent(term)}` : null);
  return (
    <Page title="Trazabilidad de documentos" subtitle="Del requerimiento o la cotización hasta el pago y su registro contable">
      <div className="filters">
        <label>Número de documento<input autoFocus placeholder="OC-000012, PV-000034, SETP990000001…" value={q}
          onChange={(e) => { setQ(e.target.value); setSelected(null); }} /></label>
      </div>
      {term.length >= 2 && !selected && <DataTable rows={data} empty="No se encontraron documentos con ese número"
        onRowClick={setSelected} columns={[{ key: "label", title: "Documento" }, { key: "number", title: "Número" },
          { key: "date", title: "Fecha", render: (r) => fmtDate(r.date) }, { key: "party", title: "Tercero", render: (r) => r.party ?? "—" },
          { key: "status", title: "Estado", render: (r) => r.status ? <Badge value={r.status} /> : "—" },
          { key: "amount", title: "Valor", align: "right", render: (r) => r.amount != null ? fmtMoney(r.amount, r.currency ?? undefined) : "—" }]} />}
      {selected && <>
        <h3>{selected.label} {selected.number}</h3>
        <button className="secondary" onClick={() => setSelected(null)}>← Volver a los resultados</button>
        <TracePanel type={selected.type} id={selected.id} />
      </>}
    </Page>
  );
}
