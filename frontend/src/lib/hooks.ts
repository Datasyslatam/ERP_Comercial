import { useCallback, useEffect, useState } from "react";
import { get, Json } from "./api";
import { useSession } from "./session";

/** Carga un recurso GET y lo recarga al cambiar la ruta o la empresa activa. */
export function useFetch<T = Json>(path: string | null) {
  const { company } = useSession();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const reload = useCallback(() => {
    if (!path) return;
    setLoading(true);
    setError(null);
    get<T>(path)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [path]);
  useEffect(() => {
    reload();
  }, [reload, company?.id]);
  return { data, error, loading, reload, setData };
}

/** Opciones para selects a partir de un listado paginado de maestros. */
export function useOptions(path: string | null, labelOf: (x: Json) => string) {
  const { data } = useFetch<{ items: Json[] }>(path);
  return (data?.items ?? []).map((x) => ({ value: x.id as number, label: labelOf(x) }));
}
