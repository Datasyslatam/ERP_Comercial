import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

vi.mock("./lib/session", () => ({
  useSession: () => ({
    me: { full_name: "Ana", companies: [{ id: 1, code: "CO1", name: "Empresa", country: "CO" }] },
    company: { id: 1 }, selectCompany: vi.fn(), logout: vi.fn(), can: () => true, moduleOn: () => true,
  }),
}));

import { Layout, sectionOf } from "./components/Layout";

const renderAt = (path: string) => render(<MemoryRouter initialEntries={[path]}><Layout /></MemoryRouter>);

describe("Menú lateral", () => {
  it("despliega la sección de la ruta actual y deja las demás plegadas", () => {
    renderAt("/contabilidad/cartera");
    expect(screen.getByRole("button", { name: "Contabilidad" })).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("button", { name: "Compras" })).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByRole("link", { name: "Cartera y pagos" })).toHaveClass("active");
  });

  it("despliega y pliega una sección con cada clic", () => {
    renderAt("/");
    const compras = screen.getByRole("button", { name: "Compras" });
    const items = document.getElementById(compras.getAttribute("aria-controls")!)!;
    expect(items).toHaveAttribute("aria-hidden", "true");
    expect(screen.getByText("Órdenes de compra").closest("a")).toHaveAttribute("tabindex", "-1");

    fireEvent.click(compras);
    expect(compras).toHaveAttribute("aria-expanded", "true");
    expect(items).toHaveAttribute("aria-hidden", "false");
    expect(screen.getByText("Órdenes de compra").closest("a")).not.toHaveAttribute("tabindex");

    fireEvent.click(compras);
    expect(compras).toHaveAttribute("aria-expanded", "false");
    expect(items).toHaveAttribute("aria-hidden", "true");
  });

  it("ubica la sección de cada ruta", () => {
    expect(sectionOf("/")).toBe("Gerencia");
    expect(sectionOf("/logistica/despachos")).toBe("Ventas y logística");
    expect(sectionOf("/no-existe")).toBeUndefined();
  });
});
