import { readFileSync, readdirSync } from "node:fs";
import { extname, join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Escenario "Foco visible en todo interactivo" (specs/design-system/spec.md,
 * tarea 7.2, d10-design-system-shell): `:focus-visible` con anillo 2px
 * `var(--focus-ring)` + offset 2 en TODO interactivo, y ningún elemento con
 * `outline: none` sin un reemplazo visible (design/DESIGN-SYSTEM.md §10).
 *
 * Esta suite audita ESTÁTICAMENTE `styles/**​/*.css` (dos checks
 * deterministas — no depende de renderizar+medir, algo que jsdom no puede
 * hacer de verdad):
 *
 * 1. Cada familia de componente interactivo del inventario (botón, campo,
 *    dropdown, ítem de menú, links del sidebar, toggle de colapso, íconos
 *    del topbar, buscador, skip-link, cierre de toast, campana) tiene una
 *    regla `:focus-visible` (o `:focus-within` en el único caso documentado
 *    de abajo) propia en el CSS portado.
 * 2. Todo `outline: none`/`outline: 0` del CSS está en la lista explícita
 *    de excepciones documentadas (`ALLOWED_OUTLINE_NONE`), cada una con su
 *    reemplazo visible verificado a mano — si aparece un `outline: none`
 *    nuevo sin agregarlo (con su justificación) a esa lista, el test falla:
 *    obliga a documentar la excepción, no a que pase desapercibida.
 *
 * El resto ("el anillo se ve exactamente así, con este radio/color en las
 * 4 combinaciones") lo garantiza el CSS ya portado de tokens + la
 * inspección visual en /styleguide (tarea 7.3) — límite de jsdom, no hay
 * verificación de renderizado real de outline.
 */

const FRONTEND_ROOT = join(__dirname, "..");

function collectCssFiles(dir: string, files: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const fullPath = join(dir, entry.name);
    if (entry.isDirectory()) {
      collectCssFiles(fullPath, files);
    } else if (extname(entry.name) === ".css") {
      files.push(fullPath);
    }
  }
  return files;
}

const ALL_CSS = collectCssFiles(join(FRONTEND_ROOT, "styles"))
  .map((file) => readFileSync(file, "utf8"))
  .join("\n\n");

/**
 * Interactivos del inventario base (design/DESIGN-SYSTEM.md §8) con su
 * selector y el tipo de reemplazo de foco esperado. `focus-within` está
 * marcado aparte porque es la única familia que delega el anillo a un
 * ancestro en vez de mostrarlo en el propio elemento enfocado (ver
 * excepción 2 de ALLOWED_OUTLINE_NONE).
 */
const FOCUS_VISIBLE_FAMILIES: Array<{ name: string; selector: RegExp }> = [
  { name: "botón (.btn)", selector: /\.btn:focus-visible\s*\{/ },
  { name: "campos (.input/.select/.textarea)", selector: /\.input:focus-visible[^{]*\{/ },
  { name: "dropdown — disparador", selector: /\.dropdown__trigger:focus-visible\s*\{/ },
  { name: "dropdown — ítem de menú", selector: /\.dropdown-menu__item:focus-visible\s*\{/ },
  { name: "sidebar — link de navegación", selector: /\.shell-sidebar__link:focus-visible\s*\{/ },
  { name: "sidebar — toggle de colapso", selector: /\.shell-sidebar__collapse-btn:focus-visible\s*\{/ },
  { name: "topbar — ícono (tema/hamburguesa)", selector: /\.shell-topbar__icon:focus-visible\s*\{/ },
  { name: "topbar — buscador (delega a :focus-within)", selector: /\.shell-topbar__search:focus-within\s*\{/ },
  { name: "campana de notificaciones", selector: /\.notif-bell:focus-visible\s*\{/ },
  { name: "skip-link", selector: /\.skip-link:focus-visible\s*\{/ },
  { name: "toast — cierre manual", selector: /\.toast__close:focus-visible\s*\{/ },
];

describe('Foco visible — escenario "Foco visible en todo interactivo" (tarea 7.2): cobertura por familia', () => {
  it.each(FOCUS_VISIBLE_FAMILIES)("$name define :focus-visible (o :focus-within delegado)", ({ selector }) => {
    expect(selector.test(ALL_CSS)).toBe(true);
  });

  it("las reglas con outline explícito usan var(--focus-ring) (nunca un color literal)", () => {
    const outlineDeclarations = ALL_CSS.match(/outline:\s*2px\s+solid\s+[^;]+;/g) ?? [];
    expect(outlineDeclarations.length).toBeGreaterThan(0);
    for (const declaration of outlineDeclarations) {
      expect(declaration).toContain("var(--focus-ring)");
    }
  });
});

/**
 * Excepciones documentadas a "outline: none siempre necesita reemplazo EN
 * LA MISMA regla" — cada una tiene su reemplazo verificado a mano en otra
 * parte del CSS (columna "replacement"), no es un `outline: none` "suelto".
 */
const ALLOWED_OUTLINE_NONE = [
  {
    pattern: /\.input:focus-visible,\s*\.select:focus-visible,\s*\.textarea:focus-visible\s*\{[^}]*outline:\s*none/,
    replacement: "mismo bloque agrega box-shadow halo 3px (design/DESIGN-SYSTEM.md §8.2: “focus (borde --accent + halo 3px al 25%)”), reemplazo alternativo documentado del anillo genérico para campos.",
  },
  {
    pattern: /\.shell-topbar__search-input\s*\{[^}]*outline:\s*none/,
    replacement:
      "el reemplazo vive en el ancestro .shell-topbar__search:focus-within (anillo 2px var(--focus-ring) offset 1) — se apaga el outline nativo del <input> para no duplicar el anillo del contenedor.",
  },
  {
    pattern: /\.shell-content:focus-visible\s*\{\s*outline:\s*none/,
    replacement:
      "el <main> del shell recibe tabIndex={-1} como destino PROGRAMÁTICO del skip-link (nunca entra al orden de Tab): no es un control interactivo que necesite anillo propio.",
  },
];

describe('Foco visible — escenario "Foco visible en todo interactivo" (tarea 7.2): outline: none solo con reemplazo documentado', () => {
  const rawOutlineNoneCount = (ALL_CSS.match(/outline:\s*(none|0)\b/g) ?? []).length;

  it("cada outline:none/0 del CSS está cubierto por una excepción documentada con reemplazo verificado", () => {
    for (const { pattern } of ALLOWED_OUTLINE_NONE) {
      expect(pattern.test(ALL_CSS)).toBe(true);
    }
  });

  it("no aparecieron outline:none/0 NUEVOS fuera de la lista documentada (guarda de regresión)", () => {
    expect(rawOutlineNoneCount).toBe(ALLOWED_OUTLINE_NONE.length);
  });
});
