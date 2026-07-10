import { describe, expect, it, vi, afterEach } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import { useTurnStream } from "@/lib/chat/use-turn-stream";
import { createControlledReader, mockSseResponse, sseFrame } from "@/lib/chat/test-support/sse-mock";
import { MessageColumn, type StreamingTurnStatus } from "./message-column";

const LABELS = {
  emptyGreeting: "¿En qué te puedo ayudar hoy?",
  stoppedCaption: "Detenida por vos",
  streamingDoneAnnouncement: "Respuesta completa",
  cursorAriaLabel: "El agente está escribiendo",
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

    // Cursor visible apenas arranca el streaming.
    expect(await screen.findByTestId("stream-cursor")).toBeTruthy();

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
