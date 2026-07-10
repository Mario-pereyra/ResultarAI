import { afterEach, describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { createControlledReader, mockSseResponse, sseFrame } from "./test-support/sse-mock";
import { useTurnStream } from "./use-turn-stream";

// Shape del evento `done` para el rol Funcional (tarea 4.1 del backend,
// `telemetry.py::layer_turn_metadata`): sin la clave `telemetry` -- ausente,
// no `null`/`{}`. El hook no distingue rol (solo transporta lo que llega),
// así que alcanza con este shape mínimo para probar su comportamiento.
const DONE_METADATA_BASE = {
  turn_id: "turn-1",
  user_message_id: "msg-1",
  assistant_message_id: "asst-1",
  reprocessed_count: 0,
  stopped: false,
  is_alternate_model: false,
  compacted: false,
  escalation: null,
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useTurnStream — envío de turno", () => {
  it("acumula fragmentos y cierra con los metadatos del evento done", async () => {
    const reader = createControlledReader();
    const fetchMock = vi.fn(async () =>
      mockSseResponse(reader.reader, {
        headers: { "X-Turn-Id": "turn-1", "X-User-Message-Id": "msg-1" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useTurnStream({ reconnectDelayMs: 0 }));

    act(() => {
      void result.current.sendTurn("session-1", "hola");
    });

    await waitFor(() => expect(result.current.status).toBe("streaming"));
    // `status` pasa a "streaming" de entrada (apenas se llama a `sendTurn`,
    // antes de que resuelva el `fetch`); `turnId`/`userMessageId` recién
    // llegan un instante después, leídos de los headers de la respuesta
    // (`X-Turn-Id`/`X-User-Message-Id`) -- se esperan aparte.
    await waitFor(() => expect(result.current.turnId).toBe("turn-1"));
    expect(result.current.userMessageId).toBe("msg-1");

    reader.push(sseFrame(1, "fragment", { text: "Hola " }));
    await waitFor(() => expect(result.current.text).toBe("Hola "));

    reader.push(sseFrame(2, "fragment", { text: "mundo" }));
    await waitFor(() => expect(result.current.text).toBe("Hola mundo"));

    reader.push(sseFrame(3, "done", { ...DONE_METADATA_BASE }));
    reader.close();

    await waitFor(() => expect(result.current.status).toBe("done"));
    expect(result.current.doneMetadata?.assistant_message_id).toBe("asst-1");
    expect(fetchMock).toHaveBeenCalledTimes(1);

    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ text: "hola" });
  });

  it("expone el evento de escalación sin alterar el texto entregado", async () => {
    const reader = createControlledReader();
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => mockSseResponse(reader.reader, { headers: { "X-Turn-Id": "turn-2" } })),
    );

    const { result } = renderHook(() => useTurnStream({ reconnectDelayMs: 0 }));
    act(() => {
      void result.current.sendTurn("session-1", "necesito Pro");
    });
    await waitFor(() => expect(result.current.status).toBe("streaming"));

    reader.push(sseFrame(1, "fragment", { text: "Esta consulta es compleja." }));
    await waitFor(() => expect(result.current.text).toBe("Esta consulta es compleja."));

    reader.push(
      sseFrame(2, "escalation", { reason: "cruza varias localizaciones", target_profile: "deepseek-v4-pro" }),
    );
    await waitFor(() => expect(result.current.escalation).not.toBeNull());
    expect(result.current.escalation?.target_profile).toBe("deepseek-v4-pro");
    // El marcador crudo nunca viaja en el texto (tarea 1.4 del backend).
    expect(result.current.text).not.toContain("NEEDS_PRO");
  });
});

describe("useTurnStream — reconexión tras un corte de conexión", () => {
  it("reconecta con Last-Event-ID y el texto final no duplica fragmentos", async () => {
    const firstReader = createControlledReader();
    const secondReader = createControlledReader();
    const fetchMock = vi.fn();
    fetchMock.mockImplementationOnce(async () =>
      mockSseResponse(firstReader.reader, {
        headers: { "X-Turn-Id": "turn-1", "X-User-Message-Id": "msg-1" },
      }),
    );
    fetchMock.mockImplementationOnce(async () => mockSseResponse(secondReader.reader));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useTurnStream({ reconnectDelayMs: 0 }));

    act(() => {
      void result.current.sendTurn("session-1", "hola");
    });
    await waitFor(() => expect(result.current.status).toBe("streaming"));

    firstReader.push(sseFrame(1, "fragment", { text: "Hola " }));
    await waitFor(() => expect(result.current.text).toBe("Hola "));

    firstReader.push(sseFrame(2, "fragment", { text: "mundo" }));
    await waitFor(() => expect(result.current.text).toBe("Hola mundo"));

    // Corte de conexión a mitad de turno: el reader del POST se cierra sin
    // que nunca haya llegado el evento `done`.
    firstReader.close();

    // El hook reconecta solo, sin intervención del consumidor, contra
    // `GET /api/turns/{turnId}/stream` con el último id visto.
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    const [secondUrl, secondInit] = fetchMock.mock.calls[1] as [string, RequestInit];
    expect(secondUrl).toBe("/api/turns/turn-1/stream?last_event_id=2");
    expect(secondInit.method).toBe("GET");

    // El segundo stream repite defensivamente el id=2 ya visto (el
    // contrato del backend no debería duplicar, pero el cliente no debe
    // confiar ciegamente: ver `seenFragmentIds` en use-turn-stream.ts)
    // antes de aportar contenido nuevo y cerrar.
    secondReader.push(sseFrame(2, "fragment", { text: "mundo" }));
    secondReader.push(sseFrame(3, "fragment", { text: "!" }));
    secondReader.push(sseFrame(4, "done", { ...DONE_METADATA_BASE }));
    secondReader.close();

    await waitFor(() => expect(result.current.status).toBe("done"));
    expect(result.current.text).toBe("Hola mundo!");
  });

  it("se rinde con status error tras agotar los reintentos de reconexión", async () => {
    const firstReader = createControlledReader();
    // Cortado ya de entrada: cualquier reconexión (2ª/3ª llamada a fetch)
    // "lee" un stream que ya viene cerrado sin `done`, así que cada
    // reintento agota de inmediato -- exactamente lo que se necesita para
    // ejercitar el tope de reintentos sin que el test cuelgue esperando.
    const closedReader = { read: () => Promise.resolve({ done: true as const }) };
    let callCount = 0;
    const fetchMock = vi.fn(async () => {
      callCount += 1;
      if (callCount === 1) {
        return mockSseResponse(firstReader.reader, { headers: { "X-Turn-Id": "turn-3" } });
      }
      return mockSseResponse(closedReader);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() =>
      useTurnStream({ reconnectDelayMs: 0, maxReconnectAttempts: 2 }),
    );

    act(() => {
      void result.current.sendTurn("session-1", "hola");
    });
    await waitFor(() => expect(result.current.status).toBe("streaming"));

    firstReader.push(sseFrame(1, "fragment", { text: "..." }));
    await waitFor(() => expect(result.current.text).toBe("..."));

    // Corte de conexión a mitad de turno: el primer stream se cierra sin `done`.
    firstReader.close();

    await waitFor(() => expect(result.current.status).toBe("error"));
    expect(result.current.error?.message).toBeTruthy();
    // 1 intento inicial + 2 reintentos = 3 llamadas a fetch.
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });
});
