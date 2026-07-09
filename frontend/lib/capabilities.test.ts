import { describe, expect, it } from "vitest";
import { CAPABILITIES_BY_ROLE } from "./capabilities";

/**
 * Tarea 5.2, d10-design-system-shell.
 * Valores literales copiados a mano de la tabla "Diferencias por rol" de
 * design/VISTAS/01-acceso-shell.md Vista 3 — a propósito NO derivados de
 * `CAPABILITIES_BY_ROLE` ni de ninguna otra constante compartida, para que
 * el test detecte una regresión real en vez de comparar la constante
 * consigo misma.
 */
describe('CAPABILITIES_BY_ROLE — tabla "Diferencias por rol" (Vista 3)', () => {
  it("Funcional: Catálogo, Chat, Workflows, Aprobaciones, Mi espacio — sin Administración ni Construcción", () => {
    expect(CAPABILITIES_BY_ROLE.funcional).toEqual([
      "catalogo",
      "chat",
      "workflows",
      "aprobaciones",
      "mi-espacio",
    ]);
  });

  it("Técnico: las mismas 5 secciones que Funcional — sin Administración ni Construcción", () => {
    expect(CAPABILITIES_BY_ROLE.tecnico).toEqual([
      "catalogo",
      "chat",
      "workflows",
      "aprobaciones",
      "mi-espacio",
    ]);
  });

  it("Admin: las 5 secciones comunes más Administración y Construcción (tras el kicker ADMIN)", () => {
    expect(CAPABILITIES_BY_ROLE.admin).toEqual([
      "catalogo",
      "chat",
      "workflows",
      "aprobaciones",
      "mi-espacio",
      "administracion",
      "construccion",
    ]);
  });
});
