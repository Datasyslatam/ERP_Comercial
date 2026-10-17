import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DataTable, Form } from "./components/ui";
import { fmtMoney, fmtNumber, label } from "./lib/format";
import { qs } from "./lib/api";

describe("formato", () => {
  it("no inventa cifras: valores nulos se muestran como guion", () => {
    expect(fmtNumber(null)).toBe("—");
    expect(fmtMoney(undefined)).toBe("—");
    expect(fmtMoney("1285.20", "COP")).toContain("COP");
  });
  it("traduce estados", () => {
    expect(label("no_data")).toBe("Sin datos");
    expect(label("accepted")).toBe("Aceptada");
  });
  it("construye query strings omitiendo vacíos", () => {
    expect(qs({ a: 1, b: "", c: null, d: "x" })).toBe("?a=1&d=x");
    expect(qs({})).toBe("");
  });
});

describe("componentes", () => {
  it("tabla vacía muestra mensaje", () => {
    render(<DataTable rows={[]} columns={[{ key: "x", title: "X" }]} empty="Nada" />);
    expect(screen.getByText("Nada")).toBeInTheDocument();
  });

  it("formulario envía valores tipados y muestra errores de la API", async () => {
    const submit = vi.fn().mockRejectedValueOnce(new Error("Dígito de verificación del NIT incorrecto"))
      .mockResolvedValueOnce(undefined);
    render(<Form fields={[{ name: "code", label: "Código", required: true },
      { name: "site_id", label: "Sede", type: "select", options: [{ value: 7, label: "Principal" }] },
      { name: "active", label: "Activo", type: "checkbox" }]} onSubmit={submit} />);
    fireEvent.change(screen.getByLabelText(/Código/), { target: { value: "C1" } });
    fireEvent.change(screen.getByLabelText(/Sede/), { target: { value: "7" } });
    fireEvent.click(screen.getByText("Guardar"));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("NIT incorrecto"));
    expect(submit).toHaveBeenCalledWith({ code: "C1", site_id: 7, active: false });
  });
});
