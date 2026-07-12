import userEvent from "@testing-library/user-event";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AttachmentItem } from "@/lib/chat/attachment-adapter";
import { AttachmentPreviewPanel, type AttachmentPreviewPanelLabels } from "./attachment-preview-panel";

/**
 * Tests del panel "Ver lo que verá el agente" (d14-attachments, tarea 8.3).
 * Fuente normativa: `design/ANEXO-ATTACHMENTS.md` §3.4/§10 + spec
 * `openspec/changes/d14-attachments/specs/attachments-ui/spec.md`
 * (Requirements "Vista previa 'Ver lo que verá el agente'" y "Transparencia
 * de espacio por capa de rol"). Cubre puntualmente los DOS escenarios de la
 * verificación de la tarea:
 *
 * - "Vista previa de un adjunto truncado": la extracción exacta con sus
 *   marcadores, el conteo de tokens/%, y el pie permanente.
 * - "Mismo adjunto, métricas por rol": Funcional ve "% del espacio del
 *   mensaje", Técnico/Admin ve tokens -- MISMO texto literal que ya usa el
 *   chip (`attachment-chip.test.tsx`).
 *
 * `composer.test.tsx`/`chat-content-attachments.test.tsx` cubren la
 * integración de apertura desde el chip real; acá se aísla el panel con un
 * doble de `fetch` propio (mismo criterio que `attachment-adapter.test.ts`).
 */

const LABELS: AttachmentPreviewPanelLabels = {
  title: "Esto es exactamente lo que recibirá el agente",
  closeLabel: "Cerrar vista previa",
  footer: "Contenido extraído automáticamente — puede diferir del documento original.",
  loading: "Cargando vista previa…",
  error: "No pudimos cargar la vista previa de este adjunto. Probá de nuevo.",
  metricTechAdmin: "Listo · {tokens} tokens",
  metricFunctional: "Listo · usa {percent}% del espacio del mensaje",
  truncatedNotice:
    "Por el límite de espacio, el agente verá el {percent}% del archivo (se priorizaron las secciones relacionadas con tu consulta). Las partes omitidas están marcadas — podés pedirlas explícitamente en el chat.",
};

function makeItem(overrides: Partial<AttachmentItem> = {}): AttachmentItem {
  return {
    id: "attachment-local-1",
    attachmentId: "att-1",
    file: new File(["contenido"], "balance_marzo.xlsx"),
    originalName: "balance_marzo.xlsx",
    status: "ready",
    sendable: true,
    requiresTestDataConfirmation: false,
    tokenCount: 8200,
    includedPercent: 62,
    truncated: true,
    message: null,
    confirming: false,
    ...overrides,
  };
}

const TRUNCATED_TEXT = [
  'Inventario de hojas (3):',
  '1. "Resumen"   — 24 filas × 5 col (incluida completa)',
  '2. "Detalle"   — 1.480 filas × 8 col (incluidas 150 primeras + 20 últimas)',
  '… (1.310 filas omitidas por límite de espacio — pedilas explícitamente si las necesitás) …',
].join("\n");

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function stubPreviewFetch(body: unknown, status = 200) {
  const fetchMock = vi.fn(async () => jsonResponse(status, body));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('AttachmentPreviewPanel — escenario "Vista previa de un adjunto truncado" (ANEXO §3.4)', () => {
  it("muestra la extracción exacta con sus marcadores, tokens/% y el pie permanente", async () => {
    stubPreviewFetch({
      id: "att-1",
      inserted: false,
      text: TRUNCATED_TEXT,
      token_count: 8200,
      included_percent: 62,
      truncated: true,
    });

    render(
      <AttachmentPreviewPanel item={makeItem()} onClose={vi.fn()} role="tecnico" labels={LABELS} />,
    );

    expect(screen.getByRole("dialog")).toBeTruthy();
    expect(screen.getByText(LABELS.loading)).toBeTruthy();

    // `Modal` portalea a `document.body` (fuera del `container` que devuelve
    // `render()`) -- se busca en `document` directamente, no en `container`.
    await waitFor(() => {
      expect(document.querySelector(".attachment-preview__body")).toBeTruthy();
    });
    // Extracción EXACTA, byte-idéntica -- incluidos sus marcadores de
    // secciones omitidas (comparación directa de `textContent`, sin la
    // normalización de espacios que aplica `getByText`).
    expect(document.querySelector(".attachment-preview__body")?.textContent).toBe(TRUNCATED_TEXT);

    // Marcador de sección omitida, textual, dentro de la extracción exacta.
    expect(screen.getByText(/omitidas por límite de espacio/)).toBeTruthy();
    // Métrica (Técnico/Admin: tokens) y aviso de truncado con el % incluido.
    expect(screen.getByText("balance_marzo.xlsx · Listo · 8.200 tokens")).toBeTruthy();
    expect(
      screen.getByText(
        "Por el límite de espacio, el agente verá el 62% del archivo (se priorizaron las secciones relacionadas con tu consulta). Las partes omitidas están marcadas — podés pedirlas explícitamente en el chat.",
      ),
    ).toBeTruthy();
    // Pie PERMANENTE -- siempre visible, no condicional al truncado.
    expect(
      screen.getByText("Contenido extraído automáticamente — puede diferir del documento original."),
    ).toBeTruthy();
  });

  it("adjunto NO truncado: no muestra el aviso de truncado", async () => {
    stubPreviewFetch({
      id: "att-1",
      inserted: false,
      text: "contenido completo, sin marcadores",
      token_count: 500,
      included_percent: 100,
      truncated: false,
    });

    render(
      <AttachmentPreviewPanel
        item={makeItem({ truncated: false, includedPercent: 100, tokenCount: 500 })}
        onClose={vi.fn()}
        role="admin"
        labels={LABELS}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("contenido completo, sin marcadores")).toBeTruthy();
    });
    expect(screen.queryByText(/Por el límite de espacio/)).toBeNull();
  });
});

describe('AttachmentPreviewPanel — escenario "Mismo adjunto, métricas por rol" (ANEXO §10)', () => {
  it("Funcional ve «Listo · usa 34% del espacio del mensaje»", async () => {
    stubPreviewFetch({
      id: "att-1",
      inserted: false,
      text: "texto",
      token_count: 8200,
      included_percent: 34,
      truncated: false,
    });

    render(
      <AttachmentPreviewPanel
        item={makeItem({ truncated: false, includedPercent: 34 })}
        onClose={vi.fn()}
        role="funcional"
        labels={LABELS}
      />,
    );

    await waitFor(() => {
      expect(
        screen.getByText("balance_marzo.xlsx · Listo · usa 34% del espacio del mensaje"),
      ).toBeTruthy();
    });
  });

  it("Técnico ve «Listo · 8.200 tokens»", async () => {
    stubPreviewFetch({
      id: "att-1",
      inserted: false,
      text: "texto",
      token_count: 8200,
      included_percent: 34,
      truncated: false,
    });

    render(
      <AttachmentPreviewPanel
        item={makeItem({ truncated: false, includedPercent: 34 })}
        onClose={vi.fn()}
        role="tecnico"
        labels={LABELS}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("balance_marzo.xlsx · Listo · 8.200 tokens")).toBeTruthy();
    });
  });
});

describe("AttachmentPreviewPanel — apertura/cierre y estados no felices", () => {
  it("item null: no renderiza el diálogo", () => {
    render(<AttachmentPreviewPanel item={null} onClose={vi.fn()} role="tecnico" labels={LABELS} />);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("Escape cierra el panel (onClose)", async () => {
    const user = userEvent.setup();
    stubPreviewFetch({
      id: "att-1",
      inserted: false,
      text: "texto",
      token_count: 100,
      included_percent: 100,
      truncated: false,
    });
    const onClose = vi.fn();

    render(<AttachmentPreviewPanel item={makeItem()} onClose={onClose} role="admin" labels={LABELS} />);
    await waitFor(() => expect(screen.getByRole("dialog")).toBeTruthy());

    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('botón de cierre (aria-label "Cerrar vista previa") llama a onClose', async () => {
    const user = userEvent.setup();
    stubPreviewFetch({
      id: "att-1",
      inserted: false,
      text: "texto",
      token_count: 100,
      included_percent: 100,
      truncated: false,
    });
    const onClose = vi.fn();

    render(<AttachmentPreviewPanel item={makeItem()} onClose={onClose} role="admin" labels={LABELS} />);
    await waitFor(() => expect(screen.getByRole("dialog")).toBeTruthy());

    await user.click(screen.getByRole("button", { name: "Cerrar vista previa" }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("el fetch falla (409 extraction_not_ready): muestra el texto de error, nunca un panel en blanco", async () => {
    stubPreviewFetch({ detail: { error_code: "extraction_not_ready", params: {} } }, 409);

    render(<AttachmentPreviewPanel item={makeItem()} onClose={vi.fn()} role="admin" labels={LABELS} />);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeTruthy();
    });
    expect(screen.getByText(LABELS.error)).toBeTruthy();
  });

  it("adjunto sin attachmentId (defensivo): muestra error sin intentar el fetch", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(
      <AttachmentPreviewPanel
        item={makeItem({ attachmentId: null })}
        onClose={vi.fn()}
        role="admin"
        labels={LABELS}
      />,
    );

    expect(screen.getByRole("alert")).toBeTruthy();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
