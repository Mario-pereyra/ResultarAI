"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ComposerPlaceholder, type ComposerPlaceholderLabels } from "@/components/chat/composer-placeholder";
import { MessageColumn, type ChatMessageItem } from "@/components/chat/message-column";
import { Skeleton } from "@/components/ui/skeleton";
import { csrfHeaders } from "@/lib/csrf";
import { resolveActiveBranch } from "@/lib/chat/session-tree";
import type { CreatedSession, SessionDetail } from "@/lib/chat/types";
import { useTurnStream } from "@/lib/chat/use-turn-stream";

export interface ChatContentLabels {
  /** Agente con el que se crea la sesión nueva al primer envío. El
   * selector de agente es `d15` (documentado en
   * `openspec/BACKLOG-DESCUBRIMIENTOS.md`) -- por ahora siempre
   * `"default_chat"`. */
  agentId: string;
  emptyGreeting: string;
  stoppedCaption: string;
  streamingDoneAnnouncement: string;
  cursorAriaLabel: string;
  composer: ComposerPlaceholderLabels;
  loading: string;
  loadError: string;
  sendError: string;
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
 * Orquestación de la vista 05 (`design/VISTAS/02-chat.md`): carga/crea la
 * sesión, conecta `use-turn-stream.ts` y renderiza `MessageColumn` +
 * `ComposerPlaceholder`. Un solo componente para ambas rutas (`chat/page.tsx`
 * y `chat/[sessionId]/page.tsx`, patrón de `app/(shell)/administracion/`) --
 * evita que crear la sesión a mitad de un turno en streaming desmonte el
 * árbol (navegar de `/chat` a `/chat/{id}` cambiaría de segmento de ruta,
 * ver la nota en `handleTurnDone` sobre CUÁNDO se actualiza la URL).
 */
export function ChatContent({ initialSessionId, labels }: ChatContentProps) {
  const router = useRouter();
  const turnStream = useTurnStream();

  const [sessionId, setSessionId] = useState<string | null>(initialSessionId);
  const [messages, setMessages] = useState<ChatMessageItem[]>([]);
  const [loadingSession, setLoadingSession] = useState(initialSessionId !== null);
  const [loadError, setLoadError] = useState(false);
  const [sendError, setSendError] = useState(false);

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

    setMessages((prev) => [...prev, { id: nextLocalMessageId(), role: "user", content: text }]);
    await turnStream.sendTurn(id, text);
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

  return (
    <div className="chat-shell">
      <MessageColumn
        className="chat-shell__messages"
        messages={messages}
        streaming={streaming}
        labels={{
          emptyGreeting: labels.emptyGreeting,
          stoppedCaption: labels.stoppedCaption,
          streamingDoneAnnouncement: labels.streamingDoneAnnouncement,
          cursorAriaLabel: labels.cursorAriaLabel,
        }}
      />
      {showSendError ? (
        <p className="chat-shell__error" role="alert">
          {labels.sendError}
        </p>
      ) : null}
      <ComposerPlaceholder
        labels={labels.composer}
        sending={turnStream.status === "streaming"}
        onSubmit={handleSubmit}
      />
    </div>
  );
}
