import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { VisibleToolCallView } from "@/lib/chat/types";
import { ToolCallLine, type ToolCallLineLabels } from "./tool-call-line";

/**
 * Tarea 5.2 de d13-chat-conversacion: tool calls colapsadas/expandibles
 * consumiendo el contrato `tool-call-visibility` de c09-mcp-tools
 * (`resultarai/core/audit/visibility.py`, `render_for_role`) -- lenguaje
 * simple + resultado truncado para Funcional, parámetros completos +
 * latencia para Técnico/Admin, EL MISMO `VisibleToolCallView`.
 */

const LABELS: ToolCallLineLabels = {
  parametersLabel: "Parámetros",
  latencyLabel: "Latencia:",
};

/** Fixture conforme al contrato c09: `parameters` completos (como los
 * vería Técnico/Admin -- ver el docstring de `VisibleToolCallView` sobre
 * por qué el gateo de Funcional vive en el componente, no en el dato). */
const CALL: VisibleToolCallView = {
  tool_name: "buscar_documentacion",
  status: "executed",
  status_label: "ejecutada",
  simple_description:
    "Se consultó «buscar_documentacion». Resultado: MATA010 — Parámetros de localización, 3 coincidencias.",
  parameters: { query: "MV_PAISLOC", repo: "TDN" },
  result_preview: "MATA010 — Parámetros de localización, 3 coincidencias.",
  duration_ms: 820,
};

const PENDING_APPROVAL_CALL: VisibleToolCallView = {
  tool_name: "actualizar_parametro",
  status: "pending_approval",
  status_label: "en espera de aprobación",
  simple_description: "Se intentó usar «actualizar_parametro»; está en espera de aprobación.",
  parameters: { campo: "MV_PAISLOC", valor: "BOL" },
  result_preview: null,
  duration_ms: null,
};

describe("ToolCallLine — colapsada por defecto (tarea 5.2)", () => {
  it("muestra el nombre de la tool y su estado, en lenguaje simple y sin el resultado ni parámetros", () => {
    render(<ToolCallLine call={CALL} role="tecnico" labels={LABELS} />);

    const trigger = screen.getByRole("button", { name: /buscar_documentacion/ });
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
    expect(screen.getByText(/ejecutada/)).toBeTruthy();
    expect(screen.queryByText(CALL.simple_description)).toBeNull();
    expect(screen.queryByText(LABELS.parametersLabel)).toBeNull();
  });

  it("una escritura escalada se muestra 'en espera de aprobación', nunca como ejecutada (c09)", () => {
    render(<ToolCallLine call={PENDING_APPROVAL_CALL} role="admin" labels={LABELS} />);
    expect(screen.getByText(/en espera de aprobación/)).toBeTruthy();
  });
});

describe("ToolCallLine — capa Funcional (tarea 5.2 / c09 've la tool call en lenguaje simple')", () => {
  it("al expandir ve una descripción en lenguaje simple con el resultado truncado, sin parámetros en el DOM", async () => {
    const user = userEvent.setup();
    render(<ToolCallLine call={CALL} role="funcional" labels={LABELS} />);

    await user.click(screen.getByRole("button", { name: /buscar_documentacion/ }));

    expect(screen.getByText(CALL.simple_description)).toBeTruthy();
    expect(screen.queryByText(LABELS.parametersLabel)).toBeNull();
    expect(document.body.innerHTML).not.toContain("MV_PAISLOC");
    expect(screen.queryByText(LABELS.latencyLabel)).toBeNull();
  });
});

describe("ToolCallLine — capa Técnico/Admin (tarea 5.2 / c09 'ven parámetros completos')", () => {
  it("Técnico: al expandir la MISMA tool call ve además los parámetros completos y la latencia", async () => {
    const user = userEvent.setup();
    render(<ToolCallLine call={CALL} role="tecnico" labels={LABELS} />);

    await user.click(screen.getByRole("button", { name: /buscar_documentacion/ }));

    expect(screen.getByText(CALL.simple_description)).toBeTruthy();
    expect(screen.getByText(LABELS.parametersLabel)).toBeTruthy();
    expect(screen.getByText(/"query": "MV_PAISLOC"/)).toBeTruthy();
    expect(screen.getByText(/Latencia:\s*0,8 s/)).toBeTruthy();
  });

  it("Admin: mismo comportamiento que Técnico", async () => {
    const user = userEvent.setup();
    render(<ToolCallLine call={CALL} role="admin" labels={LABELS} />);

    await user.click(screen.getByRole("button", { name: /buscar_documentacion/ }));

    expect(screen.getByText(LABELS.parametersLabel)).toBeTruthy();
    expect(screen.getByText(/"repo": "TDN"/)).toBeTruthy();
  });
});

describe("ToolCallLine — plegado/expansión accesible por teclado (tarea 5.2)", () => {
  it("Enter en el botón enfocado alterna aria-expanded y revela el detalle", async () => {
    const user = userEvent.setup();
    render(<ToolCallLine call={CALL} role="funcional" labels={LABELS} />);

    const trigger = screen.getByRole("button", { name: /buscar_documentacion/ });
    trigger.focus();
    expect(document.activeElement).toBe(trigger);

    await user.keyboard("{Enter}");
    expect(trigger.getAttribute("aria-expanded")).toBe("true");
    expect(screen.getByText(CALL.simple_description)).toBeTruthy();

    await user.keyboard(" ");
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByText(CALL.simple_description)).toBeNull();
  });
});
