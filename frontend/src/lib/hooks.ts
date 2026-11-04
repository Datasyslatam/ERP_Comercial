import { useCallback, useEffect, useRef, useState } from "react";
import { get, Json } from "./api";
import { useSession } from "./session";

/** Carga un recurso GET y lo recarga al cambiar la ruta o la empresa activa. */
export function useFetch<T = Json>(path: string | null) {
  const { company } = useSession();
  // Los datos quedan atados a su ruta: al cambiarla, una pantalla nunca recibe la forma de la consulta anterior.
  const [state, setState] = useState<{ path: string | null; value: T | null }>({ path, value: null });
  const latest = useRef(path);
  latest.current = path;
  const data = state.path === path ? state.value : null;
  const setData = useCallback((value: T | null) => setState({ path, value }), [path]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const reload = useCallback(() => {
    if (!path) return;
    setLoading(true);
    setError(null);
    get<T>(path)
      .then((value) => { if (latest.current === path) setState({ path, value }); })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [path]);
  useEffect(() => {
    reload();
  }, [reload, company?.id]);
  return { data, error, loading, reload, setData };
}

/** Los listados llegan paginados ({ items }) o como lista simple, por ejemplo las unidades de medida. */
type ListResponse = { items: Json[] } | Json[];
const rowsOf = (data: ListResponse | null) => (Array.isArray(data) ? data : data?.items ?? []);

/** Diccionario id → etiqueta para mostrar nombres en lugar de identificadores en las tablas. */
export function useLookup(path: string | null, labelOf: (x: Json) => string) {
  const { data } = useFetch<ListResponse>(path);
  const map = new Map<number, string>(rowsOf(data).map((x) => [x.id as number, labelOf(x)]));
  return (id: unknown) => (id === null || id === undefined || id === "" ? "—" : map.get(Number(id)) ?? `#${id}`);
}

/** Nombres de artículos (SKU · descripción), el caso más frecuente. */
export function useItemNames() {
  return useLookup("/items?limit=500", (x) => `${x.sku} · ${x.name}`);
}

/** Opciones para selects a partir de un listado paginado de maestros. */
export function useOptions(path: string | null, labelOf: (x: Json) => string) {
  const { data } = useFetch<ListResponse>(path);
  return rowsOf(data).map((x) => ({ value: x.id as number, label: labelOf(x) }));
}
