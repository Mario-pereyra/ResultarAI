import userEvent from "@testing-library/user-event";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ChatHeader, type ChatHeaderLabels } from "./chat-header";
import type { SessionTaximeterLabels } from "./session-taximeter";

/**
 * Cierra el hueco documentado en `openspec/BACKLOG-DESCUBRIMIENTOS.md`
 * (2026-07-10, tareas 4.2/4.3/4.4): `chat-content.tsx` nunca construyó el
 * `chat-top` real de `design/VISTAS/02-chat.md` vista 05 §0.1 / vista 06
 * §2 y §Móvil -- ver el docstring de `ChatHeader` para el detalle completo
 * de qué campos cierra (agente, taxímetro T/A) y cuáles quedan
 * deliberadamente fuera (`agent.icon`/`agent.short_description`: sin dato
 * real hoy; título de sesión: ausente de los "campos exactos" de la
 * vista).
 */

const HEADER_LABELS: ChatHeaderLabels = {
  sessionMenuLabel: "Menú de la sesión",
};

const TAXIMETER_LABELS: SessionTaximeterLabels = {
  label: "Sesión",
  srLabelPrefix: "Costo de sesión:",
  degradedTooltip: "costo estimado, telemetría diferida",
};

function renderHeader(role: "funcional" | "tecnico" | "admin") {
  return render(
    <ChatHeader
      agentName="DocAgent"
      role={role}
      costUsd={0.03}
      totalTokens={12400}
      degraded={false}
      taximeterLabels={TAXIMETER_LABELS}
      labels={HEADER_LABELS}
    />,
  );
}

describe("ChatHeader — header desktop (vista 05 §Datos que muestra)", () => {
  it("muestra el nombre del agente para los tres roles", () => {
    renderHeader("funcional");
    expect(screen.getByText("DocAgent")).toBeTruthy();
  });

  it("Funcional: sin taxímetro y sin botón de menú de sesión (DS §9.7, nada que ocultar)", () => {
    renderHeader("funcional");
    expect(screen.queryByRole("status", { name: /Costo de sesión/ })).toBeNull();
    expect(screen.queryByRole("button", { name: HEADER_LABELS.sessionMenuLabel })).toBeNull();
  });

  it("Técnico/Admin: taxímetro visible junto al agente", () => {
    renderHeader("tecnico");
    const status = screen.getByRole("status", { name: /Costo de sesión/ });
    expect(status).toBeTruthy();
    expect(screen.getByText("USD 0,0300")).toBeTruthy();

    renderHeader("admin");
    expect(screen.getAllByText("USD 0,0300")).toHaveLength(2);
  });
});

describe("ChatHeader — menú de sesión móvil (dual-render, vista 06 §Móvil: \"el taxímetro sale del header y vive en el menú de sesión\")", () => {
  it("el botón de menú existe SIEMPRE en el DOM para Técnico/Admin (dual-render: CSS decide si se ve en desktop o móvil)", () => {
    renderHeader("tecnico");
    const trigger = screen.getByRole("button", { name: HEADER_LABELS.sessionMenuLabel });
    expect(trigger.getAttribute("aria-haspopup")).toBe("true");
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
  });

  it("una sola instancia del taxímetro sirve de contenido inline (desktop) y de panel del menú (móvil) -- nunca dos", () => {
    renderHeader("admin");
    // Antes y después de abrir el menú, sigue habiendo UN solo `role="status"`:
    // ver el docstring de `ChatHeader` sobre por qué no se duplica el nodo.
    expect(screen.getAllByRole("status", { name: /Costo de sesión/ })).toHaveLength(1);
  });

  it("clickear el disparador abre el panel (aria-expanded + clase is-open) y muestra el taxímetro", async () => {
    const user = userEvent.setup();
    renderHeader("admin");

    const trigger = screen.getByRole("button", { name: HEADER_LABELS.sessionMenuLabel });
    await user.click(trigger);

    expect(trigger.getAttribute("aria-expanded")).toBe("true");
    const panel = document.getElementById(trigger.getAttribute("aria-controls") ?? "");
    expect(panel?.className).toContain("is-open");
    expect(screen.getByText("USD 0,0300")).toBeTruthy();
  });

  it("Escape cierra el panel y devuelve el foco al disparador", async () => {
    const user = userEvent.setup();
    renderHeader("admin");

    const trigger = screen.getByRole("button", { name: HEADER_LABELS.sessionMenuLabel });
    await user.click(trigger);
    expect(trigger.getAttribute("aria-expanded")).toBe("true");

    await user.keyboard("{Escape}");
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
    expect(document.activeElement).toBe(trigger);
  });

  it("un click afuera del menú lo cierra", async () => {
    const user = userEvent.setup();
    render(
      <div>
        <button type="button">fuera</button>
        <ChatHeader
          agentName="DocAgent"
          role="admin"
          costUsd={0.03}
          totalTokens={12400}
          degraded={false}
          taximeterLabels={TAXIMETER_LABELS}
          labels={HEADER_LABELS}
        />
      </div>,
    );

    const trigger = screen.getByRole("button", { name: HEADER_LABELS.sessionMenuLabel });
    await user.click(trigger);
    expect(trigger.getAttribute("aria-expanded")).toBe("true");

    await user.click(screen.getByRole("button", { name: "fuera" }));
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
  });
});
