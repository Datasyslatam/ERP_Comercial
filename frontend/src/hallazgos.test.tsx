import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

// Regresión de H-01, H-13, H-53, H-62 y H-66: lo que la pantalla muestra y envía.
const post = vi.fn();
const api = vi.fn();
const responses: Record<string, unknown> = {};
vi.mock("./lib/api", () => ({
  get: (path: string) => Promise.resolve(path in responses ? responses[path] : { items: [] }),
  post: (...args: unknown[]) => post(...args),
  api: (...args: unknown[]) => api(...args),
  put: vi.fn(),
  patch: vi.fn(),
  qs: () => "",
  download: vi.fn(),
}));
vi.mock("./lib/session", () => ({
  useSession: () => ({ company: { id: 1 }, can: () => true, moduleOn: () => true }),
}));

import { ErrorBoundary } from "./components/ErrorBoundary";
import { useFetch, useOptions } from "./lib/hooks";
import { EntriesPage, PeriodsPage, ReportsPage } from "./pages/Accounting";

beforeEach(() => {
  post.mockReset().mockResolvedValue({ id: 99 });
  api.mockReset().mockResolvedValue(undefined);
  window.confirm = () => true;
  for (const k of Object.keys(responses)) delete responses[k];
});

describe("Listas de opciones (H-13)", () => {
  function Options({ path }: { path: string }) {
    const options = useOptions(path, (x) => x.code);
    return <ul>{options.map((o) => <li key={o.value}>{o.label}</li>)}</ul>;
  }

  it("acepta una lista simple, como la de unidades de medida", async () => {
    responses["/uoms"] = [{ id: 1, code: "UND" }];
    render(<Options path="/uoms" />);
    expect(await screen.findByText("UND")).toBeTruthy();
  });

  it("sigue aceptando listados paginados", async () => {
    responses["/sites"] = { items: [{ id: 2, code: "SEDE" }] };
    render(<Options path="/sites" />);
    expect(await screen.findByText("SEDE")).toBeTruthy();
  });
});

describe("Cambio de consulta (H-66)", () => {
  it("no entrega los datos de la ruta anterior", async () => {
    responses["/a"] = { value: "de A" };
    responses["/b"] = { value: "de B" };
    function Show() {
      const [path, setPath] = useState("/a");
      const { data } = useFetch<{ value: string }>(path);
      return <button onClick={() => setPath("/b")}>{data ? data.value : "sin datos"}</button>;
    }
    render(<Show />);
    fireEvent.click(await screen.findByText("de A"));
    expect(screen.getByText("sin datos")).toBeTruthy();
    expect(await screen.findByText("de B")).toBeTruthy();
  });

  it("muestra el Estado de resultados al elegirlo en la lista", async () => {
    responses["/accounts?limit=500"] = { items: [] };
    for (const key of Object.keys(responses)) void key;
    const trial = { balanced: true, total_debit: "0", total_credit: "0", rows: [] };
    const income = { sections: { revenue: [], cost: [], expense: [] }, gross_profit: "5", net_income: "3" };
    const today = new Date().toISOString().slice(0, 10);
    const start = today.slice(0, 8) + "01";
    responses[`/accounting/reports/trial-balance?start=${start}&end=${today}`] = trial;
    responses[`/accounting/reports/income-statement?start=${start}&end=${today}`] = income;
    render(<MemoryRouter><ReportsPage /></MemoryRouter>);
    await screen.findByText(/Débitos/);
    fireEvent.change(screen.getByLabelText("Reporte"), { target: { value: "income-statement" } });
    expect(await screen.findByText(/Utilidad bruta/)).toBeTruthy();
  });

  it("una pantalla que falla no deja la aplicación en blanco", () => {
    const silence = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const Broken = (): JSX.Element => { throw new Error("fallo"); };
    render(<ErrorBoundary><Broken /></ErrorBoundary>);
    expect(screen.getByRole("alert").textContent).toContain("Esta pantalla encontró un error");
    silence.mockRestore();
  });
});

describe("Periodos contables (H-01)", () => {
  it("permite abrir un año que no existe", async () => {
    const year = new Date().getFullYear();
    responses[`/accounting/periods?year=${year}`] = [{ month: 1, year, status: "open", start_date: "", end_date: "" }];
    responses[`/accounting/periods?year=${year + 1}`] = [];
    render(<PeriodsPage />);
    fireEvent.change(await screen.findByLabelText("Año"), { target: { value: String(year + 1) } });
    fireEvent.click(await screen.findByRole("button", { name: `Abrir año ${year + 1}` }));
    await waitFor(() => expect(post).toHaveBeenCalledWith("/accounting/periods/open-year", { year: year + 1, month: 1 }));
  });
});

describe("Comprobantes (H-62)", () => {
  it("permite descartar un borrador sin abrir su detalle", async () => {
    responses["/accounting/entries?limit=100"] = { items: [{ id: 7, number: "BR-1", status: "draft", description: "x", total_debit: "0" }] };
    render(<EntriesPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Descartar" }));
    await waitFor(() => expect(api).toHaveBeenCalledWith("DELETE", "/accounting/entries/7"));
    expect(document.querySelector(".modal")).toBeNull();
  });
});
