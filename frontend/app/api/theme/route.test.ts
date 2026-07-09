import { describe, expect, it } from "vitest";
import { NextRequest } from "next/server";
import { POST } from "./route";

function requestWithThemeCookie(theme?: string) {
  return new NextRequest("http://localhost/catalogo", {
    method: "POST",
    headers: theme ? { cookie: `theme=${theme}` } : undefined,
  });
}

/**
 * Escenario "Alternar tema persiste entre sesiones" (tarea 5.4,
 * d10-design-system-shell): verifica la escritura de la cookie `theme` que
 * hace el route handler que consume components/shell/topbar.tsx.
 */
describe("POST /api/theme", () => {
  it("sin cookie previa (dark, default de instancia) escribe theme=light", async () => {
    const response = await POST(requestWithThemeCookie());
    expect(response.cookies.get("theme")?.value).toBe("light");
  });

  it("con theme=dark escribe theme=light", async () => {
    const response = await POST(requestWithThemeCookie("dark"));
    expect(response.cookies.get("theme")?.value).toBe("light");
  });

  it("con theme=light escribe theme=dark (alterna en el sentido inverso)", async () => {
    const response = await POST(requestWithThemeCookie("light"));
    expect(response.cookies.get("theme")?.value).toBe("dark");
  });

  it("la cookie se escribe con maxAge de un año (persiste entre sesiones)", async () => {
    const response = await POST(requestWithThemeCookie("dark"));
    const cookie = response.cookies.get("theme");
    expect(cookie?.maxAge).toBe(60 * 60 * 24 * 365);
    expect(cookie?.path).toBe("/");
  });
});
