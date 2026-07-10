import { describe, expect, it, vi, afterEach } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useTurnStream } from "@/lib/chat/use-turn-stream";
import { createControlledReader, mockSseResponse, sseFrame } from "@/lib/chat/test-support/sse-mock";
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
