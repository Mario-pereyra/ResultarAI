import { describe, expect, it } from "vitest";
import messages from "./es.json";

/**
 * Verificaciones deterministas del catálogo (tarea 6.1/6.3,
 * d10-design-system-shell) — complementa a `scripts/check-hardcoded-strings.mjs`
 * (que audita que NO haya texto fuera del catálogo) con dos chequeos sobre
 * el CONTENIDO del catálogo mismo:
 *
 * 1. Escenario "Textos del shell en voseo" (specs/i18n-foundation/spec.md):
 *    ningún mensaje usa formas tuteantes ("verifica", "puedes", "tienes",
 *    "haz clic"...) ni el "usted" formal — design/DESIGN-SYSTEM.md §4.2.
 * 2. Escenario "Contador de notificaciones no leídas": el mensaje del
 *    contador de la campana usa sintaxis de plural ICU (no concatenación
 *    manual) — y de paso se deja documentado que el de aprobaciones del
 *    sidebar (construido en la tarea 5.3) YA la usaba.
 */

/** Recorre el árbol del catálogo y devuelve cada string hoja con su "ruta" (para reportar dónde falló). */
function collectLeafStrings(node: unknown, path: string[] = []): Array<{ path: string; value: string }> {
  if (typeof node === "string") {
    return [{ path: path.join("."), value: node }];
  }
  if (node && typeof node === "object") {
    return Object.entries(node as Record<string, unknown>).flatMap(([key, value]) =>
      collectLeafStrings(value, [...path, key]),
    );
  }
  return [];
}

/**
 * Formas tuteantes/de "usted" más comunes en textos UI en español —
 * lista NO exhaustiva (heurística documentada, mismo criterio pragmático
 * que scripts/check-hardcoded-strings.mjs): cubre los verbos de ejemplo
 * citados por design/DESIGN-SYSTEM.md §4.2 ("verificá", no "verifica" ni
 * "verifique") más las formas de uso más frecuente en copy de producto
 * (imperativos y presente indicativo de 2a persona). Los tests de nuevas
 * claves deben seguir usando voseo; si esta lista da un falso positivo
 * real (palabra que casualmente coincide pero no es 2a persona), ajustarla
 * acá con el porqué.
 */
const TUTEO_FORMS = [
  "verifica",
  "verifique",
  "escribe",
  "escriba",
  "revisa",
  "revise",
  "solicita",
  "solicite",
  "puedes",
  "tienes",
  "quieres",
  "sabes",
  "debes",
  "eres",
  "haz clic",
  "haga clic",
  " usted",
  " tú ",
  "¿tú",
];
const TUTEO_PATTERN = new RegExp(
  `\\b(${TUTEO_FORMS.map((form) => form.trim()).join("|")})\\b`,
  "i",
);

describe('Catálogo es.json — escenario "Textos del shell en voseo"', () => {
  const leaves = collectLeafStrings(messages);

  it("recolecta al menos un mensaje (guarda contra un catálogo vacío/roto)", () => {
    expect(leaves.length).toBeGreaterThan(0);
  });

  it.each(leaves)("$path no usa formas tuteantes ni de usted", ({ path, value }) => {
    expect(TUTEO_PATTERN.test(value), `"${path}" = "${value}" parece tuteo/usted, no voseo`).toBe(
      false,
    );
  });
});

describe('Catálogo es.json — escenario "Contador de notificaciones no leídas" (plural ICU, tarea 6.3)', () => {
  it("Shell.topbar.notificationsAriaLabel usa sintaxis de plural ICU con los 3 casos (=0/one/other)", () => {
    const message = messages.Shell.topbar.notificationsAriaLabel;
    expect(message).toContain("{count, plural,");
    expect(message).toContain("=0 {");
    expect(message).toContain("one {");
    expect(message).toContain("other {");
  });

  it("Shell.sidebar.approvalsAriaLabel (tarea 5.3) ya usa plural ICU — verificación de no regresión", () => {
    const message = messages.Shell.sidebar.approvalsAriaLabel;
    expect(message).toContain("{count, plural,");
    expect(message).toContain("one {");
    expect(message).toContain("other {");
  });
});
