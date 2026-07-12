"use client";

import { useCallback, useRef, useState } from "react";
import { csrfHeaders } from "@/lib/csrf";
import { readSseFrames, type SseFrame } from "./sse";
import type { TurnDoneMetadata, TurnEscalation } from "./types";

/**
 * Cliente SSE del turno de chat (d13-chat-conversacion, tarea 3.1 del
 * frontend). Implementa el contrato completo documentado en
 * `resultarai/app/api/chat_stream.py`: envío de turno vía `fetch()` +
 * `ReadableStream` (POST no compatible con `EventSource`), reconexión por
 * `Last-Event-ID` ante un corte de conexión, y cancelación.
 *
 * Diseño pensado para que las tareas siguientes se enchufen sin rehacer
 * este hook:
 * - 3.4 (composer, botón enviar↔detener): `status`/`cancelTurn` ya cubren
 *   el ciclo completo.
 * - 5.3 (tarjeta de escalación): `escalation` se expone tal cual llega del
 *   evento SSE, sin transformar -- la UI decide cuándo mostrarla.
 * - 6.x (tarjetas de error accionables): `error.status`/`error.message` dan
 *   la base; el mapeo a códigos como `GATEWAY_OFFLINE`/`QUOTA` queda para
 *   esas tareas (este hook no conoce esos códigos).
 * - 2.5 (reanudar sesión con un turno en curso en otra pestaña):
 *   `attachToTurn(turnId, lastEventId)` re-conecta sin reenviar el mensaje.
 */

export type TurnStreamStatus = "idle" | "streaming" | "done" | "error";

export interface TurnStreamError {
  /** `null` cuando el error no vino de una respuesta HTTP con código (p.
   * ej. la reconexión se agotó tras varios intentos, o el turno en curso
   * quedó en un 409 sin `turn_id` identificable). */
  status: number | null;
  message: string;
}

export interface SendTurnOptions {
  /** Edita el mensaje con este id en vez de enviar un turno nuevo (decisión
   * 4 de design.md: mismo endpoint, distinguido por este campo). */
  editsMessageId?: string;
  /** `attachment_id` de adjuntos `sendable` del borrador (d14-attachments,
   * tarea 8.1/6.3) -- espejo de `SendMessageRequest.attachment_ids`
   * (`resultarai/app/api/chat.py`): ADITIVO y opcional, `undefined`/vacío deja
   * el comportamiento IDÉNTICO al de antes de d14. El adapter del composer
   * (`lib/chat/attachment-adapter.ts::attachmentIdsForSend`) es quien resuelve
   * esta lista -- este hook solo la transporta tal cual en el body del POST. */
  attachmentIds?: string[];
}

export interface UseTurnStreamOptions {
  /** Reintentos de reconexión ante un corte de conexión a mitad de turno
   * (tarea 1.6 del backend). Configurable para que los tests no dependan de
   * temporizadores reales. Default 3. */
  maxReconnectAttempts?: number;
  /** Espera entre reintentos de reconexión, en ms (`0` recomendado en
   * tests). Default 300. El backoff visible con countdown (5→15→60 s) es
   * la tarjeta `GATEWAY_OFFLINE` de la tarea 6.1 -- este valor es solo un
   * respiro entre reintentos internos, no UI. */
  reconnectDelayMs?: number;
}

export interface UseTurnStreamResult {
  status: TurnStreamStatus;
  /** Texto acumulado de los fragmentos del turno en curso (o del último). */
  text: string;
  turnId: string | null;
  userMessageId: string | null;
  escalation: TurnEscalation | null;
  doneMetadata: TurnDoneMetadata | null;
  error: TurnStreamError | null;
  /** Envía un turno nuevo (o una edición, con `options.editsMessageId`). */
  sendTurn: (sessionId: string, text: string, options?: SendTurnOptions) => Promise<void>;
  /** Se re-conecta a un turno ya en curso (reanudar sesión, tarea 2.5). */
  attachToTurn: (turnId: string, lastEventId?: number) => Promise<void>;
  /** Cancela el turno en curso (tarea 1.7 del backend). No-op sin turno activo. */
  cancelTurn: () => Promise<void>;
  /** Vuelve a `idle` y limpia el estado del último turno -- se llama
   * después de "plegar" el texto final dentro del historial persistido
   * (ver `chat-content.tsx`), para que la columna de mensajes deje de
   * mostrar el bloque en streaming (ya duplicaría el mensaje ya plegado). */
  reset: () => void;
}

const DEFAULT_MAX_RECONNECT_ATTEMPTS = 3;
const DEFAULT_RECONNECT_DELAY_MS = 300;

function wait(ms: number): Promise<void> {
  if (ms <= 0) return Promise.resolve();
  return new Promise((resolve) => setTimeout(resolve, ms));
}

interface StreamOnceResult {
  /** `true` si se vio el evento `done` (el turno cerró normalmente). */
  completed: boolean;
  /** `true` si ya se fijó `status: "error"` -- no hay que reconectar. */
  fatal: boolean;
  /** 409: ya hay un turno en curso sobre la sesión; re-attachearse a este id
   * en vez de reintentar el envío (ver docstring de `chat_stream.py`). */
  conflictTurnId: string | null;
}

interface ConflictBody {
  turn_id?: string;
  detail?: { turn_id?: string };
}

export function useTurnStream(options: UseTurnStreamOptions = {}): UseTurnStreamResult {
  const maxReconnectAttempts = options.maxReconnectAttempts ?? DEFAULT_MAX_RECONNECT_ATTEMPTS;
  const reconnectDelayMs = options.reconnectDelayMs ?? DEFAULT_RECONNECT_DELAY_MS;

  const [status, setStatus] = useState<TurnStreamStatus>("idle");
  const [text, setText] = useState("");
  const [turnId, setTurnId] = useState<string | null>(null);
  const [userMessageId, setUserMessageId] = useState<string | null>(null);
  const [escalation, setEscalation] = useState<TurnEscalation | null>(null);
  const [doneMetadata, setDoneMetadata] = useState<TurnDoneMetadata | null>(null);
  const [error, setError] = useState<TurnStreamError | null>(null);

  // Estado mutable que no debe disparar renders por sí mismo: se consulta
  // desde el bucle de streaming, que vive fuera del ciclo de render de
  // React (una cadena de `await` disparada por un evento de usuario).
  // `seenFragmentIds` evita duplicar texto ante cualquier solapamiento en
  // el replay de la reconexión (defensa en profundidad: el contrato del
  // backend garantiza `id > Last-Event-ID` sin solapar, pero el cliente no
  // debería confiar ciegamente en eso para la propiedad "sin duplicados").
  const seenFragmentIds = useRef<Set<number>>(new Set());
  const lastEventIdRef = useRef(0);
  const turnIdRef = useRef<string | null>(null);
  const accumulatedTextRef = useRef("");
  // Generación del turno actual: se incrementa en cada `sendTurn`/
  // `attachToTurn`/`reset`. Un bucle de streaming "viejo" (de un turno ya
  // abandonado -- p. ej. el usuario mandó un turno nuevo mientras uno
  // anterior seguía reconectando) se auto-cancela comparando contra este
  // valor en cada punto de retomar tras un `await`.
  const generationRef = useRef(0);

  const resetTransientState = useCallback(() => {
    seenFragmentIds.current = new Set();
    lastEventIdRef.current = 0;
    accumulatedTextRef.current = "";
  }, []);

  const reset = useCallback(() => {
    generationRef.current += 1;
    resetTransientState();
    turnIdRef.current = null;
    setStatus("idle");
    setText("");
    setTurnId(null);
    setUserMessageId(null);
    setEscalation(null);
    setDoneMetadata(null);
    setError(null);
  }, [resetTransientState]);

  const applyFrame = useCallback((frame: SseFrame) => {
    if (frame.id !== null) lastEventIdRef.current = frame.id;

    if (frame.event === "fragment") {
      const id = frame.id;
      if (id !== null && seenFragmentIds.current.has(id)) return; // ya aplicado (replay)
      if (id !== null) seenFragmentIds.current.add(id);
      let parsed: { text: string };
      try {
        parsed = JSON.parse(frame.data) as { text: string };
      } catch {
        return; // frame corrupto/truncado -- se ignora, la reconexión lo repone
      }
      accumulatedTextRef.current += parsed.text;
      setText(accumulatedTextRef.current);
      return;
    }

    if (frame.event === "escalation") {
      try {
        setEscalation(JSON.parse(frame.data) as TurnEscalation);
      } catch {
        // Defensivo: un evento de escalación corrupto no debe tumbar el turno.
      }
      return;
    }

    if (frame.event === "done") {
      try {
        const metadata = JSON.parse(frame.data) as TurnDoneMetadata;
        setDoneMetadata(metadata);
        setUserMessageId(metadata.user_message_id);
      } catch {
        setError({ status: null, message: "No se pudo interpretar el cierre del turno." });
      }
    }
  }, []);

  const streamOnce = useCallback(
    async (url: string, init: RequestInit): Promise<StreamOnceResult> => {
      let response: Response;
      try {
        response = await fetch(url, init);
      } catch {
        return { completed: false, fatal: false, conflictTurnId: null }; // red caída -> reconectar
      }

      if (response.status === 409 && init.method !== "GET") {
        let conflictTurnId: string | null = null;
        try {
          const body = (await response.json()) as ConflictBody;
          conflictTurnId = body.turn_id ?? body.detail?.turn_id ?? null;
        } catch {
          conflictTurnId = null;
        }
        if (conflictTurnId) return { completed: false, fatal: false, conflictTurnId };
        setStatus("error");
        setError({
          status: 409,
          message: "Ya hay un turno en curso en esta sesión y no se pudo identificar.",
        });
        return { completed: false, fatal: true, conflictTurnId: null };
      }

      if (!response.ok || response.body === null) {
        setStatus("error");
        setError({ status: response.status, message: "El servidor no pudo continuar el turno." });
        return { completed: false, fatal: true, conflictTurnId: null };
      }

      const headerTurnId = response.headers.get("X-Turn-Id");
      if (headerTurnId) {
        turnIdRef.current = headerTurnId;
        setTurnId(headerTurnId);
      }
      const headerUserMessageId = response.headers.get("X-User-Message-Id");
      if (headerUserMessageId) setUserMessageId(headerUserMessageId);

      setStatus("streaming");

      const reader = response.body.getReader();
      let completed = false;
      try {
        for await (const frame of readSseFrames(reader)) {
          applyFrame(frame);
          if (frame.event === "done") completed = true;
        }
      } catch {
        // Corte de conexión a mitad de turno -- se resuelve en `runTurn` (reconectar).
      }

      if (completed) setStatus("done");
      return { completed, fatal: false, conflictTurnId: null };
    },
    [applyFrame],
  );

  const runTurn = useCallback(
    async (initialUrl: string, initialInit: RequestInit, generation: number): Promise<void> => {
      let url = initialUrl;
      let init = initialInit;
      let attempt = 0;

      while (generation === generationRef.current) {
        const result = await streamOnce(url, init);
        if (generation !== generationRef.current) return;
        if (result.fatal || result.completed) return;

        if (result.conflictTurnId) {
          url = `/api/turns/${result.conflictTurnId}/stream?last_event_id=${lastEventIdRef.current}`;
          init = { method: "GET" };
          continue;
        }

        attempt += 1;
        if (!turnIdRef.current || attempt > maxReconnectAttempts) {
          setStatus("error");
          setError({
            status: null,
            message: "Se perdió la conexión con el turno y no se pudo reconectar.",
          });
          return;
        }

        await wait(reconnectDelayMs);
        if (generation !== generationRef.current) return;
        url = `/api/turns/${turnIdRef.current}/stream?last_event_id=${lastEventIdRef.current}`;
        init = { method: "GET" };
      }
    },
    [streamOnce, maxReconnectAttempts, reconnectDelayMs],
  );

  const sendTurn = useCallback(
    async (sessionId: string, turnText: string, sendOptions: SendTurnOptions = {}) => {
      generationRef.current += 1;
      const generation = generationRef.current;
      resetTransientState();
      turnIdRef.current = null;
      setText("");
      setTurnId(null);
      setUserMessageId(null);
      setEscalation(null);
      setDoneMetadata(null);
      setError(null);
      setStatus("streaming");

      const body: { text: string; edits_message_id?: string; attachment_ids?: string[] } = {
        text: turnText,
      };
      if (sendOptions.editsMessageId) body.edits_message_id = sendOptions.editsMessageId;
      if (sendOptions.attachmentIds && sendOptions.attachmentIds.length > 0) {
        body.attachment_ids = sendOptions.attachmentIds;
      }

      await runTurn(
        `/api/sessions/${sessionId}/messages/stream`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json", ...csrfHeaders() },
          body: JSON.stringify(body),
        },
        generation,
      );
    },
    [runTurn, resetTransientState],
  );

  const attachToTurn = useCallback(
    async (existingTurnId: string, lastEventId = 0) => {
      generationRef.current += 1;
      const generation = generationRef.current;
      resetTransientState();
      lastEventIdRef.current = lastEventId;
      turnIdRef.current = existingTurnId;
      setText("");
      setTurnId(existingTurnId);
      setUserMessageId(null);
      setEscalation(null);
      setDoneMetadata(null);
      setError(null);
      setStatus("streaming");

      await runTurn(
        `/api/turns/${existingTurnId}/stream?last_event_id=${lastEventId}`,
        { method: "GET" },
        generation,
      );
    },
    [runTurn, resetTransientState],
  );

  const cancelTurn = useCallback(async () => {
    const id = turnIdRef.current;
    if (!id) return;
    try {
      await fetch(`/api/turns/${id}/cancel`, { method: "POST", headers: { ...csrfHeaders() } });
    } catch {
      // El `done` con `stopped: true` sigue llegando por el stream igual
      // (ver docstring de `chat_stream.py`); no hace falta reflejarlo acá.
    }
  }, []);

  return {
    status,
    text,
    turnId,
    userMessageId,
    escalation,
    doneMetadata,
    error,
    sendTurn,
    attachToTurn,
    cancelTurn,
    reset,
  };
}
