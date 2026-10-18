import { afterEach, describe, expect, it, vi } from "vitest";
import { get, login, OFFLINE_MESSAGE, serverStatus } from "./lib/api";

const reply = (status: number, body: string, type = "application/json") =>
  vi.fn().mockResolvedValue(new Response(body || null, { status, headers: { "content-type": type } }));

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe("inicio de sesión", () => {
  it("sin API detrás del proxy (500 sin cuerpo) avisa que no hay conexión, sin errores de JSON", async () => {
    vi.stubGlobal("fetch", reply(500, "", "text/plain"));
    await expect(login("a@b.co", "x")).rejects.toThrow(OFFLINE_MESSAGE);
  });

  it("si la red falla avisa que no hay conexión", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("NetworkError when attempting to fetch resource.")));
    await expect(login("a@b.co", "x")).rejects.toThrow(OFFLINE_MESSAGE);
  });

  it("muestra el mensaje del servidor ante credenciales inválidas", async () => {
    vi.stubGlobal("fetch", reply(401, JSON.stringify({ error: { code: "unauthorized", message: "Credenciales inválidas" } })));
    await expect(login("a@b.co", "x")).rejects.toThrow("Credenciales inválidas");
  });

  it("guarda la sesión cuando el ingreso es correcto", async () => {
    vi.stubGlobal("fetch", reply(200, JSON.stringify({ access_token: "at", refresh_token: "rt" })));
    await login("a@b.co", "x");
    expect(sessionStorage.getItem("erp.rt")).toBe("rt");
  });
});

describe("peticiones", () => {
  it("un 503 sin cuerpo del ERP indica que el servidor no está disponible", async () => {
    sessionStorage.setItem("erp.rt", "rt");
    vi.stubGlobal("fetch", vi.fn().mockImplementation(async () => new Response(null, { status: 503 })));
    await expect(get("/items")).rejects.toThrow("no está disponible (error 503)");
    expect(sessionStorage.getItem("erp.rt")).toBe("rt"); // una caída de la API no cierra la sesión
  });
});

describe("estado del servidor", () => {
  it("en línea solo si /health/ready responde ok, con su entorno", async () => {
    vi.stubGlobal("fetch", reply(200, JSON.stringify({ status: "ok", environment: "development" })));
    expect(await serverStatus()).toEqual({ online: true, environment: "development" });
  });
  it("sin conexión si la API no responde o responde otra cosa", async () => {
    vi.stubGlobal("fetch", reply(500, "", "text/plain"));
    expect(await serverStatus()).toEqual({ online: false });
    vi.stubGlobal("fetch", reply(200, "<!doctype html>", "text/html"));
    expect(await serverStatus()).toEqual({ online: false });
  });
});
