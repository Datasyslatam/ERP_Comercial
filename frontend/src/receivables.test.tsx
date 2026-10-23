import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const post = vi.fn();
const responses: Record<string, unknown> = {
  "/bank-accounts": { items: [{ id: 4, name: "Banco principal", currency: "COP" }] },
  "/taxes?active=true&limit=200": { items: [] },
  "/accounting/reconciliation?kind=receivable": { balanced: false, difference: "50.00", currency: "COP",
    parties_with_difference: 1, accounts: [{ label: "Cartera", account_code: "130505", gl: "326.00", subledger: "276.00" }],
    parties: [{ party_id: 3, party: "Cliente S.A.S.", gl: "326.00", subledger: "276.00", difference: "50.00" }] },
};
vi.mock("./lib/api", () => ({
  get: (path: string) => Promise.resolve(responses[path] ?? { items: [] }),
  post: (...args: unknown[]) => post(...args),
  download: vi.fn(),
}));
vi.mock("./lib/session", () => ({
  useSession: () => ({ company: { id: 1, country: "CO" }, can: () => true, moduleOn: () => true }),
}));

import { distribute, PaymentModal } from "./pages/Accounting";
import { Reconciliation } from "./pages/Receivables";

beforeEach(() => post.mockReset().mockResolvedValue({ id: 1 }));

describe("Cartera", () => {
  it("reparte lo aplicado por vencimiento y deja el excedente como anticipo", () => {
    const items = [{ open_item_id: 2, open_amount: "357.00", due_date: "2026-11-30" },
      { open_item_id: 1, open_amount: "476.00", due_date: "2026-11-01" }];
    expect(distribute(items, 600)).toEqual({ allocations: [{ open_item_id: 1, amount: "476.00" },
      { open_item_id: 2, amount: "124.00" }], advance: 0 });
    expect(distribute(items, 933.1).advance).toBeCloseTo(100.1);
  });

  it("paga varias facturas del mismo tercero en un solo recaudo", async () => {
    const done = vi.fn();
    render(<PaymentModal kind="receivable" onClose={vi.fn()} onDone={done} items={[
      { open_item_id: 1, party_id: 3, party: "Cliente S.A.S.", document: "SETP1", currency: "COP", open_amount: "476.00", due_date: "2026-11-01" },
      { open_item_id: 2, party_id: 3, party: "Cliente S.A.S.", document: "SETP2", currency: "COP", open_amount: "357.00", due_date: "2026-11-30" }]} />);
    expect(screen.getByText(/Recaudo de 2 documentos de Cliente S.A.S./)).toBeInTheDocument();
    await screen.findByRole("option", { name: /Banco principal/ });
    fireEvent.change(screen.getByLabelText(/Cuenta bancaria/), { target: { value: "4" } });
    expect(screen.getByLabelText(/Valor recibido en banco/)).toHaveValue(833);
    fireEvent.change(screen.getByLabelText(/Valor recibido en banco/), { target: { value: "933" } });
    fireEvent.click(screen.getByText("Guardar"));
    await waitFor(() => expect(done).toHaveBeenCalled());
    expect(post.mock.calls[0][1]).toMatchObject({ party_id: 3, currency: "COP", amount: "933",
      allocations: [{ open_item_id: 1, amount: "476.00" }, { open_item_id: 2, amount: "357.00" }] });
  });

  it("registra un anticipo sin facturas con la moneda de la cuenta bancaria", async () => {
    const done = vi.fn();
    render(<PaymentModal kind="payable" party={{ id: 8, name: "Proveedor Ltda." }} onClose={vi.fn()} onDone={done} />);
    expect(screen.getByText("Anticipo a Proveedor Ltda.")).toBeInTheDocument();
    expect(screen.queryByText("+ Retención")).not.toBeInTheDocument();
    await screen.findByRole("option", { name: /Banco principal/ });
    fireEvent.change(screen.getByLabelText(/Cuenta bancaria/), { target: { value: "4" } });
    fireEvent.change(screen.getByLabelText(/Valor del anticipo/), { target: { value: "300" } });
    fireEvent.click(screen.getByText("Guardar"));
    await waitFor(() => expect(done).toHaveBeenCalled());
    expect(post.mock.calls[0][1]).toMatchObject({ kind: "disbursement", party_id: 8, currency: "COP", amount: "300",
      allocations: [], withholdings: [] });
  });

  it("advierte la diferencia entre el auxiliar y la contabilidad con el detalle por tercero", async () => {
    render(<Reconciliation kind="receivable" />);
    expect(await screen.findByText(/Diferencia de 50,00 COP/)).toBeInTheDocument();
    fireEvent.click(screen.getByText("Ver terceros"));
    expect(screen.getByText(/Cliente S.A.S.: mayor 326,00/)).toBeInTheDocument();
  });
});
