import { useState } from "react";
import { download, Json, patch, post, qs } from "../lib/api";
import { useFetch } from "../lib/hooks";
import { useSession } from "../lib/session";
import { Column, DataTable, Field, Form, Modal, Page } from "./ui";

/** Página genérica de datos maestros: listado con búsqueda, alta, edición, desactivación y exportación. */
export function ResourcePage({ title, path, columns, fields, writePerm, exportPerm, subtitle }: {
  title: string; path: string; columns: Column[]; fields: Field[]; writePerm: string; exportPerm?: string;
  subtitle?: string;
}) {
  const { can } = useSession();
  const [q, setQ] = useState("");
  const [editing, setEditing] = useState<Json | null>(null);
  const { data, error, reload } = useFetch<{ items: Json[]; total: number }>(`${path}${qs({ q, limit: 200 })}`);
  const canWrite = can(writePerm);

  return (
    <Page title={title} subtitle={subtitle} actions={<>
      <input type="search" placeholder="Buscar…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Buscar" />
      {exportPerm && can(exportPerm) && (
        <button className="secondary" onClick={() => download(`${path}/export.csv${qs({ q })}`, `${title}.csv`)}>
          Exportar CSV</button>)}
      {canWrite && <button onClick={() => setEditing({})}>Nuevo</button>}
    </>}>
      {error && <div className="alert alert-error">{error}</div>}
      <p className="muted">{data ? `${data.total} registros` : ""}</p>
      <DataTable columns={columns} rows={data?.items} onRowClick={canWrite ? (r) => setEditing(r) : undefined} />
      {editing && (
        <Modal title={editing.id ? `Editar ${title.toLowerCase()}` : `Nuevo registro`} onClose={() => setEditing(null)}>
          <Form fields={fields} initial={editing} onCancel={() => setEditing(null)} onSubmit={async (d) => {
            if (editing.id) await patch(`${path}/${editing.id}`, d);
            else await post(path, d);
            setEditing(null);
            reload();
          }} />
        </Modal>
      )}
    </Page>
  );
}
