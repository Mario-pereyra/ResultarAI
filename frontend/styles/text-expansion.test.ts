import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Escenario "Botón con texto 25% más largo no rompe el layout"
 * (specs/i18n-foundation/spec.md, tarea 6.2, d10-design-system-shell).
 *
 * Límite de jsdom documentado: jsdom no tiene motor de layout real (no
 * hay `getBoundingClientRect` con medidas reales, no hay reflow), así que
 * "no desborda/recorta" no se puede verificar renderizando y midiendo
 * píxeles como en un browser real. Lo que SÍ es verificable y determinista
 * en este entorno:
 *
 * 1. Contrato ESTÁTICO del CSS (esta suite): ningún selector de un
 *    contenedor de texto traducible del shell/componentes base fija un
 *    `width` en píxeles (solo `min-width`/`max-width`, que no cortan texto
 *    — permiten crecer) y ninguno combina `overflow: hidden` +
 *    `text-overflow: ellipsis` (que SÍ truncaría visualmente el texto
 *    inflado) — esto es exactamente la regla del design system §12:
 *    "botones con padding flexible y white-space: nowrap consciente; nada
 *    de anchos fijos al píxel sobre texto traducible".
 * 2. Contrato de COMPONENTE (`components/shell/*.inflated-text.test.tsx` y
 *    `components/ui/button.test.tsx`): un texto un 25% más largo se
 *    renderiza COMPLETO en el DOM (el componente no lo trunca con JS/CSS
 *    inline) y sin que el componente le agregue un `style` con ancho fijo.
 */

const FRONTEND_ROOT = join(__dirname, "..");

function readCss(...parts: string[]): string {
  return readFileSync(join(FRONTEND_ROOT, ...parts), "utf8");
}

const CSS_SOURCES = {
  shell: readCss("styles", "shell.css"),
  button: readCss("styles", "components", "button.css"),
  fields: readCss("styles", "components", "fields.css"),
  dropdown: readCss("styles", "components", "dropdown.css"),
  tag: readCss("styles", "components", "tag.css"),
};

const ALL_CSS = Object.values(CSS_SOURCES).join("\n");

/**
 * Contenedores de TEXTO TRADUCIBLE del shell/componentes base cubiertos
 * por este change (d10) — se excluyen a propósito contenedores de datos
 * NO traducibles (badges numéricos, avatares de iniciales, `kbd` de
 * atajo de teclado) porque el design system explícitamente no les exige
 * reservar +25%: no llevan texto de catálogo, llevan números/iniciales
 * fijas (`design/DESIGN-SYSTEM.md` §12: "Lo que NO se traduce").
 */
const TEXT_CONTAINER_SELECTORS = [
  ".btn",
  ".shell-sidebar__link",
  ".shell-sidebar__name",
  ".shell-sidebar__label",
  ".shell-topbar__user-name",
  ".dropdown__trigger",
  ".dropdown-menu__item",
  ".field-label",
  ".field-hint",
  ".field-error",
  ".tag",
  ".badge-rol",
];

/** Bloques de regla top-level `selector(es) { declaraciones }` (no entra a @media anidados). */
function parseTopLevelRules(css: string): Array<{ selectors: string[]; body: string }> {
  const withoutComments = css.replace(/\/\*[\s\S]*?\*\//g, "");
  const rules: Array<{ selectors: string[]; body: string }> = [];
  const pattern = /([^{}]+)\{([^{}]*)\}/g;
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(withoutComments)) !== null) {
    const selectorPart = match[1].trim();
    if (selectorPart.startsWith("@") || selectorPart.startsWith("from") || selectorPart.startsWith("to")) {
      continue;
    }
    const selectors = selectorPart.split(",").map((s) => s.trim());
    rules.push({ selectors, body: match[2] });
  }
  return rules;
}

/** Declaraciones cuyo selector EXACTO (sin pseudo-clases/descendientes) es `selector`. */
function baseRuleBodiesFor(selector: string): string[] {
  return parseTopLevelRules(ALL_CSS)
    .filter((rule) => rule.selectors.includes(selector))
    .map((rule) => rule.body);
}

describe('Contrato CSS "+25%" — contenedores de texto sin ancho fijo ni truncado forzado (tarea 6.2)', () => {
  // Nota: NO se exige que cada selector tenga una regla base propia — varios
  // (`.shell-sidebar__label`, `.field-hint`, `.field-error`) son `<span>`s
  // sin ninguna declaración de layout propia (solo heredan tipografía), lo
  // que ya satisface trivialmente "sin ancho fijo": si no hay regla, no hay
  // `width` que fijar. Los dos checks de abajo son vacuously true en ese caso.

  it.each(TEXT_CONTAINER_SELECTORS)(
    "%s no fija `width` EN PÍXELES (min-width/max-width y width en %% están permitidos: no cortan, permiten crecer)",
    (selector) => {
      const bodies = baseRuleBodiesFor(selector);
      for (const body of bodies) {
        // Negative lookbehind manual para min-/max-width; solo se prohíbe la
        // unidad px (design/DESIGN-SYSTEM.md §12: "anchos EN PÍXELES") — un
        // `width: 100%` (ej. .dropdown-menu__item, para llenar el menú) es
        // relativo al contenedor, no un corte duro de contenido.
        const widthDeclarations = body.match(/(?<!min-)(?<!max-)\bwidth\s*:\s*[\d.]+px\s*;/g) ?? [];
        expect(widthDeclarations, `${selector} declara width fijo en px: ${widthDeclarations.join(", ")}`).toHaveLength(
          0,
        );
      }
    },
  );

  it.each(TEXT_CONTAINER_SELECTORS)("%s no combina overflow:hidden + text-overflow:ellipsis (truncado forzado)", (selector) => {
    const bodies = baseRuleBodiesFor(selector);
    for (const body of bodies) {
      const hasEllipsis = /text-overflow\s*:\s*ellipsis/.test(body);
      const hasOverflowHidden = /(?<!-x)(?<!-y)\boverflow\s*:\s*hidden/.test(body);
      expect(
        hasEllipsis && hasOverflowHidden,
        `${selector} trunca el texto con ellipsis: ${body}`,
      ).toBe(false);
    }
  });

  it(".btn usa white-space: nowrap CON padding flexible (no ancho fijo) — patrón explícito de DESIGN-SYSTEM.md §12", () => {
    const [body] = baseRuleBodiesFor(".btn");
    expect(body).toMatch(/white-space\s*:\s*nowrap/);
    expect(body).toMatch(/padding\s*:\s*0\s+var\(--sp-4\)/);
    expect(body).not.toMatch(/(?<!min-)(?<!max-)\bwidth\s*:/);
  });
});
