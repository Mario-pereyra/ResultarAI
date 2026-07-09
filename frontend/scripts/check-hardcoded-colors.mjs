#!/usr/bin/env node
/**
 * check-hardcoded-colors.mjs — Auditoría estática de colores hardcodeados
 * (d10-design-system-shell, tarea 4.9).
 *
 * Escanea frontend/{app,components,styles}/** buscando valores de color
 * literales (hex #abc/#aabbcc[aa], rgb(/rgba(/hsl(/hsla() fuera de la capa
 * de tokens (styles/tokens.css, la única fuente de verdad de valores de
 * color — excluida a propósito). Sale con código != 0 y lista
 * archivo:línea si encuentra alguna coincidencia.
 *
 * Escenario cubierto: "Auditoría estática sin hex hardcodeado"
 * (openspec/changes/d10-design-system-shell/specs/design-system/spec.md).
 *
 * Node puro (sin dependencias): se ejecuta con `node scripts/check-hardcoded-colors.mjs`
 * desde frontend/, o vía `npm run audit:colors`.
 */

import { readdirSync, readFileSync, statSync } from "node:fs";
import { extname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = fileURLToPath(new URL(".", import.meta.url));
const frontendRoot = join(scriptDir, "..");

// Directorios de frontend/ a escanear (relativos a frontendRoot).
const SCAN_DIRS = ["app", "components", "styles"];

// Extensiones donde puede aparecer un color: CSS de componentes y
// código React/TS (que NUNCA debería tener estilos inline con colores).
const SCANNED_EXTENSIONS = new Set([".css", ".ts", ".tsx", ".js", ".jsx", ".mjs"]);

// Único archivo excluido: la capa de tokens es la fuente de verdad de
// valores de color (design/mockups/tokens.css, portado 1:1).
const EXCLUDED_FILES = new Set([join(frontendRoot, "styles", "tokens.css")]);

// hex de 3 a 8 dígitos (#abc, #aabbcc, #aabbccdd) + rgb()/rgba()/hsl()/hsla().
const COLOR_PATTERN = /#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(/g;

function collectFiles(dir, files = []) {
  let entries;
  try {
    entries = readdirSync(dir);
  } catch {
    // El directorio puede no existir todavía (p. ej. components/ antes de
    // esta tarea); no es un error de la auditoría.
    return files;
  }

  for (const entry of entries) {
    const fullPath = join(dir, entry);
    const info = statSync(fullPath);

    if (info.isDirectory()) {
      collectFiles(fullPath, files);
    } else if (SCANNED_EXTENSIONS.has(extname(entry))) {
      files.push(fullPath);
    }
  }

  return files;
}

function findColorLiterals(filePath) {
  const content = readFileSync(filePath, "utf8");
  const lines = content.split("\n");
  const matches = [];

  lines.forEach((line, index) => {
    if (COLOR_PATTERN.test(line)) {
      matches.push({ line: index + 1, snippet: line.trim() });
    }
    // Los regex con flag global mantienen estado (lastIndex) entre llamadas
    // a .test(); se resetea explícitamente por línea para evitar falsos
    // negativos intermitentes.
    COLOR_PATTERN.lastIndex = 0;
  });

  return matches;
}

function main() {
  const files = SCAN_DIRS.flatMap((dir) => collectFiles(join(frontendRoot, dir)));
  const findings = [];

  for (const file of files) {
    if (EXCLUDED_FILES.has(file)) continue;

    for (const match of findColorLiterals(file)) {
      findings.push({
        file: relative(frontendRoot, file),
        line: match.line,
        snippet: match.snippet,
      });
    }
  }

  if (findings.length > 0) {
    console.error(
      `\nAuditoría de colores: ${findings.length} coincidencia(s) de color hardcodeado fuera de styles/tokens.css:\n`,
    );
    for (const finding of findings) {
      console.error(`  ${finding.file}:${finding.line}  ${finding.snippet}`);
    }
    console.error(
      "\nLa capa de componentes debe consumir solo var(--token). Reemplazá el valor literal por el token semántico equivalente (ver styles/tokens.css).\n",
    );
    process.exitCode = 1;
    return;
  }

  console.log(
    "Auditoría de colores: sin coincidencias. Todos los componentes consumen tokens semánticos.",
  );
}

main();
