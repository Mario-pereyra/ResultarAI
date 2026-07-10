"use client";

import type { ReactNode } from "react";
import { formatAbsoluteTime, formatRelativeTime } from "@/lib/chat/format-time";
import type { ChatRole } from "@/lib/chat/types";
import { useAutoScroll } from "@/lib/chat/use-auto-scroll";
import { ActivityIndicator, type ActivityIndicatorLabels } from "./activity-indicator";
import { FeedbackActions, type FeedbackActionsLabels } from "./feedback-actions";
import { MarkdownContent } from "./markdown-content";

export interface ChatMessageItem {
  id: string;
  role: ChatRole;
  content: string;
  createdAt?: string;
  /** `"stopped"` cuando el turno se detuvo antes de completar (tarea 1.7). */
  status?: string;
}

export type StreamingTurnStatus = "streaming" | "done" | "error";

export interface StreamingTurn {
  text: string;
  status: StreamingTurnStatus;
  /** Descripción puntual de la tool call en curso (tarea 5.2, `ActivityIndicator`).
   * Sin poblar todavía en este change: `undefined` cae al texto genérico
   * "Consultando…" (tarea 3.3). */
  activityDetail?: string;
}

export interface MessageColumnLabels {
  emptyGreeting: string;
  stoppedCaption: string;
  streamingDoneAnnouncement: string;
  cursorAriaLabel: string;
  /** Línea de actividad plegada previa a la respuesta (tarea 3.3). */
  activity: ActivityIndicatorLabels;
  /** Botón flotante "↓ Nuevos mensajes" (tarea 3.3). */
  newMessages: string;
  /** Acciones 👍/👎 bajo cada respuesta completada (tarea 3.6). */
  feedback: FeedbackActionsLabels;
}

export interface MessageColumnProps {
  messages: ChatMessageItem[];
  /** Turno del agente en curso, todavía no plegado en `messages` (ver
   * `lib/chat/use-turn-stream.ts`). `null`/`undefined` cuando no hay ningún
   * turno activo. */
  streaming?: StreamingTurn | null;
  labels: MessageColumnLabels;
  className?: string;
  /** Contenido adicional del estado vacío (tarea 3.5: `StarterSuggestions`),
   * renderizado debajo del saludo SOLO cuando no hay mensajes ni turno en
   * curso. `MessageColumn` no conoce el catálogo de agentes -- el caller
   * decide qué mostrar acá. */
  emptyStateExtra?: ReactNode;
}

/**
 * Columna de mensajes (tarea 3.1, `design/VISTAS/02-chat.md` vista 05):
 * renderiza el historial persistido más -- si lo hay -- el turno del
 * agente en curso, con markdown incremental (negritas, listas, tablas,
 * bloques de código con highlighting -- ver `MarkdownContent`, que también
 * cubre la sanitización anti-XSS de la tarea 3.2) y el cursor de bloque
 * parpadeante mientras `streaming.status === "streaming"`.
 *
 * Tarea 3.3: el propio elemento con `overflow-y: auto` (`.msg-column`,
 * `useAutoScroll`) es quien mide el scroll -- mientras el turno está en
 * curso sin texto todavía, se muestra `ActivityIndicator` en el lugar que
 * ocuparía la respuesta; con cada fragmento/mensaje nuevo, si el usuario
 * estaba al final se fuerza el scroll, si no se enciende el botón flotante
 * "Nuevos mensajes" (sin forzar nada). Tarea 3.6: cada mensaje `assistant`
 * ya persistido (nunca el que sigue en streaming) muestra `FeedbackActions`.
 *
 * Fuera de alcance a propósito (tarea 5.4, ver
 * `openspec/changes/d13-chat-conversacion/tasks.md`): selector de versiones
 * y acciones de copiar/regenerar -- se deja la estructura lista para que esa
 * tarea las agregue sin reescribir este componente.
 */
export function MessageColumn({
  messages,
  streaming,
  labels,
  className,
  emptyStateExtra,
}: MessageColumnProps) {
  const isEmpty = messages.length === 0 && !streaming;

  // Cambia con cada mensaje persistido nuevo y con cada fragmento de texto
  // en streaming -- exactamente lo que dispara la reevaluación de
  // "¿el usuario sigue al final?" (tarea 3.3).
  const scrollVersion = `${messages.length}:${streaming ? streaming.text.length : -1}:${
    streaming?.status ?? "idle"
  }`;
  const { containerRef, showNewMessagesButton, handleScroll, scrollToBottom } =
    useAutoScroll(scrollVersion);

  return (
    <div className={["msg-column-region", className].filter(Boolean).join(" ")}>
      <div
        className="msg-column"
        ref={containerRef}
        onScroll={handleScroll}
        data-testid="msg-scroll-container"
      >
        {isEmpty ? (
          <div className="msg-column__empty">
            <p>{labels.emptyGreeting}</p>
            {emptyStateExtra}
          </div>
        ) : (
          <ol className="msg-column__list">
            {messages.map((message) => (
              <li key={message.id}>
                <ChatMessageRow
                  message={message}
                  stoppedCaption={labels.stoppedCaption}
                  feedbackLabels={labels.feedback}
                />
              </li>
            ))}
            {streaming ? (
              <li>
                {streaming.status === "streaming" && streaming.text.length === 0 ? (
                  <ActivityRow labels={labels.activity} detail={streaming.activityDetail} />
                ) : (
                  <StreamingMessageRow
                    streaming={streaming}
                    cursorAriaLabel={labels.cursorAriaLabel}
                  />
                )}
              </li>
            ) : null}
          </ol>
        )}
        {/* Vista 05 §0.4: la región aria-live anuncia al COMPLETAR el turno,
            nunca token por token -- por eso no envuelve el texto en
            streaming (que cambia en cada fragmento), solo este nodo aparte. */}
        <p className="sr-only" role="status" aria-live="polite">
          {streaming?.status === "done" ? labels.streamingDoneAnnouncement : ""}
        </p>
      </div>
      {showNewMessagesButton ? (
        <button type="button" className="msg-new-messages-btn" onClick={scrollToBottom}>
          {labels.newMessages}
        </button>
      ) : null}
    </div>
  );
}

function ChatMessageRow({
  message,
  stoppedCaption,
  feedbackLabels,
}: {
  message: ChatMessageItem;
  stoppedCaption: string;
  feedbackLabels: FeedbackActionsLabels;
}) {
  if (message.role === "user") {
    return (
      <div className="msg-row msg-row--user">
        <div className="msg-bubble msg-bubble--user">
          <MarkdownContent content={message.content} variant="user" />
        </div>
      </div>
    );
  }

  return (
    <div className="msg-row msg-row--agent">
      <span className="msg-avatar" aria-hidden="true">
        🤖
      </span>
      <div className="msg-agent-body">
        <MarkdownContent content={message.content} variant="agent" />
        <div className="msg-meta">
          {message.status === "stopped" ? (
            <span className="msg-meta__stopped">{stoppedCaption}</span>
          ) : null}
          {message.createdAt ? (
            <time dateTime={message.createdAt} title={formatAbsoluteTime(message.createdAt)}>
              {formatRelativeTime(message.createdAt)}
            </time>
          ) : null}
        </div>
        {/* Tarea 3.6: acciones de turno visibles recién acá -- este mensaje
            ya está persistido/completado, nunca el que sigue en streaming
            (`StreamingMessageRow`, más abajo, no las renderiza). */}
        <FeedbackActions messageId={message.id} labels={feedbackLabels} />
      </div>
    </div>
  );
}

function StreamingMessageRow({
  streaming,
  cursorAriaLabel,
}: {
  streaming: StreamingTurn;
  cursorAriaLabel: string;
}) {
  return (
    <div className="msg-row msg-row--agent" aria-busy={streaming.status === "streaming"}>
      <span className="msg-avatar" aria-hidden="true">
        🤖
      </span>
      <div className="msg-agent-body">
        <MarkdownContent content={streaming.text} variant="agent" />
        {streaming.status === "streaming" ? (
          <span
            className="chat-cursor"
            data-testid="stream-cursor"
            role="img"
            aria-label={cursorAriaLabel}
          >
            ▌
          </span>
        ) : null}
      </div>
    </div>
  );
}

function ActivityRow({ labels, detail }: { labels: ActivityIndicatorLabels; detail?: string }) {
  return (
    <div className="msg-row msg-row--agent" aria-busy="true">
      <span className="msg-avatar" aria-hidden="true">
        🤖
      </span>
      <div className="msg-agent-body">
        <ActivityIndicator labels={labels} detail={detail} />
      </div>
    </div>
  );
}
