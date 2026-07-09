#!/usr/bin/env node
/**
 * check-contrast.ts — Verificación automatizada de contraste WCAG 2.1
 * (d10-design-system-shell, tarea 7.1).
 *
 * Parsea `styles/tokens.css`, extrae los 4 sets de tokens semánticos de
 * color (dark·default, light·default, dark·totvs, light·totvs) y calcula
 * el ratio de contraste WCAG 2.1 para cada PAR NORMATIVO de
 * `design/DESIGN-SYSTEM.md` §5.3 ("Pares de texto principales — todos
 * ≥4.5:1 (AA texto normal)"), codificados abajo en `CONTRAST_PAIRS` con
 * su umbral explícito (los 10 pares de §5.3 son todos texto normal, así
 * que el umbral es 4.5:1 en los 10 — ninguno de ellos es de los casos
 * "texto ≥24px o gráficos" a 3:1 que menciona el Requirement de
 * specs/design-system/spec.md en términos generales; si un futuro par
 * grande/gráfico se agrega a §5.3, se codifica acá con `threshold: 3`).
 *
 * Escenario cubierto: "Verificación automatizada de contraste"
 * (openspec/changes/d10-design-system-shell/specs/design-system/spec.md).
 *
 * Node ejecuta `.ts` nativamente en este toolchain (type stripping, sin
 * flags — verificado con el Node del proyecto) así que este script corre
 * igual que un `.mjs`: `node scripts/check-contrast.ts` o
 * `npm run check:contrast`. Sin dependencias nuevas.
 *
 * Si algún par falla: el script NO ajusta ningún valor de token — solo
 * reporta la lista de pares/sets que no cumplen. Ajustar un token de color
 * es una decisión de diseño (design/mockups/tokens.css es la fuente de
 * verdad), no algo que un script de verificación deba tocar.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = fileURLToPath(new URL(".", import.meta.url));
const frontendRoot = join(scriptDir, "..");
const tokensPath = join(frontendRoot, "styles", "tokens.css");

type Brand = "default" | "totvs";
type ThemeName = "dark" | "light";
type TokenSet = Record<string, string>;
type SetKey = `${ThemeName}-${Brand}`;

/**
 * Pares normativos de design/DESIGN-SYSTEM.md §5.3, con su umbral AA
 * explícito. Los 10 pares de la matriz son "texto normal" -> 4.5:1.
 */
const CONTRAST_PAIRS: Array<{ fg: string; bg: string; threshold: number }> = [
  { fg: "--ink", bg: "--bg", threshold: 4.5 },
  { fg: "--ink-dim", bg: "--panel", threshold: 4.5 },
  { fg: "--ink-faint", bg: "--panel", threshold: 4.5 },
  { fg: "--accent", bg: "--bg", threshold: 4.5 },
  { fg: "--accent-ink", bg: "--accent-fill", threshold: 4.5 },
  { fg: "--money", bg: "--bg", threshold: 4.5 },
  { fg: "--info", bg: "--bg", threshold: 4.5 },
  { fg: "--warn", bg: "--bg", threshold: 4.5 },
  { fg: "--danger", bg: "--bg", threshold: 4.5 },
  { fg: "--danger-ink", bg: "--danger", threshold: 4.5 },
];

const THEME_BRAND_BLOCK_PATTERN =
  /html\[data-theme="(dark|light)"\]\[data-brand="(default|totvs)"\]\s*\{([^}]*)\}/g;

function parseTokenSets(css: string): Record<SetKey, TokenSet> {
  const sets = {} as Record<SetKey, TokenSet>;
  let match: RegExpExecArray | null;

  while ((match = THEME_BRAND_BLOCK_PATTERN.exec(css)) !== null) {
    const [, theme, brand, body] = match;
    const key = `${theme}-${brand}` as SetKey;
    const tokens: TokenSet = {};

    const declarationPattern = /(--[a-z0-9-]+)\s*:\s*([^;]+);/g;
    let declaration: RegExpExecArray | null;
    while ((declaration = declarationPattern.exec(body)) !== null) {
      tokens[declaration[1]] = declaration[2].trim();
    }

    sets[key] = tokens;
  }

  return sets;
}

/** `#rgb` / `#rrggbb` / `rgb()` / `rgba()` -> `[r, g, b]` (0-255, alpha ignorado: los tokens de §5.3 son opacos). */
function parseColor(value: string): [number, number, number] {
  const trimmed = value.trim();

  if (trimmed.startsWith("#")) {
    let hex = trimmed.slice(1);
    if (hex.length === 3) {
      hex = hex
        .split("")
        .map((c) => c + c)
        .join("");
    }
    const r = parseInt(hex.slice(0, 2), 16);
    const g = parseInt(hex.slice(2, 4), 16);
    const b = parseInt(hex.slice(4, 6), 16);
    return [r, g, b];
  }

  const rgbaMatch = trimmed.match(/rgba?\(([^)]+)\)/);
  if (rgbaMatch) {
    const parts = rgbaMatch[1].split(",").map((part) => parseFloat(part.trim()));
    return [parts[0], parts[1], parts[2]];
  }

  throw new Error(`No se pudo interpretar el color: "${value}"`);
}

/** Luminancia relativa WCAG 2.1 (https://www.w3.org/TR/WCAG21/#dfn-relative-luminance). */
function relativeLuminance([r, g, b]: [number, number, number]): number {
  const channel = (c: number) => {
    const cs = c / 255;
    return cs <= 0.03928 ? cs / 12.92 : Math.pow((cs + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

/** Ratio de contraste WCAG 2.1 (https://www.w3.org/TR/WCAG21/#dfn-contrast-ratio). */
function contrastRatio(a: [number, number, number], b: [number, number, number]): number {
  const la = relativeLuminance(a);
  const lb = relativeLuminance(b);
  const lighter = Math.max(la, lb);
  const darker = Math.min(la, lb);
  return (lighter + 0.05) / (darker + 0.05);
}

type Failure = {
  set: SetKey;
  pair: string;
  ratio: number;
  threshold: number;
};

function main() {
  const css = readFileSync(tokensPath, "utf8");
  const sets = parseTokenSets(css);
  const setKeys = Object.keys(sets) as SetKey[];

  if (setKeys.length !== 4) {
    console.error(
      `Se esperaban los 4 sets de tema×brand en styles/tokens.css, se encontraron ${setKeys.length}: ${setKeys.join(", ")}`,
    );
    process.exitCode = 1;
    return;
  }

  const failures: Failure[] = [];
  let checkedCount = 0;

  for (const setKey of setKeys) {
    const tokens = sets[setKey];

    for (const { fg, bg, threshold } of CONTRAST_PAIRS) {
      const fgValue = tokens[fg];
      const bgValue = tokens[bg];

      if (!fgValue || !bgValue) {
        failures.push({ set: setKey, pair: `${fg} / ${bg}`, ratio: NaN, threshold });
        continue;
      }

      const ratio = contrastRatio(parseColor(fgValue), parseColor(bgValue));
      checkedCount += 1;

      if (ratio < threshold) {
        failures.push({ set: setKey, pair: `${fg} / ${bg}`, ratio, threshold });
      }
    }
  }

  console.log(
    `Verificación de contraste: ${checkedCount} par(es) calculados sobre ${setKeys.length} sets ` +
      `(${CONTRAST_PAIRS.length} pares normativos de design/DESIGN-SYSTEM.md §5.3 × ${setKeys.length} sets tema×brand).`,
  );

  if (failures.length > 0) {
    console.error(`\n${failures.length} par(es) NO cumplen el umbral AA:\n`);
    for (const failure of failures) {
      const ratioText = Number.isNaN(failure.ratio) ? "token faltante" : `${failure.ratio.toFixed(2)}:1`;
      console.error(`  [${failure.set}] ${failure.pair} — ${ratioText} (mínimo ${failure.threshold}:1)`);
    }
    console.error(
      "\nEste script NO ajusta tokens.css: si un par verbatim del design falla, es un hallazgo a reportar, " +
        "no algo para \"arreglar\" acá — revisar primero que el par/umbral copiado coincida con design/DESIGN-SYSTEM.md §5.3.\n",
    );
    process.exitCode = 1;
    return;
  }

  console.log("Todos los pares cumplen el umbral AA en los 4 sets.");
}

main();
