import { describe, expect, it } from "vitest";
import { parseGatewayStatus, parseRole, resolveDevSession } from "./dev-session";

describe("dev-session (provider de desarrollo del SessionContext, tarea 5.1)", () => {
  it("parseRole cae a funcional (menor privilegio) si el valor es inválido o falta", () => {
    expect(parseRole(undefined)).toBe("funcional");
    expect(parseRole("no-existe")).toBe("funcional");
    expect(parseRole("admin")).toBe("admin");
    expect(parseRole("tecnico")).toBe("tecnico");
  });

  it("parseGatewayStatus cae a ok si el valor es inválido o falta", () => {
    expect(parseGatewayStatus(undefined)).toBe("ok");
    expect(parseGatewayStatus("no-existe")).toBe("ok");
    expect(parseGatewayStatus("offline")).toBe("offline");
  });

  it("resolveDevSession arma la sesión mock del rol pedido, con sus capacidades resueltas", () => {
    const admin = resolveDevSession("admin", undefined);
    expect(admin.user).toEqual({ name: "marcos", role: "admin" });
    expect(admin.pendingApprovals).toBe(3);
    expect(admin.unreadNotifications).toBe(4);
    expect(admin.gateway.status).toBe("ok");
    expect(admin.capabilities).toContain("administracion");

    const funcional = resolveDevSession(undefined, "offline");
    expect(funcional.user).toEqual({ name: "lucia", role: "funcional" });
    expect(funcional.gateway.status).toBe("offline");
    expect(funcional.unreadNotifications).toBe(1);
    expect(funcional.capabilities).not.toContain("administracion");
  });

  it('escenario "Contador de notificaciones no leídas" (tarea 6.3): valores mock por rol, mismos que design/mockups/03-shell.html', () => {
    expect(resolveDevSession("funcional", undefined).unreadNotifications).toBe(1);
    expect(resolveDevSession("tecnico", undefined).unreadNotifications).toBe(2);
    expect(resolveDevSession("admin", undefined).unreadNotifications).toBe(4);
  });
});
