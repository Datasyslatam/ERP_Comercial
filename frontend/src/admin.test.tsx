import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// Dobles de API y sesión: se valida lo que envían las pantallas de administración.
const post = vi.fn();
const patch = vi.fn();
const responses: Record<string, unknown> = {
  "/admin/users": [{ id: 1, full_name: "Ana Admin", email: "ana@x.co", status: "active", roles: [], last_login_at: null }],
  "/admin/roles": [
    { id: 10, code: "vendedor", name: "Vendedor", is_system: true, users_count: 1, permissions: ["sales.order.read"] },
    { id: 11, code: "jefe", name: "Jefe de ventas", is_system: false, users_count: 0, permissions: ["sales.order.read"] }],
  "/sites": { items: [{ id: 3, name: "Bogotá" }] },
  "/admin/roles/11": { id: 11, code: "jefe", name: "Jefe de ventas", is_system: false, editable: true, users_count: 0,
    permissions: ["sales.order.read"], users: [], approval_limits: [], history: [] },
  "/admin/permissions": [{ module: "sales", label: "Ventas", resources: [{ resource: "order", label: "Pedidos de venta", actions: [
    { code: "sales.order.read", action: "read", label: "Consultar" },
    { code: "sales.order.create", action: "create", label: "Crear y editar" },
    { code: "sales.order.approve", action: "approve", label: "Aprobar" }] }] }],
};
const mine = new Set(["admin.users.read", "admin.users.create", "admin.users.admin", "admin.roles.read", "admin.roles.admin",
  "sales.order.read", "sales.order.create"]);
vi.mock("./lib/api", () => ({
  get: (path: string) => Promise.resolve(responses[path] ?? { items: [] }),
  post: (...args: unknown[]) => post(...args),
  patch: (...args: unknown[]) => patch(...args),
  put: vi.fn(),
  api: vi.fn(),
  download: vi.fn(),
  qs: (p: Record<string, unknown>) => {
    const s = Object.entries(p).filter(([, v]) => v !== "" && v != null).map(([k, v]) => `${k}=${v}`).join("&");
    return s ? `?${s}` : "";
  },
}));
vi.mock("./lib/session", () => ({
  useSession: () => ({ company: { id: 1, currency: "COP" }, me: { id: 1, email: "ana@x.co" }, can: (p: string) => mine.has(p),
    moduleOn: () => true }),
}));

import { RolesPage, UsersPage } from "./pages/Admin";

beforeEach(() => {
  post.mockReset();
  patch.mockReset().mockResolvedValue({});
});

describe("Alta de usuarios", () => {
  it("envía los roles con sede y vigencia y muestra la contraseña temporal una sola vez", async () => {
    post.mockResolvedValue({ id: 5, full_name: "Nuevo", email: "n@x.co", temporary_password: "Tmp-Clave-123!" });
    render(<UsersPage />);
    fireEvent.click(await screen.findByText("Nuevo usuario"));
    const dialog = within(screen.getByRole("dialog"));
    fireEvent.change(dialog.getByLabelText(/Nombre completo/), { target: { value: "Nuevo" } });
    fireEvent.change(dialog.getByLabelText(/Correo/), { target: { value: "n@x.co" } });
    await dialog.findByRole("option", { name: "Vendedor" });
    fireEvent.change(dialog.getByLabelText("Rol"), { target: { value: "vendedor" } });
    await dialog.findByRole("option", { name: "Bogotá" });
    fireEvent.change(dialog.getByLabelText("Sede"), { target: { value: "3" } });
    fireEvent.change(dialog.getByLabelText("Vigente hasta"), { target: { value: "2099-12-31" } });
    fireEvent.click(dialog.getByText("Crear usuario"));
    await screen.findByText("Tmp-Clave-123!");
    const [path, body] = post.mock.calls[0];
    expect(path).toBe("/admin/users");
    expect(body).toMatchObject({ email: "n@x.co", full_name: "Nuevo",
      roles: [{ role_code: "vendedor", site_id: 3, expires_on: "2099-12-31" }] });
    expect(body.password).toBeUndefined(); // se genera en el servidor
  });
});

describe("Matriz de permisos", () => {
  it("bloquea los permisos que el administrador no tiene y guarda solo lo seleccionado", async () => {
    render(<RolesPage />);
    fireEvent.click(await screen.findByText("Jefe de ventas"));
    const approve = await screen.findByLabelText("Pedidos de venta · Aprobar");
    expect(approve).toBeDisabled(); // sales.order.approve no está entre los permisos propios
    fireEvent.click(screen.getByLabelText("Pedidos de venta · Crear y editar"));
    fireEvent.click(screen.getByText("Guardar permisos"));
    await waitFor(() => expect(patch).toHaveBeenCalled());
    const [path, body] = patch.mock.calls[0];
    expect(path).toBe("/admin/roles/11");
    expect([...body.permissions].sort()).toEqual(["sales.order.create", "sales.order.read"]);
  });
});
