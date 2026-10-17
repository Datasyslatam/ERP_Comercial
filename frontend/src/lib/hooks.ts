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

/** Diccionario id → etiqueta para mostrar nombres en lugar de identificadores en las tablas. */
export function useLookup(path: string | null, labelOf: (x: Json) => string) {
  const { data } = useFetch<{ items: Json[] }>(path);
  const map = new Map<number, string>((data?.items ?? []).map((x) => [x.id as number, labelOf(x)]));
  return (id: unknown) => (id === null || id === undefined || id === "" ? "—" : map.get(Number(id)) ?? `#${id}`);
}

/** Nombres de artículos (SKU · descripción), el caso más frecuente. */
export function useItemNames() {
  return useLookup("/items?limit=500", (x) => `${x.sku} · ${x.name}`);
}

/** Opciones para selects a partir de un listado paginado de maestros. */
export function useOptions(path: string | null, labelOf: (x: Json) => string) {
  const { data } = useFetch<{ items: Json[] }>(path);
  return (data?.items ?? []).map((x) => ({ value: x.id as number, label: labelOf(x) }));
}
