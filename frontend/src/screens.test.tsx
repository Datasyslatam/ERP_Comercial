import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// La API y la sesión se sustituyen por dobles: estas pruebas validan lo que la pantalla envía.
const post = vi.fn();
const responses: Record<string, unknown> = {
  "/bank-accounts": { items: [{ id: 4, name: "Banco principal", currency: "COP" }] },
  "/taxes?active=true&limit=200": { items: [
    { id: 5, code: "RTEC25", name: "Retención compras", kind: "withholding_income", rate: "2.5", applies_to: "both" },
    { id: 6, code: "IVA19", name: "IVA 19%", kind: "vat", rate: "19", applies_to: "both" }] },
  "/items?limit=500": { items: [{ id: 7, sku: "ART-A", name: "Artículo A" }] },
  "/einvoicing/correction-codes": { credit_note: { "1": "Devolución parcial", "3": "Rebaja o descuento" },
    debit_note: { "1": "Intereses" } },
};
vi.mock("./lib/api", () => ({
  get: (path: string) => Promise.resolve(responses[path] ?? { items: [] }),
  post: (...args: unknown[]) => post(...args),
  qs: () => "",
  download: vi.fn(),
}));
vi.mock("./lib/session", () => ({
  useSession: () => ({ company: { id: 1 }, can: () => true, moduleOn: () => true }),
}));

import { PaymentModal } from "./pages/Accounting";
import { NoteModal } from "./pages/Invoicing";

beforeEach(() => post.mockReset().mockResolvedValue({ id: 99 }));

describe("Recaudo con retenciones", () => {
  it("calcula la retención y aplica a la partida el valor recibido más lo retenido", async () => {
    const done = vi.fn();
    render(<PaymentModal kind="receivable" onClose={vi.fn()} onDone={done}
      item={{ open_item_id: 11, party_id: 3, document: "SETP1", currency: "COP", open_amount: "1000.00" }} />);
    fireEvent.click(screen.getByText("+ Retención"));
    await screen.findByRole("option", { name: /RTEC25/ });
    expect(screen.queryByRole("option", { name: /IVA19/ })).not.toBeInTheDocument(); // solo retenciones
    fireEvent.change(screen.getByLabelText("Retención"), { target: { value: "5" } });
    fireEvent.change(screen.getByLabelText("Base"), { target: { value: "1000" } });
    fireEvent.click(screen.getByText("Calcular"));
    expect(screen.getByLabelText("Valor retenido")).toHaveValue(25);
    await screen.findByRole("option", { name: /Banco principal/ });
    fireEvent.change(screen.getByLabelText(/Cuenta bancaria/), { target: { value: "4" } });
    fireEvent.change(screen.getByLabelText(/Valor recibido en banco/), { target: { value: "975" } });
    fireEvent.click(screen.getByText("Guardar"));
    await waitFor(() => expect(done).toHaveBeenCalled());
    const [path, body] = post.mock.calls[0];
    expect(path).toBe("/accounting/payments");
    expect(body).toMatchObject({
      kind: "receipt", party_id: 3, bank_account_id: 4, amount: "975", currency: "COP",
      withholdings: [{ tax_id: 5, base: "1000", amount: "25.00" }],
      allocations: [{ open_item_id: 11, amount: "1000.00" }],
    });
    expect(body.idempotency_key).toMatch(/^ui-11-/);
  });

  it("un pago a proveedor no ofrece retenciones", () => {
    render(<PaymentModal kind="payable" onClose={vi.fn()} onDone={vi.fn()}
      item={{ open_item_id: 2, party_id: 3, document: "FE-1", currency: "COP", open_amount: "10" }} />);
    expect(screen.queryByText("+ Retención")).not.toBeInTheDocument();
  });
});

describe("Notas crédito y débito", () => {
  const invoice = { id: 9, full_number: "SETP990000000", lines: [{ id: 3, item_id: 7, quantity: "5", unit_price: "100" }] };

  it("envía la nota crédito con concepto, motivo y líneas", async () => {
    const created = vi.fn();
    render(<NoteModal invoice={invoice} itemName={() => "ART-A · Artículo A"} onClose={vi.fn()} onCreated={created} />);
    await screen.findByRole("option", { name: /Devolución parcial/ });
    fireEvent.change(screen.getByLabelText(/Concepto de corrección/), { target: { value: "1" } });
    fireEvent.change(screen.getByLabelText(/Motivo/), { target: { value: "Devolución de 2 unidades" } });
    fireEvent.change(screen.getByLabelText(/cantidad \(facturado 5\)/), { target: { value: "2" } });
    fireEvent.click(screen.getByText("Crear nota en borrador"));
    await waitFor(() => expect(created).toHaveBeenCalledWith({ id: 99 }));
    expect(post).toHaveBeenCalledWith("/einvoicing/invoices/9/notes", {
      doc_type: "credit_note", correction_code: "1", reason: "Devolución de 2 unidades",
      lines: [{ invoice_line_id: 3, quantity: "2", unit_price: "100" }],
    });
  });

  it("exige al menos una línea y muestra los conceptos de la nota débito", async () => {
    render(<NoteModal invoice={invoice} itemName={() => "ART-A"} onClose={vi.fn()} onCreated={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Tipo de nota"), { target: { value: "debit_note" } });
    await screen.findByRole("option", { name: /Intereses/ });
    fireEvent.change(screen.getByLabelText(/Concepto de corrección/), { target: { value: "1" } });
    fireEvent.change(screen.getByLabelText(/Motivo/), { target: { value: "Intereses de mora" } });
    fireEvent.click(screen.getByText("Crear nota en borrador"));
    expect(await screen.findByRole("alert")).toHaveTextContent("al menos una línea");
    expect(post).not.toHaveBeenCalled();
  });
});
