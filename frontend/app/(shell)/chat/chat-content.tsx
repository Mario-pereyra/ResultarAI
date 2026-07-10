"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { ActivityIndicatorLabels } from "@/components/chat/activity-indicator";
import { Composer, type ComposerHandle, type ComposerLabels } from "@/components/chat/composer";
import type { FeedbackActionsLabels } from "@/components/chat/feedback-actions";
import { MessageColumn, type ChatMessageItem } from "@/components/chat/message-column";
import { SessionTaximeter, type SessionTaximeterLabels } from "@/components/chat/session-taximeter";
import { StarterSuggestions } from "@/components/chat/starter-suggestions";
import type { TurnTelemetryLabels } from "@/components/chat/turn-telemetry-row";
import { Skeleton } from "@/components/ui/skeleton";
import { csrfHeaders } from "@/lib/csrf";
import { resolveActiveBranch } from "@/lib/chat/session-tree";
import type { CreatedSession, SessionDetail, TurnTelemetry } from "@/lib/chat/types";
import { useTurnStream } from "@/lib/chat/use-turn-stream";
import { useSession } from "@/lib/session-context";

export interface ChatContentLabels {
  /** Agente con el que se crea la sesión nueva al primer envío, y con el que
   * se resuelve `GET /api/agents/{id}` (tarea 3.5, sugerencias de inicio). El
   * selector de agente es `d15` (documentado en
   * `openspec/BACKLOG-DESCUBRIMIENTOS.md`) -- por ahora siempre
   * `"default_chat"`. */
  agentId: string;
  emptyGreeting: string;
  stoppedCaption: string;
  streamingDoneAnnouncement: string;
  cursorAriaLabel: string;
  activity: ActivityIndicatorLabels;
  newMessages: string;
  feedback: FeedbackActionsLabels;
  composer: ComposerLabels;
  loading: string;
  loadError: string;
  sendError: string;
  /** Taxímetro de sesión en el header (tarea 4.2) -- ver `SessionTaximeter`. */
  taximeter: SessionTaximeterLabels;
  /** Fila de telemetría por turno (tareas 4.2/4.3) -- ver `TurnTelemetryRow`. */
  telemetry: TurnTelemetryLabels;
}

export interface ChatContentProps {
  /** `null` para una conversación nueva: la sesión se crea recién al
   * enviar el primer mensaje (tarea 1 de este change, "Rutas"). */
  initialSessionId: string | null;
  labels: ChatContentLabels;
}

// Contador de ids locales para el eco optimista del mensaje de usuario
// (tarea 3.1): se reemplaza por el id real la próxima vez que la sesión se
// recargue desde `GET /sessions/{id}` -- no se persiste ni se expone fuera
// de este módulo, así que un contador de módulo alcanza (sin colisión
// dentro de una misma pestaña, que es todo lo que necesita un `key` de
// React).
let localMessageCounter = 0;
function nextLocalMessageId(): string {
  localMessageCounter += 1;
  return `local-${localMessageCounter}`;
}

/**
 * Lee `telemetry` de `turn_metadata` (`GET /sessions/{id}`, tarea 2.3) --
 * `Record<string, unknown> | null` en el tipo del backend, así que el cast
 * final confía en el contrato ya documentado en `telemetry.py`
 * (`layer_turn_metadata`): si la clave está presente, tiene EXACTAMENTE el
 * shape de `TurnTelemetry`. Devuelve `undefined` (no `null`) para que
 * `ChatMessageItem.telemetry` quede sin poblar -- mismo criterio de
 * "ausencia, no valor vacío" que usa el backend.
 */
function extractTelemetry(turnMetadata: Record<string, unknown> | null): TurnTelemetry | undefined {
  if (!turnMetadata) return undefined;
  const raw = turnMetadata.telemetry;
  if (!raw || typeof raw !== "object") return undefined;
  return raw as TurnTelemetry;
}

/**
 * Suma acumulada de costo/tokens de un conjunto de telemetrías de turno
 * (tarea 4.2, taxímetro) + detección de "traza no disponible" (tarea 4.4).
 * Entradas `undefined` (mensajes de usuario, o rol Funcional donde
 * `telemetry` nunca existe) se ignoran. `degraded` queda en `true` si
 * ALGÚN turno no trae `trace_id` -- ver el docstring de
 * `SessionTaximeter.degraded` para por qué esta señal solo tiene efecto
 * visual para Admin (Técnico jamás trae `trace_id`, degradado o no).
 */
function sumTelemetry(items: ReadonlyArray<TurnTelemetry | undefined>): {
  costUsd: number;
  totalTokens: number;
  degraded: boolean;
} {
  let costUsd = 0;
  let totalTokens = 0;
  let degraded = false;
  for (const item of items) {
    if (!item) continue;
    costUsd += item.cost_usd ?? 0;
    totalTokens +=
      (item.cache_hit_tokens ?? 0) + (item.cache_miss_tokens ?? 0) + (item.cache_write_tokens ?? 0);
    if (!item.trace_id) degraded = true;
  }
  return { costUsd, totalTokens, degraded };
}

/**
 * Orquestación de la vista 05 (`design/VISTAS/02-chat.md`): carga/crea la
 * sesión, conecta `use-turn-stream.ts` y renderiza `MessageColumn` +
 * `Composer`. Un solo componente para ambas rutas (`chat/page.tsx`
 * y `chat/[sessionId]/page.tsx`, patrón de `app/(shell)/administracion/`) --
 * evita que crear la sesión a mitad de un turno en streaming desmonte el
 * árbol (navegar de `/chat` a `/chat/{id}` cambiaría de segmento de ruta,
 * ver la nota en `handleTurnDone` sobre CUÁNDO se actualiza la URL).
 */
export function ChatContent({ initialSessionId, labels }: ChatContentProps) {
  const router = useRouter();
  const turnStream = useTurnStream();
  const composerRef = useRef<ComposerHandle>(null);
  // Tareas 4.2/4.3/4.4: rol de la sesión de identidad -- decide SOLO la
  // visibilidad del taxímetro (capa de conveniencia de UI; la seguridad real
  // ya la aplicó el backend en `telemetry.py`, ver decisión 7 de design.md).
  const { user } = useSession();

  const [sessionId, setSessionId] = useState<string | null>(initialSessionId);
  const [messages, setMessages] = useState<ChatMessageItem[]>([]);
  const [loadingSession, setLoadingSession] = useState(initialSessionId !== null);
  const [loadError, setLoadError] = useState(false);
  const [sendError, setSendError] = useState(false);
  const [composerText, setComposerText] = useState("");
  // Sugerencias de inicio (tarea 3.5): `agent.starter_prompts` resuelto vía
  // `GET /api/agents/{id}` -- ver `MessageColumn`, que solo las muestra en
  // el estado vacío (sin mensajes ni turno en curso).
  const [starterPrompts, setStarterPrompts] = useState<string[]>([]);

  // Evita plegar el mismo turno dos veces si el efecto de abajo se
  // re-ejecuta (p. ej. por un re-render intermedio antes de que
  // `turnStream.reset()` termine de aplicarse).
  const foldedTurnIdRef = useRef<string | null>(null);

  const loadSession = useCallback(
    async (id: string) => {
      setLoadingSession(true);
      setLoadError(false);
      try {
        const res = await fetch(`/api/sessions/${id}`);
        if (!res.ok) throw new Error("No se pudo cargar la sesión.");
        const detail = (await res.json()) as SessionDetail;
        const branch = resolveActiveBranch(detail.messages, detail.active_leaf_id);
        setMessages(
          branch.map((message) => ({
            id: message.id,
            role: message.role === "user" ? "user" : "assistant",
            content: message.content,
            createdAt: message.created_at,
            status: message.status,
            telemetry: extractTelemetry(message.turn_metadata),
          })),
        );

        // Reanudar sesión (tarea 2.5): si otra pestaña/dispositivo dejó un
        // turno en curso, re-attachearse al stream real en vez de mostrar
        // la sesión como inactiva -- el mensaje de usuario de ese turno ya
        // viene en `detail.messages` (ver docstring de
        // `get_session_detail_endpoint`), así que nunca se reenvía.
        if (detail.in_progress_turn) {
          foldedTurnIdRef.current = null;
          await turnStream.attachToTurn(
            detail.in_progress_turn.turn_id,
            detail.in_progress_turn.last_event_id,
          );
        }
      } catch {
        setLoadError(true);
      } finally {
        setLoadingSession(false);
      }
    },
    // `turnStream` es estable entre renders (ver use-turn-stream.ts) pero
    // cambia de identidad de objeto en cada uno; no hace falta re-crear
    // este callback por eso.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  useEffect(() => {
    if (initialSessionId) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      loadSession(initialSessionId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialSessionId]);

  // Tarea 3.5: resuelve las sugerencias de inicio del agente una sola vez.
  // Falla en silencio (sin sugerencias) si el endpoint no responde -- no es
  // condición para que el resto del chat funcione.
  useEffect(() => {
    let cancelled = false;
    async function loadAgent() {
      try {
        const res = await fetch(`/api/agents/${labels.agentId}`);
        if (!res.ok) return;
        const data = (await res.json()) as { starter_prompts: string[] };
        if (!cancelled) setStarterPrompts(data.starter_prompts);
      } catch {
        // Sin sugerencias no rompe el chat: la vista 05 sigue funcional.
      }
    }
    void loadAgent();
    return () => {
      cancelled = true;
    };
  }, [labels.agentId]);

  // Pliega el turno en curso dentro del historial persistido cuando cierra
  // (la columna deja de mostrar el bloque "en streaming" y pasa a
  // mostrarlo como parte de `messages`, sin duplicarlo). Recién ACÁ --no
  // antes-- se sincroniza la URL a `/chat/{sessionId}` para una
  // conversación nueva: navegar antes desmontaría este árbol (cambia de
  // `chat/page.tsx` a `chat/[sessionId]/page.tsx`) y perdería el texto en
  // streaming a mitad de turno.
  useEffect(() => {
    if (turnStream.status !== "done" || !turnStream.doneMetadata) return;
    if (foldedTurnIdRef.current === turnStream.doneMetadata.turn_id) return;
    foldedTurnIdRef.current = turnStream.doneMetadata.turn_id;

    const metadata = turnStream.doneMetadata;
    const finalText = turnStream.text;
    setMessages((prev) => {
      if (prev.some((message) => message.id === metadata.assistant_message_id)) return prev;
      return [
        ...prev,
        {
          id: metadata.assistant_message_id,
          role: "assistant",
          content: finalText,
          status: metadata.stopped ? "stopped" : "complete",
          telemetry: metadata.telemetry,
        },
      ];
    });

    if (sessionId) router.replace(`/chat/${sessionId}`);
    turnStream.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [turnStream.status, turnStream.doneMetadata]);

  const ensureSession = useCallback(async (): Promise<string | null> => {
    if (sessionId) return sessionId;
    try {
      const res = await fetch("/api/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...csrfHeaders() },
        body: JSON.stringify({ agent_id: labels.agentId }),
      });
      if (!res.ok) throw new Error("No se pudo crear la sesión.");
      const created = (await res.json()) as CreatedSession;
      setSessionId(created.id);
      return created.id;
    } catch {
      setSendError(true);
      return null;
    }
  }, [sessionId, labels.agentId]);

  async function handleSubmit(text: string) {
    setSendError(false);
    const id = await ensureSession();
    if (!id) return;

    setComposerText("");
    setMessages((prev) => [...prev, { id: nextLocalMessageId(), role: "user", content: text }]);
    await turnStream.sendTurn(id, text);
  }

  function handleStop() {
    void turnStream.cancelTurn();
  }

  // Tarea 3.5: click en una sugerencia SOLO precarga el composer y le da
  // foco -- nunca crea la sesión ni envía el turno (eso queda para que el
  // usuario confirme con Enter/"Enviar").
  function handleStarterSelect(text: string) {
    setComposerText(text);
    composerRef.current?.focus();
  }

  if (loadingSession) {
    return (
      <div className="msg-column" aria-busy="true">
        <Skeleton variant="block" label={labels.loading} />
        <Skeleton variant="text" lines={3} label={labels.loading} />
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="msg-column">
        <p role="alert">{labels.loadError}</p>
      </div>
    );
  }

  const streaming =
    turnStream.status === "streaming" ||
    turnStream.status === "error" ||
    turnStream.status === "done"
      ? { text: turnStream.text, status: turnStream.status }
      : null;

  // Derivado durante el render (no vía efecto): un error de streaming se
  // refleja apenas cambia `turnStream.status`, sin el "cascading render"
  // de espejar ese estado en un `useState` propio actualizado por efecto.
  const showSendError = sendError || turnStream.status === "error";
  const isStreamingTurn = turnStream.status === "streaming";

  // Tarea 4.2: "+ los done en vivo" -- el turno recién cerrado por SSE ya
  // tiene `doneMetadata.telemetry`, pero el efecto que lo pliega dentro de
  // `messages` corre un render después (ver el `useEffect` de arriba). Sin
  // este empalme, el taxímetro "parpadearía" un frame por detrás del último
  // costo mientras ese efecto todavía no corrió.
  const doneMetadata = turnStream.doneMetadata;
  const liveTelemetry =
    turnStream.status === "done" &&
    doneMetadata &&
    !messages.some((message) => message.id === doneMetadata.assistant_message_id)
      ? doneMetadata.telemetry
      : undefined;
  const taximeterTotals = sumTelemetry([
    ...messages.map((message) => message.telemetry),
    liveTelemetry,
  ]);
  const showTaximeterBar = user.role === "tecnico" || user.role === "admin";

  return (
    <div className="chat-shell">
      {/* El chequeo de rol de acá arriba es solo para no dejar un
          `.chat-taximeter-bar` vacío en el DOM para Funcional -- la
          visibilidad REAL (incluido el desglose) la decide
          `SessionTaximeter` mismo (ver su docstring). */}
      {showTaximeterBar ? (
        <div className="chat-taximeter-bar">
          <SessionTaximeter
            role={user.role}
            costUsd={taximeterTotals.costUsd}
            totalTokens={taximeterTotals.totalTokens}
            degraded={taximeterTotals.degraded}
            labels={labels.taximeter}
          />
        </div>
      ) : null}
      <MessageColumn
        className="chat-shell__messages"
        messages={messages}
        streaming={streaming}
        labels={{
          emptyGreeting: labels.emptyGreeting,
          stoppedCaption: labels.stoppedCaption,
          streamingDoneAnnouncement: labels.streamingDoneAnnouncement,
          cursorAriaLabel: labels.cursorAriaLabel,
          activity: labels.activity,
          newMessages: labels.newMessages,
          feedback: labels.feedback,
          telemetry: labels.telemetry,
        }}
        emptyStateExtra={
          starterPrompts.length > 0 ? (
            <StarterSuggestions prompts={starterPrompts} onSelect={handleStarterSelect} />
          ) : null
        }
      />
      {showSendError ? (
        <p className="chat-shell__error" role="alert">
          {labels.sendError}
        </p>
      ) : null}
      <Composer
        ref={composerRef}
        labels={labels.composer}
        streaming={isStreamingTurn}
        value={composerText}
        onChange={setComposerText}
        onSubmit={handleSubmit}
        onStop={handleStop}
      />
    </div>
  );
}
