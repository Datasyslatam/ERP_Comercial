import { useState } from "react";
import { download, Json, post } from "../lib/api";
import { fmtDate } from "../lib/format";
import { useFetch } from "../lib/hooks";
import { Alert, DataTable } from "./ui";

/** Soportes de un documento (por ejemplo, la entrega firmada). El servidor valida tamaño, tipo y permisos. */
export function Attachments({ entity, id, canAdd }: { entity: string; id: number; canAdd: boolean }) {
  const { data, reload } = useFetch<Json[]>(`/attachments?entity_type=${entity}&entity_id=${id}`);
  const [error, setError] = useState<string | null>(null);
  const upload = async (file: File | undefined) => {
    if (!file) return;
    setError(null);
    const body = new FormData();
    body.append("entity_type", entity);
    body.append("entity_id", String(id));
    body.append("file", file);
    try {
      await post("/attachments", body);
      reload();
    } catch (e) {
      setError((e as Error).message);
    }
  };
  return (
    <>
      <h3>Adjuntos</h3>
      <Alert>{error}</Alert>
      <DataTable rows={data} empty="Sin adjuntos" columns={[{ key: "filename", title: "Archivo" },
        { key: "created_at", title: "Fecha", render: (r) => fmtDate(r.created_at) },
        { key: "a", title: "", render: (r) => <button className="secondary" onClick={() => download(`/attachments/${r.id}/content`, r.filename)}>Descargar</button> }]} />
      {canAdd && <label>Agregar archivo <input aria-label="Agregar archivo" type="file" onChange={(e) => { upload(e.target.files?.[0]); e.target.value = ""; }} /></label>}
    </>
  );
}
