"use client";

import ReactMarkdown, { type Components } from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import rehypeSanitize from "rehype-sanitize";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";
import { ALLOWED_MARKDOWN_ELEMENTS, markdownSanitizeSchema } from "./markdown-sanitize-schema";

export type MarkdownContentVariant = "agent" | "user";

export interface MarkdownContentProps {
  /**
   * Markdown crudo: del agente en streaming, o el eco del texto del
   * usuario. Tarea 3.2 (d13-chat-conversacion): la MISMA sanitización se
   * aplica a ambos casos (`variant` solo cambia la clase CSS del
   * contenedor, nunca el pipeline de renderizado/sanitización). NUNCA se
   * inserta con `dangerouslySetInnerHTML`: `react-markdown` parsea a un AST
   * (mdast -> hast) que `rehype-sanitize` filtra con la lista blanca
   * explícita de `markdown-sanitize-schema.ts` ANTES de que
   * `react-markdown` lo convierta a elementos React reales.
   */
  content: string;
  variant?: MarkdownContentVariant;
  className?: string;
}

// Copia mutable para la prop `allowedElements` de react-markdown (la
// constante exportada es una tupla `readonly` -- ver
// `markdown-sanitize-schema.ts`). Definida a nivel de módulo para no
// recrear el array en cada render.
const ALLOWED_ELEMENTS_LIST: string[] = [...ALLOWED_MARKDOWN_ELEMENTS];

// Solo http/https/mailto sobreviven (tarea 3.2: "URLs: solo http/https/mailto,
// nada de javascript:"). Reimplementación del algoritmo de
// `defaultUrlTransform` de react-markdown (un ':' antes del primer '/', '?'
// o '#' se interpreta como esquema; sin eso, la URL es relativa y se deja
// pasar tal cual) pero con la lista de protocolos restringida -- el default
// de la librería también permite `irc(s)`/`xmpp`, más de lo que pide esta
// tarea. Actúa ADEMÁS de -- no en lugar de -- `protocols.href` del schema
// de sanitize (`markdown-sanitize-schema.ts`): dos mecanismos
// independientes bloqueando el mismo vector.
const ALLOWED_URL_PROTOCOLS = new Set(["http", "https", "mailto"]);

function sanitizeUrl(url: string): string {
  const colon = url.indexOf(":");
  const questionMark = url.indexOf("?");
  const numberSign = url.indexOf("#");
  const slash = url.indexOf("/");

  const looksRelative =
    colon < 0 ||
    (slash > -1 && colon > slash) ||
    (questionMark > -1 && colon > questionMark) ||
    (numberSign > -1 && colon > numberSign);

  if (looksRelative) return url;

  const scheme = url.slice(0, colon).toLowerCase();
  return ALLOWED_URL_PROTOCOLS.has(scheme) ? url : "";
}

// Enlaces con `target="_blank"` reforzados con `rel="noopener noreferrer"`
// (evita que la pestaña nueva pueda navegar la original vía `window.opener`).
// `table` se envuelve en un contenedor con scroll horizontal propio (nunca
// desborda el body -- ver styles/components/chat.css `.md-table-scroll`).
const markdownComponents: Components = {
  a({ href, children, ...rest }) {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer" {...rest}>
        {children}
      </a>
    );
  },
  table({ children, ...rest }) {
    return (
      <div className="md-table-scroll">
        <table {...rest}>{children}</table>
      </div>
    );
  },
};

/**
 * Renderizador de markdown sanitizado (tareas 3.1/3.2). Soporta negritas,
 * listas, tablas, bloques de código con highlighting por lenguaje (vía
 * `rehype-highlight`, que resalta a nivel de AST -- ya no hay HTML crudo
 * que sanitizar aparte del que produce el propio pipeline) y saltos de
 * línea simples preservados (`remark-breaks`, vista 05: "texto plano con
 * saltos" para el eco del usuario).
 *
 * Orden del pipeline (importa): `rehypeHighlight` corre ANTES que
 * `rehypeSanitize` -- así el highlighting ya sucedió sobre el AST cuando
 * sanitize hace su pasada final; el schema de sanitize sabe exactamente
 * qué clases de highlight.js dejar pasar (`markdown-sanitize-schema.ts`).
 * Sanitize es SIEMPRE el último paso antes de que react-markdown convierta
 * el árbol a elementos React: es el gate final e incondicional.
 */
export function MarkdownContent({ content, variant = "agent", className }: MarkdownContentProps) {
  return (
    <div
      className={["md-content", `md-content--${variant}`, className].filter(Boolean).join(" ")}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkBreaks]}
        rehypePlugins={[rehypeHighlight, [rehypeSanitize, markdownSanitizeSchema]]}
        allowedElements={ALLOWED_ELEMENTS_LIST}
        skipHtml
        urlTransform={sanitizeUrl}
        components={markdownComponents}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
