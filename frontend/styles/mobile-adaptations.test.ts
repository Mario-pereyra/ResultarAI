import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Auditoría ESTÁTICA del CSS de la tarea 8.1/8.2 (d13-chat-conversacion,
 * "Adaptación móvil"). Mismo límite documentado que
 * `styles/focus-visible.test.ts`/`styles/text-expansion.test.ts`: jsdom no
 * evalúa `@media` (no hay motor de layout real), así que lo determinista y
 * verificable acá es el CONTRATO ESTÁTICO del CSS -- cada selector
 * involucrado en la adaptación móvil tiene su regla dentro de un bloque
 * `@media (max-width: 767px)` (el MISMO breakpoint que ya usa
 * `styles/shell.css` para el drawer/hamburguesa, DS §3.3: "móvil 380 ·
 * tablet 768 · desktop 1200"). Las pruebas de COMPONENTE (`*.test.tsx`)
 * complementan esto verificando que las clases/elementos existen en el DOM
 * -- ver `components/chat/*.test.tsx`, `app/(shell)/chat/*.test.tsx`.
 */

const FRONTEND_ROOT = join(__dirname, "..");

function readCss(...parts: string[]): string {
  return readFileSync(join(FRONTEND_ROOT, ...parts), "utf8");
}

const TOKENS_CSS = readCss("styles", "tokens.css");
const CHAT_CSS = readCss("styles", "components", "chat.css");
const HISTORY_CSS = readCss("styles", "components", "history.css");
const GLOBALS_CSS = readCss("app", "globals.css");

/** Concatena el CUERPO (sin las llaves externas) de todos los bloques
 * `@media <mediaSelector> { ... }` del CSS dado -- balanceo manual de `{}`
 * (no un regex de un solo nivel) porque cada bloque contiene VARIAS reglas
 * anidadas. Mismo criterio de "parser simplificado pero determinista" que
 * `parseTopLevelRules` de `styles/text-expansion.test.ts`. */
function extractMediaBlocks(css: string, mediaSelector: string): string {
  const withoutComments = css.replace(/\/\*[\s\S]*?\*\//g, "");
  const marker = `@media ${mediaSelector}`;
  const blocks: string[] = [];
  let searchFrom = 0;
  for (;;) {
    const start = withoutComments.indexOf(marker, searchFrom);
    if (start === -1) break;
    const braceStart = withoutComments.indexOf("{", start);
    let depth = 0;
    let i = braceStart;
    for (; i < withoutComments.length; i += 1) {
      if (withoutComments[i] === "{") depth += 1;
      else if (withoutComments[i] === "}") {
        depth -= 1;
        if (depth === 0) break;
      }
    }
    blocks.push(withoutComments.slice(braceStart + 1, i));
    searchFrom = i + 1;
  }
  return blocks.join("\n");
}

describe("tokens.css — token de objetivo táctil (tarea 8.1)", () => {
  it("--touch-target-min existe una sola vez, en 44px, fuera de los 4 sets de tema×marca", () => {
    const matches = TOKENS_CSS.match(/--touch-target-min:\s*44px;/g) ?? [];
    expect(matches).toHaveLength(1);
  });
});

describe('chat.css — objetivo táctil ≥44px en móvil (tarea 8.1, escenario "Selector de ramas operable en móvil")', () => {
  const MOBILE_CHAT_CSS = extractMediaBlocks(CHAT_CSS, "(max-width: 767px)");

  it.each([
    ["flechas del selector de ramas", ".branch-sel__arrow"],
    ['botón "Editar" del mensaje', ".edit-btn"],
    ["acciones de feedback 👍/👎", ".msg-feedback__btn"],
    ['botón "⋯" del menú de sesión (chat-top, header)', ".chat-top__menu-trigger"],
  ])("%s (%s) define min-width y min-height con var(--touch-target-min) dentro de @media (max-width: 767px)", (_name, selector) => {
    const escaped = selector.replace(/[.]/g, "\\$&");
    const rule = new RegExp(`${escaped}\\s*\\{[^}]*\\}`);
    const match = MOBILE_CHAT_CSS.match(rule)?.[0];
    expect(match, `no se encontró la regla móvil de ${selector}`).toBeTruthy();
    expect(match).toMatch(/min-width:\s*var\(--touch-target-min\)/);
    expect(match).toMatch(/min-height:\s*var\(--touch-target-min\)/);
  });
});

describe('chat.css — composer fijo con área segura en móvil (tarea 8.1, vista 05 §Móvil)', () => {
  const MOBILE_CHAT_CSS = extractMediaBlocks(CHAT_CSS, "(max-width: 767px)");

  it(".chat-composer pasa a position: fixed, anclado al borde inferior del viewport", () => {
    const rule = MOBILE_CHAT_CSS.match(/\.chat-composer\s*\{[^}]*\}/)?.[0];
    expect(rule).toBeTruthy();
    expect(rule).toMatch(/position:\s*fixed/);
    expect(rule).toMatch(/bottom:\s*0/);
  });

  it(".chat-composer suma env(safe-area-inset-bottom) al padding inferior", () => {
    const rule = MOBILE_CHAT_CSS.match(/\.chat-composer\s*\{[^}]*\}/)?.[0];
    expect(rule).toMatch(/env\(safe-area-inset-bottom\)/);
  });

  it(".msg-column reduce el padding y reserva espacio inferior para el composer fijo", () => {
    const rule = MOBILE_CHAT_CSS.match(/\.msg-column\s*\{[^}]*\}/)?.[0];
    expect(rule).toBeTruthy();
    expect(rule).toMatch(/padding-bottom:[^;]*env\(safe-area-inset-bottom\)/);
  });
});

describe('chat.css — header del chat ("chat-top") colapsa a menú de sesión en móvil (vista 05 §0.1/vista 06 §Móvil, "el taxímetro sale del header y vive en el menú de sesión")', () => {
  it(".chat-top__menu-trigger (botón ⋯) está oculto por defecto, fuera del breakpoint móvil", () => {
    expect(CHAT_CSS).toMatch(/\.chat-top__menu-trigger\s*\{\s*display:\s*none;\s*\}/);
  });

  it(".chat-top__menu-panel (el taxímetro) es contenido inline por defecto (desktop) y se oculta en móvil hasta `.is-open`", () => {
    const desktopRule = CHAT_CSS.match(/\.chat-top__menu-panel\s*\{[^}]*\}/)?.[0];
    expect(desktopRule, "no se encontró la regla de base (fuera de @media) de .chat-top__menu-panel").toBeTruthy();
    expect(desktopRule).toMatch(/display:\s*flex/);

    const mobileChat = extractMediaBlocks(CHAT_CSS, "(max-width: 767px)");
    const mobileRule = mobileChat.match(/\.chat-top__menu-panel\s*\{[^}]*\}/)?.[0];
    expect(mobileRule, "no se encontró la regla móvil de .chat-top__menu-panel").toBeTruthy();
    expect(mobileRule).toMatch(/display:\s*none/);

    const mobileOpenRule = mobileChat.match(/\.chat-top__menu-panel\.is-open\s*\{[^}]*\}/)?.[0];
    expect(mobileOpenRule, "no se encontró la regla móvil de .chat-top__menu-panel.is-open").toBeTruthy();
    expect(mobileOpenRule).toMatch(/display:\s*flex/);
  });
});

describe("chat.css/globals.css — tarjetas a ancho completo con botones apilados en móvil (tarea 8.1, vista 10/08 §Móvil)", () => {
  it(".error-card__actions (globals.css, GATEWAY_OFFLINE/QUOTA/shell) apila los botones a ancho completo", () => {
    const mobileGlobals = extractMediaBlocks(GLOBALS_CSS, "(max-width: 767px)");
    const rule = mobileGlobals.match(/\.error-card__actions\s*\{[^}]*\}/)?.[0];
    expect(rule).toBeTruthy();
    expect(rule).toMatch(/flex-direction:\s*column/);
    const btnRule = mobileGlobals.match(/\.error-card__actions \.btn\s*\{[^}]*\}/)?.[0];
    expect(btnRule).toMatch(/width:\s*100%/);
  });

  it(".escalate-card__actions (vista 08, escalación) usa el MISMO breakpoint 767px que el resto del shell/chat", () => {
    // Guarda de regresión: la tarea 5.3 había dejado un breakpoint de 640px
    // (ver openspec/BACKLOG-DESCUBRIMIENTOS.md) -- corregido en la tarea 8.1.
    expect(CHAT_CSS).not.toMatch(/@media \(max-width: 640px\)/);
    const mobileChat = extractMediaBlocks(CHAT_CSS, "(max-width: 767px)");
    const rule = mobileChat.match(/\.escalate-card__actions\s*\{[^}]*\}/)?.[0];
    expect(rule).toBeTruthy();
    expect(rule).toMatch(/flex-direction:\s*column-reverse/);
  });
});

describe("history.css — buscador colapsado a ícono y menú de acciones por long-press en móvil (tarea 8.2, vista 12 §Móvil)", () => {
  const MOBILE_HISTORY_CSS = extractMediaBlocks(HISTORY_CSS, "(max-width: 767px)");

  it(".history-search-toggle (ícono de búsqueda) está oculto por defecto y visible solo en móvil", () => {
    expect(HISTORY_CSS).toMatch(/\.history-search-toggle\s*\{\s*display:\s*none;\s*\}/);
    const rule = MOBILE_HISTORY_CSS.match(/\.history-search-toggle\s*\{[^}]*\}/)?.[0];
    expect(rule).toBeTruthy();
    expect(rule).toMatch(/display:\s*(inline-flex|flex|block)/);
  });

  it(".history-toolbar__search se oculta en móvil salvo con la clase .is-expanded", () => {
    const collapsed = MOBILE_HISTORY_CSS.match(/\.history-toolbar__search\s*\{[^}]*\}/)?.[0];
    expect(collapsed).toMatch(/display:\s*none/);
    const expanded = MOBILE_HISTORY_CSS.match(/\.history-toolbar__search\.is-expanded\s*\{[^}]*\}/)?.[0];
    expect(expanded).toBeTruthy();
    expect(expanded).not.toMatch(/display:\s*none/);
  });

  it(".history-row__actions (menú ⋯ de la fila) está oculto en desktop y visible en móvil", () => {
    expect(HISTORY_CSS).toMatch(/\.history-row__actions\s*\{\s*display:\s*none;\s*\}/);
    const rule = MOBILE_HISTORY_CSS.match(/\.history-row__actions\s*\{[^}]*\}/)?.[0];
    expect(rule).toBeTruthy();
    expect(rule).toMatch(/display:\s*flex/);
  });

  it("el disparador del menú de la fila (.history-row__menu-trigger) cumple el objetivo táctil ≥44px", () => {
    const rule = MOBILE_HISTORY_CSS.match(/\.history-row__menu-trigger\s*\{[^}]*\}/)?.[0];
    expect(rule).toBeTruthy();
    expect(rule).toMatch(/min-width:\s*var\(--touch-target-min\)/);
    expect(rule).toMatch(/min-height:\s*var\(--touch-target-min\)/);
  });
});
