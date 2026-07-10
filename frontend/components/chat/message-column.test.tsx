import { describe, expect, it, vi, afterEach } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useTurnStream } from "@/lib/chat/use-turn-stream";
import { createControlledReader, mockSseResponse, sseFrame } from "@/lib/chat/test-support/sse-mock";
import type { TurnTelemetry, VisibleToolCallView } from "@/lib/chat/types";
import { MessageColumn, type StreamingTurnStatus } from "./message-column";

const LABELS = {
  emptyGreeting: "¿En qué te puedo ayudar hoy?",
  stoppedCaption: "Detenida por vos",
  streamingDoneAnnouncement: "Respuesta completa",
  cursorAriaLabel: "El agente está escribiendo",
  activity: { consulting: "Consultando…" },
  newMessages: "↓ Nuevos mensajes",
  feedback: {
    like: "Me gusta",
    dislike: "No me gusta",
    prompt: "¿Querés agregar un comentario? (opcional)",
    commentLabel: "Comentario",
    send: "Enviar",
    skip: "Omitir",
    error: "No pudimos registrar tu voto. Probá de nuevo.",
  },
  telemetry: {
    cacheHit: "HIT",
    cacheMiss: "MISS",
    cacheWrite: "WRITE",
    cacheHitAriaLabelPrefix: "cache hit,",
    cacheHitAriaLabelSuffix: "tokens cacheados",
    cacheMissAriaLabelPrefix: "cache miss,",
    cacheMissAriaLabelSuffix: "tokens sin cache",
    cacheWriteAriaLabelPrefix: "prefijo escrito al cache,",
    cacheWriteAriaLabelSuffix: "tokens",
    cacheHitTooltip: "prefijo servido desde cache: ahorro ~90% en esos tokens",
    cacheMissTooltip: "tokens procesados sin cache (primera vez)",
    cacheWriteTooltip: "prefijo escrito al cache para los próximos turnos",
    viewTrace: "ver traza",
    viewTraceAriaLabel: "Ver traza de este turno en Langfuse",
  },
  alternateModel: {
    label: "modelo alterno",
    funcionalExplanation:
      "Esta respuesta la generó un modelo alternativo porque el habitual no estaba disponible. La calidad puede variar.",
    profilePrefix: "Perfil:",
    reasonPrefix: "Motivo:",
  },
  toolCall: {
    parametersLabel: "Parámetros",
    latencyLabel: "Latencia:",
  },
};

// Shape del evento `done` para el rol Funcional (tarea 4.1 del backend,
// `telemetry.py::layer_turn_metadata`): sin la clave `telemetry`.
const DONE_METADATA = {
  turn_id: "turn-1",
  user_message_id: "msg-1",
  assistant_message_id: "asst-1",
  reprocessed_count: 0,
  stopped: false,
  is_alternate_model: false,
  compacted: false,
  escalation: null,
};

/** Conecta `useTurnStream` real a `MessageColumn` -- el "doble del stream
 * SSE" pedido por la verificación de la tarea 3.1 alimenta al hook real, y
 * este componente prueba que la UI resultante (tabla, código, cursor)
 * refleja ese estado en cada paso, tal como lo haría `chat-content.tsx`. */
function StreamingHarness() {
  const turnStream = useTurnStream({ reconnectDelayMs: 0 });

  return (
    <div>
      <button type="button" onClick={() => void turnStream.sendTurn("session-1", "mostrame un ejemplo")}>
        enviar
      </button>
      <MessageColumn
        messages={[]}
        streaming={
          turnStream.status === "streaming" ||
          turnStream.status === "done" ||
          turnStream.status === "error"
            ? { text: turnStream.text, status: turnStream.status as StreamingTurnStatus }
            : null
        }
        labels={LABELS}
      />
    </div>
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("MessageColumn — streaming con tabla y bloque de código (tarea 3.1)", () => {
  it("renderiza la tabla y el código con highlighting ANTES del done, con cursor visible, y el cursor desaparece tras done", async () => {
    const reader = createControlledReader();
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        mockSseResponse(reader.reader, {
          headers: { "X-Turn-Id": "turn-1", "X-User-Message-Id": "msg-1" },
        }),
      ),
    );

    render(<StreamingHarness />);

    await act(async () => {
      screen.getByRole("button", { name: "enviar" }).click();
    });

    // Antes de que llegue cualquier fragmento de texto: línea de actividad
    // plegada (tarea 3.3), sin cursor todavía (el cursor es del TEXTO en
    // streaming, que todavía no existe).
    expect(await screen.findByText("Consultando…")).toBeTruthy();
    expect(screen.queryByTestId("stream-cursor")).toBeNull();

    // Llega primero la tabla markdown...
    reader.push(
      sseFrame(1, "fragment", {
        text: "| Columna A | Columna B |\n| --- | --- |\n| uno | dos |\n\n",
      }),
    );
    await waitFor(() => expect(document.querySelector("table")).not.toBeNull());

    // ANTES del done: la tabla ya se renderizó como <table> real.
    const table = document.querySelector("table");
    expect(table).not.toBeNull();
    expect(table?.querySelectorAll("td")).toHaveLength(2);

    // ...y después el bloque de código con lenguaje declarado.
    reader.push(sseFrame(2, "fragment", { text: "```python\ndef saludo():\n" }));
    reader.push(sseFrame(3, "fragment", { text: '    return "hola"\n```\n' }));

    // ANTES del done: el código ya se renderiza con highlighting real
    // (clases `hljs`/`hljs-keyword`, no solo texto plano).
    await waitFor(() =>
      expect(document.querySelector("code.language-python.hljs")).not.toBeNull(),
    );
    expect(document.querySelector(".hljs-keyword")).not.toBeNull();

    // El cursor sigue presente: el turno todavía está en curso.
    expect(screen.getByTestId("stream-cursor")).toBeTruthy();

    // Cierra el turno.
    reader.push(sseFrame(4, "done", DONE_METADATA));
    reader.close();

    // Tras el done, el cursor desaparece.
    await waitFor(() => expect(screen.queryByTestId("stream-cursor")).toBeNull());

    // El contenido (tabla + código) se mantiene renderizado correctamente
    // después del cierre del turno, no solo antes.
    expect(document.querySelector("table")).not.toBeNull();
    expect(document.querySelector("code.language-python.hljs")).not.toBeNull();
  });
});

/** Estampa `scrollTop`/`scrollHeight`/`clientHeight` mockeables sobre un
 * elemento real (jsdom no implementa scroll real -- ver `use-auto-scroll.ts`).
 * `scrollTop` queda como propiedad mutable de verdad para poder leer luego
 * qué le asignó `scrollToBottom()`. */
function mockScrollMetrics(
  el: HTMLElement,
  { scrollHeight, clientHeight, scrollTop }: { scrollHeight: number; clientHeight: number; scrollTop: number },
) {
  Object.defineProperty(el, "scrollHeight", { value: scrollHeight, configurable: true });
  Object.defineProperty(el, "clientHeight", { value: clientHeight, configurable: true });
  let currentScrollTop = scrollTop;
  Object.defineProperty(el, "scrollTop", {
    configurable: true,
    get: () => currentScrollTop,
    set: (value: number) => {
      currentScrollTop = value;
    },
  });
}

describe("MessageColumn — auto-scroll condicionado y botón «Nuevos mensajes» (tarea 3.3)", () => {
  it("NO fuerza el scroll si el usuario scrolleó hacia arriba, y muestra el botón flotante", async () => {
    const reader = createControlledReader();
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        mockSseResponse(reader.reader, {
          headers: { "X-Turn-Id": "turn-1", "X-User-Message-Id": "msg-1" },
        }),
      ),
    );

    render(<StreamingHarness />);
    const container = screen.getByTestId("msg-scroll-container");

    // El usuario está al final antes de que arranque el turno.
    mockScrollMetrics(container, { scrollHeight: 500, clientHeight: 200, scrollTop: 300 });

    await act(async () => {
      screen.getByRole("button", { name: "enviar" }).click();
    });
    await screen.findByText("Consultando…");

    // El usuario scrollea hacia arriba (se aleja del fondo) ANTES de que
    // llegue contenido nuevo -- por sí solo esto no debe mostrar el botón.
    mockScrollMetrics(container, { scrollHeight: 500, clientHeight: 200, scrollTop: 0 });
    fireEvent.scroll(container);
    expect(screen.queryByText("↓ Nuevos mensajes")).toBeNull();

    // Llega un fragmento nuevo mientras el usuario sigue arriba: NO se
    // fuerza el scroll (scrollTop no vuelve a moverse solo) y aparece el
    // botón flotante en su lugar.
    reader.push(sseFrame(1, "fragment", { text: "Une respuesta larga que sigue." }));
    await waitFor(() => expect(screen.queryByText("↓ Nuevos mensajes")).not.toBeNull());
    expect(container.scrollTop).toBe(0);

    // Click en el botón: baja al fondo y el botón desaparece.
    fireEvent.click(screen.getByText("↓ Nuevos mensajes"));
    expect(container.scrollTop).toBe(container.scrollHeight);
    expect(screen.queryByText("↓ Nuevos mensajes")).toBeNull();

    reader.close();
  });

  it("SÍ fuerza el scroll al fondo con cada fragmento cuando el usuario ya está al final", async () => {
    const reader = createControlledReader();
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        mockSseResponse(reader.reader, {
          headers: { "X-Turn-Id": "turn-1", "X-User-Message-Id": "msg-1" },
        }),
      ),
    );

    render(<StreamingHarness />);
    const container = screen.getByTestId("msg-scroll-container");
    mockScrollMetrics(container, { scrollHeight: 400, clientHeight: 200, scrollTop: 200 });

    await act(async () => {
      screen.getByRole("button", { name: "enviar" }).click();
    });
    await screen.findByText("Consultando…");

    // Crece el contenido: el mock simula que `scrollHeight` crece con el
    // fragmento nuevo, como pasaría en un navegador real.
    Object.defineProperty(container, "scrollHeight", { value: 900, configurable: true });
    reader.push(sseFrame(1, "fragment", { text: "Respuesta nueva." }));

    await waitFor(() => expect(container.scrollTop).toBe(900));
    expect(screen.queryByText("↓ Nuevos mensajes")).toBeNull();

    reader.close();
  });
});

describe("MessageColumn — estados base", () => {
  it("muestra el saludo vacío cuando no hay mensajes ni turno en curso", () => {
    render(<MessageColumn messages={[]} labels={LABELS} />);
    expect(screen.getByText(LABELS.emptyGreeting)).toBeTruthy();
  });

  it("renderiza mensajes de usuario y agente ya persistidos sin cursor", () => {
    render(
      <MessageColumn
        messages={[
          { id: "m1", role: "user", content: "Hola" },
          { id: "m2", role: "assistant", content: "**Hola!** ¿En qué te ayudo?" },
        ]}
        labels={LABELS}
      />,
    );
    expect(screen.getByText("Hola")).toBeTruthy();
    expect(screen.getByText(/En qué te ayudo/)).toBeTruthy();
    expect(screen.queryByTestId("stream-cursor")).toBeNull();
  });
});

/** Telemetría de Técnico/Admin con fallback -- misma forma que arma
 * `layer_turn_metadata` (`telemetry.py`) para un turno servido por un
 * perfil de fallback. */
const ALTERNATE_MODEL_TELEMETRY: TurnTelemetry = {
  cost_usd: 0.0042,
  model_profile_id: "kimi-k2.6",
  primary_model_profile_id: "deepseek-v4-flash",
  fallback_reason: "proveedor caído 14:31",
  latency_ms: 3200,
  cache_hit_tokens: null,
  cache_miss_tokens: null,
  cache_write_tokens: null,
};

describe('MessageColumn — etiqueta "modelo alterno" por rol sobre un turno real (tarea 5.1)', () => {
  it("Funcional (mensaje sin telemetry): tag con texto simple, sin el nombre del perfil en el DOM", () => {
    render(
      <MessageColumn
        messages={[{ id: "a1", role: "assistant", content: "Respuesta", isAlternateModel: true }]}
        labels={LABELS}
      />,
    );
    const tag = screen.getByText("modelo alterno");
    expect(tag.getAttribute("aria-label")).toBe(LABELS.alternateModel.funcionalExplanation);
    expect(document.body.innerHTML).not.toContain("kimi-k2.6");
  });

  it("Técnico/Admin (mensaje con telemetry): el tag expone el nombre del perfil de forma accesible", () => {
    render(
      <MessageColumn
        messages={[
          {
            id: "a1",
            role: "assistant",
            content: "Respuesta",
            isAlternateModel: true,
            telemetry: ALTERNATE_MODEL_TELEMETRY,
          },
        ]}
        labels={LABELS}
      />,
    );
    const tag = screen.getByText("modelo alterno");
    expect(tag.getAttribute("aria-label")).toContain("kimi-k2.6");
  });

  it("turno normal (is_alternate_model false): no muestra ningún tag", () => {
    render(
      <MessageColumn
        messages={[{ id: "a1", role: "assistant", content: "Respuesta", isAlternateModel: false }]}
        labels={LABELS}
      />,
    );
    expect(screen.queryByText("modelo alterno")).toBeNull();
  });
});

/** Fixture conforme al contrato `tool-call-visibility` de c09-mcp-tools
 * (`VisibleToolCallView`, espejo de `render_for_role` en
 * `resultarai/core/audit/visibility.py`). */
const TOOL_CALL: VisibleToolCallView = {
  tool_name: "buscar_documentacion",
  status: "executed",
  status_label: "ejecutada",
  simple_description:
    "Se consultó «buscar_documentacion». Resultado: MATA010 — Parámetros de localización.",
  parameters: { query: "MV_PAISLOC" },
  result_preview: "MATA010 — Parámetros de localización.",
  duration_ms: 820,
};

describe("MessageColumn — tool calls colapsadas/expandibles por rol sobre un turno real (tarea 5.2)", () => {
  it("colapsada por defecto para cualquier rol: no muestra la descripción ni parámetros hasta expandir", () => {
    render(
      <MessageColumn
        messages={[{ id: "a1", role: "assistant", content: "Respuesta", toolCalls: [TOOL_CALL] }]}
        labels={LABELS}
        role="tecnico"
      />,
    );
    expect(screen.getByRole("button", { name: /buscar_documentacion/ })).toBeTruthy();
    expect(screen.queryByText(TOOL_CALL.simple_description)).toBeNull();
  });

  it("Funcional: al expandir ve lenguaje simple y NO ve parámetros ni latencia en el DOM", async () => {
    const user = userEvent.setup();
    render(
      <MessageColumn
        messages={[{ id: "a1", role: "assistant", content: "Respuesta", toolCalls: [TOOL_CALL] }]}
        labels={LABELS}
        role="funcional"
      />,
    );
    await user.click(screen.getByRole("button", { name: /buscar_documentacion/ }));
    expect(screen.getByText(TOOL_CALL.simple_description)).toBeTruthy();
    expect(screen.queryByText(LABELS.toolCall.parametersLabel)).toBeNull();
    expect(document.body.innerHTML).not.toContain("MV_PAISLOC");
    expect(screen.queryByText(/0,8 s/)).toBeNull();
  });

  it("Técnico: al expandir la MISMA tool call ve además parámetros completos y latencia", async () => {
    const user = userEvent.setup();
    render(
      <MessageColumn
        messages={[{ id: "a1", role: "assistant", content: "Respuesta", toolCalls: [TOOL_CALL] }]}
        labels={LABELS}
        role="tecnico"
      />,
    );
    await user.click(screen.getByRole("button", { name: /buscar_documentacion/ }));
    expect(screen.getByText(LABELS.toolCall.parametersLabel)).toBeTruthy();
    expect(screen.getByText(/MV_PAISLOC/)).toBeTruthy();
    expect(screen.getByText(/0,8 s/)).toBeTruthy();
  });
});
