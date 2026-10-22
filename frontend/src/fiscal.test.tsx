import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const download = vi.fn();
const session = { country: "VE" };
const responses: Record<string, unknown> = {
  "/fiscal/ve/sales-book?start=2026-10-01&end=2026-10-22": {
    currency: "VES", warnings: ["NC2: sin número de control de la imprenta digital"],
    totals: { general_tax: "80.00", reduced_tax: "0.00", additional_tax: "0.00", withheld: "60.00" },
    rows: [
      { n: 1, date: "2026-10-22", kind: "invoice", rif: "J001241340", name: "Cliente Especial C.A.", invoice_number: "A1",
        control_number: "00-0001", total: "1160.00", exempt: "0.00", general_base: "1000.00", general_tax: "160.00",
        reduced_base: "0.00", reduced_tax: "0.00", withheld: "0.00", certificate: null },
      { n: 2, date: "2026-10-22", kind: "withholding", rif: "J001241340", name: "Cliente Especial C.A.", affected: "A1",
        total: "0.00", withheld: "60.00", certificate: "20261000000077" }] },
  "/fiscal/ve/vat-withholdings?start=2026-10-01&end=2026-10-22": [
    { certificate: "20261000000001", date: "2026-10-22", supplier: "Proveedor C.A.", rif: "J300000014",
      invoice_number: "F-101", control_number: "00-000101", vat: "160.00", rate: "75.000000", withheld: "120.00",
      status: "posted" }],
  "/fiscal/co/withholding-certificates?start=2026-10-01&end=2026-10-22&kind=income": [
    { party_id: 8, nit: "800000003", check_digit: "4", name: "Proveedor S.A.S.", base: "1000.00", amount: "25.00",
      lines: [{ code: "RTEC25" }] }],
};
vi.mock("./lib/api", () => ({
  get: (path: string) => Promise.resolve(responses[path] ?? { rows: [], items: [] }),
  download: (...args: unknown[]) => download(...args),
}));
vi.mock("./lib/session", () => ({
  useSession: () => ({ company: { id: 1, country: session.country, currency: "VES" }, can: () => true,
    moduleOn: () => true }),
}));

import { FiscalPage } from "./pages/Fiscal";

beforeEach(() => {
  download.mockReset().mockResolvedValue(undefined);
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date("2026-10-22T15:00:00Z"));
});

describe("Libros y reportes fiscales", () => {
  it("Venezuela: libro de ventas con avisos, retenciones y descarga del TXT de la quincena", async () => {
    session.country = "VE";
    render(<FiscalPage />);
    expect((await screen.findAllByText("Cliente Especial C.A.")).length).toBe(2);
    expect(screen.getByText(/sin número de control/)).toBeInTheDocument();
    expect(screen.getByText("Retención · A1")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Exportar a Excel"));
    expect(download).toHaveBeenCalledWith("/fiscal/ve/sales-book.xlsx?start=2026-10-01&end=2026-10-22", "libro_ventas.xlsx");

    fireEvent.click(screen.getByRole("tab", { name: "Retenciones de IVA" }));
    expect(await screen.findByText("20261000000001")).toBeInTheDocument();
    expect(screen.getByLabelText("Quincena")).toHaveValue("2"); // día 22: segunda quincena
    fireEvent.click(screen.getByText("Descargar TXT"));
    expect(download).toHaveBeenLastCalledWith("/fiscal/ve/vat-withholdings.txt?year=2026&month=10&half=2",
      "retenciones_iva_202610_q2.txt");
    fireEvent.click(screen.getByText("PDF"));
    expect(download).toHaveBeenLastCalledWith("/fiscal/ve/vat-withholdings/20261000000001/pdf",
      "comprobante_retencion_iva_20261000000001.pdf");
  });

  it("Colombia: certificados por tercero y tipo de retención", async () => {
    session.country = "CO";
    render(<FiscalPage />);
    expect(screen.queryByRole("tab", { name: "Libro de ventas" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "Certificados de retención" }));
    expect(await screen.findByText("800000003-4")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Certificado PDF"));
    expect(download).toHaveBeenCalledWith(
      "/fiscal/co/withholding-certificates/8/pdf?start=2026-10-01&end=2026-10-22&kind=income", "certificado_income_800000003.pdf");
  });
});
