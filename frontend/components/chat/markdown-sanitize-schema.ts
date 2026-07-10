import type { Options as SanitizeSchema } from "rehype-sanitize";

/**
 * Lista blanca de nodos/atributos aplicada al AST del markdown ANTES de
 * renderizar (tarea 3.2 de d13-chat-conversacion, decisión 6 de design.md).
 *
 * `rehype-sanitize` recorre el hast tree ya generado por `remark-gfm` +
 * `rehype-highlight` (nunca HTML crudo: `markdown-content.tsx` nunca
 * habilita `rehype-raw` ni usa `dangerouslySetInnerHTML`) y elimina
 * cualquier nodo/atributo que no esté declarado acá.
 *
 * A propósito NO se parte de `defaultSchema` (el schema "estilo GitHub" que
 * exporta `rehype-sanitize`): es más amplio de lo que este chat necesita
 * (permite `details/summary`, `sub/sup`, `input`, atributos extendidos de
 * `id`/`align`, protocolos adicionales como `irc`/`xmpp`, etc.). Se declara
 * un esquema propio, mínimo y auditable, con exactamente los elementos que
 * pide `design/VISTAS/02-chat.md` vista 05 (negritas, listas, tablas,
 * bloques de código con highlighting, enlaces) — ver
 * `hast-util-sanitize`: cuando una clave de nivel superior del schema SÍ se
 * declara (como `attributes`/`protocols`/`tagNames` acá), reemplaza por
 * completo a la del default para esa clave, no se mezcla campo a campo; las
 * claves que se omiten (`ancestors`, `clobber`, ...) sí heredan el default
 * (p. ej. la exigencia de que `tbody`/`tr` vivan dentro de `table` se
 * mantiene).
 */

// Clases que `rehype-highlight` agrega a los <span> de cada token
// resaltado dentro de un bloque de código (prefijo `hljs-`, ver su propio
// README §CSS). Sin esta lista, la sanitización posterior a la
// resaltación (que corre DESPUÉS en el pipeline, ver `markdown-content.tsx`)
// eliminaría las clases y el highlighting desaparecería.
const HLJS_TOKEN_CLASSES = [
  "hljs-addition",
  "hljs-attr",
  "hljs-attribute",
  "hljs-built_in",
  "hljs-bullet",
  "hljs-char",
  "hljs-code",
  "hljs-comment",
  "hljs-deletion",
  "hljs-doctag",
  "hljs-emphasis",
  "hljs-formula",
  "hljs-keyword",
  "hljs-link",
  "hljs-literal",
  "hljs-meta",
  "hljs-name",
  "hljs-number",
  "hljs-operator",
  "hljs-params",
  "hljs-property",
  "hljs-punctuation",
  "hljs-quote",
  "hljs-regexp",
  "hljs-section",
  "hljs-selector-attr",
  "hljs-selector-class",
  "hljs-selector-id",
  "hljs-selector-pseudo",
  "hljs-selector-tag",
  "hljs-string",
  "hljs-strong",
  "hljs-subst",
  "hljs-symbol",
  "hljs-tag",
  "hljs-template-tag",
  "hljs-template-variable",
  "hljs-title",
  "hljs-type",
  "hljs-variable",
] as const;

/**
 * Nodos permitidos. También se pasa como `allowedElements` a
 * `react-markdown` (capa adicional: lo que no está acá ni siquiera se
 * intenta mapear a un componente de React — ver `markdown-content.tsx`).
 * Deliberadamente NO incluye `img`/`input`: los adjuntos/imágenes tienen su
 * propio pipeline dedicado (`d14-attachments`, chips con vista previa, no
 * imágenes inline en el markdown de la respuesta) y las listas de tareas
 * (`- [ ] ...`) no forman parte del alcance de esta tarea — reduce
 * superficie sin perder nada que pida la vista 05.
 *
 * `span` SÍ está incluido pese a no venir nunca del markdown del usuario:
 * es el elemento que `rehype-highlight` usa para envolver cada token
 * resaltado dentro de un bloque de código (`<span class="hljs-keyword">`,
 * ...). Sin `span` en esta lista, `rehype-sanitize`/`allowedElements` lo
 * eliminarían (desenvolviendo el texto, perdiendo el highlighting) aunque
 * sus clases sí estuvieran permitidas en `attributes.span` -- el atributo
 * no importa si el propio nodo ya se descarta.
 */
export const ALLOWED_MARKDOWN_ELEMENTS = [
  "p",
  "br",
  "strong",
  "em",
  "del",
  "ul",
  "ol",
  "li",
  "blockquote",
  "code",
  "pre",
  "span",
  "a",
  "table",
  "thead",
  "tbody",
  "tr",
  "th",
  "td",
  "h1",
  "h2",
  "h3",
  "h4",
  "h5",
  "h6",
  "hr",
] as const;

/**
 * Esquema explícito de `rehype-sanitize`: por defecto NINGÚN atributo está
 * permitido salvo los listados acá — en particular, ningún atributo de
 * evento (`onerror`, `onclick`, `onload`, ...) puede sobrevivir nunca
 * porque no aparece en ningún lado de este mapa (a diferencia de
 * `defaultSchema`, que sí declara un puñado de atributos globales vía la
 * clave `'*'`; acá no hay clave `'*'`, así que ningún atributo es global).
 * `protocols.href` restringe los esquemas de URL a http/https/mailto
 * (nunca `javascript:`), reforzando `urlTransform` de
 * `markdown-content.tsx` — dos mecanismos independientes bloqueando el
 * mismo vector (defensa en profundidad).
 */
export const markdownSanitizeSchema: SanitizeSchema = {
  tagNames: [...ALLOWED_MARKDOWN_ELEMENTS],
  attributes: {
    a: ["href", "title"],
    ol: ["start"],
    code: [["className", /^language-[\w-]+$/, "hljs"]],
    span: [["className", ...HLJS_TOKEN_CLASSES]],
  },
  protocols: {
    href: ["http", "https", "mailto"],
  },
  // Defensa en profundidad explícita: aunque `script`/`style` ya quedan
  // fuera de `tagNames` (se eliminarían igual), `strip` asegura que si
  // alguna vez aparecieran se borre también su contenido, en vez de solo
  // "desenvolverlo" (dejar pasar el texto interno sin la etiqueta).
  strip: ["script", "style"],
};
