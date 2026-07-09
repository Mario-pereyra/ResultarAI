#!/usr/bin/env node
/**
 * check-hardcoded-strings.mjs — Auditoría heurística de strings de usuario
 * hardcodeados (d10-design-system-shell, tarea 6.1).
 *
 * Escanea frontend/{app,components/shell}/** (excluyendo *.test.{ts,tsx}
 * y `messages/*.json`, que SON el catálogo) buscando texto de usuario
 * literal en JSX/TSX que no venga de una clave de catálogo (`t("...")`) ni
 * de una prop recibida desde quien llama al componente.
 *
 * NO se escanea `components/ui/**`: esos componentes reciben todo su texto
 * por props (label, hint, error, children, etc.) — ahí SIEMPRE hay
 * strings porque son los VALORES que ya vienen del catálogo un nivel más
 * arriba; auditar sus props produciría solo falsos positivos. Ver
 * `frontend/README.md` § i18n y la tarea 6.1 en
 * openspec/changes/d10-design-system-shell/tasks.md.
 *
 * Escenario cubierto: "Auditoría de strings hardcodeados"
 * (openspec/changes/d10-design-system-shell/specs/i18n-foundation/spec.md).
 *
 * ── Heurística (documentada a propósito: es un scanner de texto, no un
 *    parser AST/JSX real — mismo criterio de simplicidad que
 *    check-hardcoded-colors.mjs) ──
 *
 * 1. Se quitan primero los comentarios (`// …` y `/* … *\/`) — este repo
 *    escribe TODOS sus comentarios en español (CLAUDE.md regla 9), así que
 *    sin este paso cualquier prosa de comentario que mencione un tag HTML
 *    entre ejemplos ("... se aplica en <html> ...") se confunde con JSX
 *    real. Se reemplazan por espacios/saltos de línea (no se borran) para
 *    no correr los números de línea de los hallazgos reales.
 * 2. Se quitan genéricos de TypeScript con forma `Identificador<...>`
 *    (`Promise<Metadata>`, `SVGProps<SVGSVGElement>`, `Record<Section,
 *    ReactNode>`, `Record<K, { title: string }>` con tipo objeto anidado,
 *    `useFocusTrap<T extends HTMLElement>`) escaneando profundidad de
 *    `{}` real (no un regex de un solo nivel) — si no, sus `<`/`>` se
 *    confunden con apertura/cierre de tag JSX.
 * 3. Con el archivo ya limpio de comentarios/genéricos, se identifican los
 *    tags `<...>` (abriendo, cerrando `</...>` o autocerrado `.../>`) y se
 *    toma como candidato de texto SOLO lo que queda entre un tag de
 *    APERTURA real y el siguiente tag — nunca lo que sigue a uno de
 *    cierre/autocerrado (`<Icon />` no tiene hijos; después de `</Icon>`
 *    ya volvimos al padre). Sin esta distinción, cualquier `>` de un ícono
 *    autocerrado (omnipresentes en `components/shell/icons.tsx`) "abre"
 *    por error una búsqueda de texto que termina agarrando código real
 *    (la siguiente función, sus identificadores) como si fuera contenido
 *    JSX.
 * 4. Dentro de cada candidato de texto encontrado se vacían (sin desplazar
 *    índices) los bloques `{expresión}` — así un caso mixto como
 *    `<span>{count} pendientes</span>` sigue detectando " pendientes" como
 *    texto literal.
 * 5. Los atributos JSX "portadores de texto" (`aria-label`,
 *    `aria-valuetext`, `placeholder`, `alt`, `title`) con valor de string
 *    literal se auditan aparte, directamente sobre el archivo ya limpio de
 *    comentarios/genéricos.
 * 6. Se descarta un candidato si: mide 0 caracteres tras trim, no tiene
 *    ninguna letra minúscula (el design system exige sentence case en
 *    todo texto de UI — DESIGN-SYSTEM.md §4.2 — así que un candidato
 *    100% mayúsculas/símbolos/dígitos casi nunca es una oración
 *    traducible: cubre siglas, códigos de error `GATEWAY_OFFLINE`,
 *    iniciales de logo), o supera los 160 caracteres (indicio de que el
 *    parser simplificado igual quedó "pegado" entre dos tags lejanos —
 *    mejor un falso negativo puntual que un ruido enorme en el reporte).
 *
 * Limitación conocida y cómo correr el triage manual: al no ser un parser
 * JSX real, construcciones poco comunes (JSX multilínea con el texto
 * partido raro, comentarios dentro de un string) pueden seguir dando
 * falso positivo/negativo ocasional. Si el script marca algo dudoso,
 * revisar el archivo:línea señalado a mano — `node scripts/check-hardcoded-strings.mjs`
 * imprime archivo, línea y el snippet exacto que disparó la regla.
 */

import { readdirSync, readFileSync, statSync } from "node:fs";
import { extname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = fileURLToPath(new URL(".", import.meta.url));
const frontendRoot = join(scriptDir, "..");

// Directorios auditados (relativos a frontendRoot) — ver nota de cabecera
// sobre por qué components/ui/** queda fuera.
const SCAN_DIRS = [join("app"), join("components", "shell")];

const SCANNED_EXTENSIONS = new Set([".tsx", ".ts"]);
const TEST_FILE_PATTERN = /\.test\.tsx?$/;

// Atributos JSX que portan texto visible/anunciado al usuario.
const TEXT_ATTRIBUTES = ["aria-label", "aria-valuetext", "placeholder", "alt", "title"];
const ATTRIBUTE_PATTERN = new RegExp(
  `\\b(${TEXT_ATTRIBUTES.join("|")})=(["'])([^"'{}]*)\\2`,
  "g",
);

const MAX_CANDIDATE_LENGTH = 160;

function collectFiles(dir, files = []) {
  let entries;
  try {
    entries = readdirSync(dir);
  } catch {
    return files;
  }

  for (const entry of entries) {
    const fullPath = join(dir, entry);
    const info = statSync(fullPath);

    if (info.isDirectory()) {
      collectFiles(fullPath, files);
    } else if (SCANNED_EXTENSIONS.has(extname(entry)) && !TEST_FILE_PATTERN.test(entry)) {
      files.push(fullPath);
    }
  }

  return files;
}

/** Reemplaza cada carácter no-salto-de-línea por un espacio (preserva offsets/líneas). */
function blank(text) {
  return text.replace(/[^\n]/g, " ");
}

/** Quita `/* … *\/` y `// …`, preservando saltos de línea para no correr los números de línea. */
function stripComments(content) {
  let result = content.replace(/\/\*[\s\S]*?\*\//g, blank);
  result = result.replace(/\/\/[^\n]*/g, blank);
  return result;
}

/**
 * Quita `Identificador<...>` (genéricos TS: `Promise<Metadata>`,
 * `Record<ToastVariant, { title: string; message: string }>`,
 * `useFocusTrap<T extends HTMLElement>`) escaneando carácter a carácter en
 * vez de con un regex de un solo nivel — un genérico puede traer un TIPO
 * OBJETO anidado con sus propias `{}` (`Record<K, { a: string }>`), que un
 * regex `[^<>{}]*` no puede cruzar. Un genérico se reconoce por tener un
 * carácter de identificador PEGADO inmediatamente a la izquierda del `<`
 * (nunca es así en un tag JSX real, que siempre tiene espacio/salto de
 * línea/otro tag antes del `<`).
 */
function stripGenerics(content) {
  let result = "";
  let i = 0;
  while (i < content.length) {
    const previous = content[i - 1];
    const isGenericStart = content[i] === "<" && previous !== undefined && /[\w$]/.test(previous);

    if (isGenericStart) {
      let depth = 0;
      let j = i + 1;
      let closedAt = -1;
      for (; j < content.length; j += 1) {
        const char = content[j];
        if (char === "{") depth += 1;
        else if (char === "}") depth = Math.max(0, depth - 1);
        else if (char === ">" && depth === 0) {
          closedAt = j + 1;
          break;
        } else if (char === ";" && depth === 0) {
          break; // No parece un genérico bien formado — no consumir de más.
        }
      }
      if (closedAt !== -1) {
        result += blank(content.slice(i, closedAt));
        i = closedAt;
        continue;
      }
    }

    result += content[i];
    i += 1;
  }
  return result;
}

/**
 * Vacía (sin desplazar índices) los bloques `{...}` DENTRO de un candidato
 * ya delimitado por `>`/`<` — nunca se llama sobre el archivo completo
 * (ver nota de cabecera "Ojo").
 */
function blankExpressionBlocks(content) {
  let result = "";
  let depth = 0;
  for (const char of content) {
    if (char === "{") {
      depth += 1;
      result += " ";
    } else if (char === "}") {
      depth = Math.max(0, depth - 1);
      result += " ";
    } else if (depth > 0) {
      result += char === "\n" ? "\n" : " ";
    } else {
      result += char;
    }
  }
  return result;
}

/** ¿El candidato tiene al menos una letra minúscula (sentence case real)? */
function looksTranslatable(text) {
  if (text.length === 0 || text.length > MAX_CANDIDATE_LENGTH) return false;
  const letters = text.replace(/[^\p{L}]/gu, "");
  if (letters.length < 2) return false;
  return /\p{Ll}/u.test(letters);
}

function lineAt(content, index) {
  return content.slice(0, index).split("\n").length;
}

/**
 * Encuentra tags `<...>`: apertura (`<Name ...>`), cierre (`</Name>`) o
 * autocerrado (`<Name ... />`) — ver punto 3 de la heurística en la
 * cabecera del archivo para por qué hace falta distinguirlos.
 *
 * No es un regex: el contenido entre `<`/`>` de un tag NO es "cualquier
 * char que no sea `<`/`>`" — una prop like `onClick={() => setOpen(false)}`
 * tiene un `>` real (el de `=>`) DENTRO del atributo, y una prop como
 * `items={[{ onSelect: () => {} }]}` anida `{}` varios niveles (objeto
 * dentro de array dentro de expresión, con una función vacía adentro). Un
 * regex de un solo nivel no alcanza; acá se escanea carácter a carácter
 * llevando la profundidad de `{}` y solo se considera "cierre real" del
 * tag a un `>` visto con profundidad 0 (cualquier `<`/`>` dentro de una
 * expresión `{...}`, sin importar cuán anidada, se ignora).
 */
function scanTags(content) {
  const tags = [];
  let i = 0;
  while (i < content.length) {
    const next = content[i + 1];
    const looksLikeTagStart = content[i] === "<" && (next === "/" || /[A-Za-z]/.test(next ?? ""));

    if (looksLikeTagStart) {
      const start = i;
      let depth = 0;
      let j = i + 1;
      let closedAt = -1;
      for (; j < content.length; j += 1) {
        const char = content[j];
        if (char === "{") depth += 1;
        else if (char === "}") depth = Math.max(0, depth - 1);
        else if (char === ">" && depth === 0) {
          closedAt = j + 1;
          break;
        }
      }
      if (closedAt !== -1) {
        tags.push({ index: start, text: content.slice(start, closedAt) });
        i = closedAt;
        continue;
      }
    }
    i += 1;
  }
  return tags;
}

function findJsxTextFindings(cleaned) {
  const findings = [];
  const tags = scanTags(cleaned);

  for (let i = 0; i < tags.length - 1; i += 1) {
    const tag = tags[i];
    const tagText = tag.text;
    const isClosing = tagText.startsWith("</");
    const isSelfClosing = /\/>$/.test(tagText.trimEnd());
    if (isClosing || isSelfClosing) continue;

    const start = tag.index + tagText.length;
    const end = tags[i + 1].index;
    const withoutExpressions = blankExpressionBlocks(cleaned.slice(start, end));
    const trimmed = withoutExpressions.replace(/&nbsp;/g, " ").trim().replace(/\s+/g, " ");
    if (!looksTranslatable(trimmed)) continue;

    findings.push({ line: lineAt(cleaned, start), snippet: trimmed, kind: "texto JSX" });
  }

  return findings;
}

function findAttributeFindings(originalContent, cleaned) {
  const findings = [];
  ATTRIBUTE_PATTERN.lastIndex = 0;
  let match;
  while ((match = ATTRIBUTE_PATTERN.exec(cleaned)) !== null) {
    const [, attribute, , value] = match;
    const trimmed = value.trim();
    if (!looksTranslatable(trimmed)) continue;
    findings.push({
      line: lineAt(originalContent, match.index),
      snippet: `${attribute}="${trimmed}"`,
      kind: `atributo ${attribute}`,
    });
  }
  return findings;
}

function auditFile(content) {
  const withoutComments = stripComments(content);
  const withoutGenerics = stripGenerics(withoutComments);

  return [
    ...findJsxTextFindings(withoutGenerics),
    ...findAttributeFindings(withoutComments, withoutGenerics),
  ];
}

function main() {
  const files = SCAN_DIRS.flatMap((dir) => collectFiles(join(frontendRoot, dir)));
  const allFindings = [];

  for (const file of files) {
    const content = readFileSync(file, "utf8");
    for (const finding of auditFile(content)) {
      allFindings.push({ file: relative(frontendRoot, file), ...finding });
    }
  }

  if (allFindings.length > 0) {
    console.error(
      `\nAuditoría de strings: ${allFindings.length} posible(s) texto(s) hardcodeado(s) en app/ o components/shell/:\n`,
    );
    for (const finding of allFindings) {
      console.error(`  ${finding.file}:${finding.line}  [${finding.kind}] ${finding.snippet}`);
    }
    console.error(
      '\nExternalizá el texto a messages/es.json (voseo, sentence case) y resolvelo vía t("...") ' +
        "o una prop `labels.x` ya interpolada. Si es un falso positivo (código técnico, sigla, dato " +
        "no traducible), ajustá la heurística en este script y documentá por qué.\n",
    );
    process.exitCode = 1;
    return;
  }

  console.log(
    "Auditoría de strings: sin coincidencias en app/ ni components/shell/. Todo texto de usuario " +
      "resuelve vía catálogo (messages/es.json).",
  );
}

main();
