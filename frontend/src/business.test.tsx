import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const post = vi.fn();
const responses: Record<string, unknown> = {
  "/trace/sales_order/5": { start: "sales_order:5", truncated: false, edges: [], nodes: [
    { key: "sales_quote:2", type: "sales_quote", id: 2, flow: "sales", stage: 1, allowed: true, is_start: false, label: "Cotización",
      number: "CT-000002", date: "2026-10-01", status: "accepted", amount: "100.00", currency: "COP", route: "/ventas/cotizaciones" },
    { key: "sales_order:5", type: "sales_order", id: 5, flow: "sales", stage: 2, allowed: true, is_start: true, label: "Pedido de venta",
      number: "PV-000005", date: "2026-10-02", status: "confirmed", amount: "100.00", currency: "COP", route: "/ventas/pedidos/5" },
    { key: "journal_entry:9", type: "journal_entry", id: 9, flow: "accounting", stage: 8, allowed: false, is_start: false,
      label: "Comprobante contable", number: null, route: null }] },
  "/sales/quotes/7": { id: 7, number: "CT-000007", status: "sent", customer_id: 3, quote_date: "2026-10-20", valid_until: "2099-01-01",
    currency: "COP", total: "500.00", lines: [] },
  "/warehouses": { items: [{ id: 4, name: "Bodega principal" }] },
  "/documents/sales_order/5/email-defaults": { to: ["compras@cliente.co"], subject: "Pedido de venta PV-000005 · DLCO",
    body: "Señores Cliente:" },
  "/documents/sales_order/5/emails": [{ id: 1, created_at: "2026-10-21T10:00:00Z", to_addresses: "compras@cliente.co",
    subject: "Pedido", status: "sent", sent_at: "2026-10-21T10:00:05Z" }],
  "/sales/quotes": { items: [{ id: 7, number: "CT-000007", status: "sent", customer_id: 3, total: "500.00", currency: "COP" }] },
};
vi.mock("./lib/api", () => ({
  get: (path: string) => Promise.resolve(path.startsWith("/trace/sales_quote") ? { nodes: [], edges: [] } : responses[path] ?? { items: [] }),
  post: (...args: unknown[]) => post(...args),
  qs: () => "",
  download: vi.fn(),
  put: vi.fn(),
  api: vi.fn(),
}));
vi.mock("./lib/session", () => ({
  useSession: () => ({ company: { id: 1 }, can: () => true, moduleOn: () => true }),
}));

import { DocumentActions } from "./components/DocumentActions";
import { DraftEditor, editableLines } from "./components/DraftEditor";
import { TracePanel } from "./components/TracePanel";
import { parseStatementLines } from "./pages/Accounting";
import { QuotesPage } from "./pages/Sales";

beforeEach(() => post.mockReset());

describe("Trazabilidad", () => {
  it("muestra la cadena por flujo y oculta los documentos sin permiso", async () => {
    render(<MemoryRouter><TracePanel type="sales_order" id={5} /></MemoryRouter>);
    expect(await screen.findByText("CT-000002")).toBeInTheDocument();
    expect(screen.getByText("PV-000005").closest("button")).toBeDisabled(); // el documento actual no navega
    expect(screen.getByText("Sin acceso")).toBeInTheDocument();
    expect(screen.getByText("Tesorería y contabilidad")).toBeInTheDocument();
  });
});

describe("Cotizaciones", () => {
  it("convierte la cotización en pedido con la bodega elegida", async () => {
    post.mockResolvedValue({ id: 31 });
    render(<MemoryRouter><QuotesPage /></MemoryRouter>);
    fireEvent.click(await screen.findByText("CT-000007"));
    fireEvent.click(await screen.findByText("Convertir en pedido"));
    const dialog = within(screen.getByRole("dialog", { name: "Convertir en pedido" }));
    await dialog.findByRole("option", { name: "Bodega principal" });
    fireEvent.change(dialog.getByLabelText(/Bodega de despacho/), { target: { value: "4" } });
    fireEvent.click(dialog.getByText("Guardar"));
    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post.mock.calls[0][0]).toBe("/sales/quotes/7/convert");
    expect(post.mock.calls[0][1]).toMatchObject({ warehouse_id: 4 });
  });
});

describe("Envío de documentos por correo", () => {
  it("propone el correo del tercero y envía varios destinatarios separados por coma", async () => {
    post.mockResolvedValue({ id: 2, status: "queued" });
    render(<DocumentActions type="sales_order" id={5} number="PV-000005" canSend />);
    fireEvent.click(screen.getByText("Enviar por correo"));
    const dialog = within(await screen.findByRole("dialog"));
    expect(await dialog.findByDisplayValue("compras@cliente.co")).toBeInTheDocument();
    expect(dialog.getByText("Entregado", { exact: false })).toBeInTheDocument();
    fireEvent.change(dialog.getByLabelText("Copia"), { target: { value: "ventas@datasys.co; gerencia@datasys.co" } });
    fireEvent.click(dialog.getByText("Enviar"));
    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post.mock.calls[0][0]).toBe("/documents/sales_order/5/email");
    expect(post.mock.calls[0][1]).toMatchObject({ to: ["compras@cliente.co"], cc: ["ventas@datasys.co", "gerencia@datasys.co"],
      subject: "Pedido de venta PV-000005 · DLCO" });
    expect(await dialog.findByText(/Envío en cola/)).toBeInTheDocument();
  });

  it("oculta el envío cuando el estado no lo permite y lo explica", () => {
    render(<DocumentActions type="purchase_order" id={9} number="OC-9" canSend={false} sendHint="Se envía una vez aprobada" />);
    expect(screen.queryByText("Enviar por correo")).not.toBeInTheDocument();
    expect(screen.getByText("Se envía una vez aprobada")).toBeInTheDocument();
  });
});

describe("Edición de borradores", () => {
  it("recalcula precios de lista y promociones, conserva lo digitado a mano", () => {
    const lines = editableLines([
      { item_id: 1, quantity: "2.000000", unit_price: "130.000000", discount_pct: "8.000000", price_source: "price_list", promotion_id: 4 },
      { item_id: 2, quantity: "1.000000", unit_price: "99.000000", discount_pct: "5.000000", price_source: "manual", promotion_id: null },
      { item_id: 3, quantity: "3.000000", unit_price: "50.000000", discount_pct: "0.000000", price_source: "quote", promotion_id: null }], true);
    expect(lines).toEqual([
      { item_id: "1", quantity: "2", unit_price: "", discount_pct: "" },
      { item_id: "2", quantity: "1", unit_price: "99", discount_pct: "5" },
      { item_id: "3", quantity: "3", unit_price: "50", discount_pct: "" }]);
    // Líneas anteriores a las listas de precios (sin origen): se conserva el precio pactado
    expect(editableLines([{ item_id: 9, quantity: "1", unit_price: "1000", discount_pct: "10", price_source: null }], true)[0])
      .toEqual({ item_id: "9", quantity: "1", unit_price: "1000", discount_pct: "10" });
    // En compras el precio siempre se conserva
    expect(editableLines([{ item_id: 7, quantity: "5", unit_price: "90" }], false)[0].unit_price).toBe("90");
  });

  it("envía encabezado y líneas juntos y exige al menos una línea", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<DraftEditor title="Editar pedido" sales onClose={vi.fn()} onSubmit={onSubmit}
      initial={{ notes: "Entregar en portería" }} fields={[{ name: "notes", label: "Notas" }]}
      lines={[{ item_id: "1", quantity: "4", unit_price: "", discount_pct: "" }]} />);
    fireEvent.click(screen.getByText("Guardar cambios"));
    await waitFor(() => expect(onSubmit).toHaveBeenCalled());
    expect(onSubmit.mock.calls[0][0]).toMatchObject({ notes: "Entregar en portería" });
    expect(onSubmit.mock.calls[0][1]).toEqual([{ item_id: 1, quantity: "4" }]); // sin precio ni descuento: se calculan
    fireEvent.click(screen.getByLabelText("Quitar línea"));
    fireEvent.click(screen.getByText("Guardar cambios"));
    expect(await screen.findByText("Agregue al menos una línea")).toBeInTheDocument();
  });
});

describe("Extracto bancario", () => {
  it("interpreta formatos local e internacional y descarta líneas inválidas", () => {
    const rows = parseStatementLines("2026-10-01;Consignación;RC-1;1.500.000,50\n2026-10-02\tPago\t\t-850000.25\nencabezado;x;y;z");
    expect(rows).toEqual([
      { txn_date: "2026-10-01", description: "Consignación", reference: "RC-1", amount: "1500000.50" },
      { txn_date: "2026-10-02", description: "Pago", reference: null, amount: "-850000.25" }]);
  });
});
