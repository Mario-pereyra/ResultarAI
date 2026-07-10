import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { beforeEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MarkdownContent } from "./markdown-content";

declare global {
  interface Window {
    __pwned?: boolean;
  }
}

const SCRIPT_PAYLOAD = "<script>window.__pwned = true;</script>";
const IMG_ONERROR_PAYLOAD = '<img src="x" onerror="window.__pwned = true;">';
const JS_LINK_PAYLOAD = "[click acá](javascript:alert(1))";

const ADVERSARIAL_MARKDOWN = [
  "Texto seguro antes.",
  "",
  SCRIPT_PAYLOAD,
  "",
  IMG_ONERROR_PAYLOAD,
  "",
  JS_LINK_PAYLOAD,
  "",
  "Texto seguro después.",
].join("\n");

// Prueba adversarial de la tarea 3.2 (d13-chat-conversacion): un payload
// tipo `<script>`/`onerror=`/`javascript:` no debe ejecutarse ni aparecer
// como HTML activo -- ni en el texto del agente ni en el eco del mensaje
// del usuario (design.md decisión 6: MISMA sanitización para ambos casos).
describe("MarkdownContent — sanitización anti-XSS (tarea 3.2)", () => {
  beforeEach(() => {
    window.__pwned = undefined;
  });

  it.each(["agent", "user"] as const)(
    "un payload adversarial no ejecuta ni aparece como HTML activo (variant=%s)",
    (variant) => {
      const { container } = render(
        <MarkdownContent content={ADVERSARIAL_MARKDOWN} variant={variant} />,
      );

      // Nunca se ejecutó el script embebido.
      expect(window.__pwned).toBeUndefined();

      // Ningún <script> real en el DOM.
      expect(container.querySelector("script")).toBeNull();

      // Ningún atributo de evento sobrevivió (onerror/onclick/...).
      expect(container.querySelector("[onerror]")).toBeNull();
      expect(container.innerHTML).not.toContain("onerror=");

      // El link peligroso queda neutralizado: nunca aparece "javascript:"
      // en ningún href, y no sobrevive ningún <a> con ese esquema.
      expect(container.querySelector('a[href^="javascript:"]')).toBeNull();
      expect(container.innerHTML.toLowerCase()).not.toContain("javascript:");

      // El contenido benigno alrededor SÍ sobrevive -- prueba de que la
      // sanitización filtra lo peligroso sin vaciar todo el árbol (lo que
      // haría que las aserciones de arriba "pasaran" trivialmente).
      expect(screen.getByText("Texto seguro antes.")).toBeTruthy();
      expect(screen.getByText("Texto seguro después.")).toBeTruthy();
    },
  );

  it("nunca usa dangerouslySetInnerHTML/innerHTML con el markdown crudo", () => {
    // El propio módulo no debe contener la API prohibida (design.md
    // decisión 6): una aserción sobre el código fuente en vez de sobre el
    // DOM, como red de seguridad adicional ante un futuro cambio del
    // componente que reintroduzca el patrón peligroso.
    const path = resolve(process.cwd(), "components/chat/markdown-content.tsx");
    const source = readFileSync(path, "utf8");
    // Se busca el patrón de USO real (prop JSX / asignación), no la
    // palabra suelta -- el docstring del componente la menciona en prosa
    // para explicar justamente que nunca se usa.
    expect(source).not.toContain("dangerouslySetInnerHTML={");
    expect(source).not.toContain(".innerHTML =");
  });
});

describe("MarkdownContent — renderizado de markdown legítimo", () => {
  it("renderiza tablas, negritas y bloques de código con highlighting sin alterarlos", () => {
    const markdown = [
      "**importante**",
      "",
      "| Columna A | Columna B |",
      "| --- | --- |",
      "| uno | dos |",
      "",
      "```python",
      "def saludo():",
      '    return "hola"',
      "```",
    ].join("\n");

    const { container } = render(<MarkdownContent content={markdown} />);

    expect(container.querySelector("table")).not.toBeNull();
    expect(container.querySelectorAll("td")).toHaveLength(2);
    expect(container.querySelector("strong")?.textContent).toBe("importante");

    const codeEl = container.querySelector("code.language-python");
    expect(codeEl).not.toBeNull();
    expect(codeEl?.classList.contains("hljs")).toBe(true);
    expect(container.querySelector(".hljs-keyword")).not.toBeNull();
  });

  it("permite un link seguro con target=_blank y rel reforzado", () => {
    const { container } = render(<MarkdownContent content="[TDN](https://tdn.totvs.com)" />);
    const link = container.querySelector("a");
    expect(link).not.toBeNull();
    expect(link?.getAttribute("href")).toBe("https://tdn.totvs.com");
    expect(link?.getAttribute("target")).toBe("_blank");
    expect(link?.getAttribute("rel")).toContain("noopener");
  });
});
