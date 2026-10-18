import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

vi.mock("./lib/session", () => ({
  useSession: () => ({
    me: { full_name: "Ana María Pérez", email: "ana@datasys.test", companies: [{ id: 1, code: "CO1", name: "Empresa", country: "CO" }] },
    company: { id: 1 }, selectCompany: vi.fn(), logout: vi.fn(), can: () => true, moduleOn: () => true,
  }),
}));

import { Layout, pageOf, sectionOf } from "./components/Layout";

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

describe("Barra superior", () => {
  it("muestra la ruta de navegación de la pantalla actual", () => {
    renderAt("/logistica/rutas");
    const crumbs = screen.getByRole("navigation", { name: "Ruta de navegación" });
    expect(crumbs).toHaveTextContent("Ventas y logística");
    expect(within(crumbs).getByText("Rutas y plan de entregas")).toHaveAttribute("aria-current", "page");
  });

  it("identifica al usuario con sus iniciales y conserva el selector de empresa y la salida", () => {
    renderAt("/");
    expect(screen.getByText("AP")).toBeInTheDocument();
    expect(screen.getByText("ana@datasys.test")).toBeInTheDocument();
    expect(screen.getByLabelText("Empresa")).toHaveValue("1");
    expect(screen.getByRole("button", { name: "Salir" })).toBeInTheDocument();
  });

  it("elige la opción más específica de la ruta", () => {
    expect(pageOf("/")).toEqual({ section: "Gerencia", label: "Dashboard ejecutivo" });
    expect(pageOf("/contabilidad/cartera")).toEqual({ section: "Contabilidad", label: "Cartera y pagos" });
    expect(pageOf("/facturacion")?.label).toBe("Facturación electrónica");
    expect(pageOf("/otra")).toBeUndefined();
  });
});
