"use client";

import { formatAbsoluteTime, formatRelativeTime } from "@/lib/chat/format-time";
import type { ChatRole } from "@/lib/chat/types";
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
}

export interface MessageColumnLabels {
  emptyGreeting: string;
  stoppedCaption: string;
  streamingDoneAnnouncement: string;
  cursorAriaLabel: string;
}

export interface MessageColumnProps {
  messages: ChatMessageItem[];
  /** Turno del agente en curso, todavía no plegado en `messages` (ver
   * `lib/chat/use-turn-stream.ts`). `null`/`undefined` cuando no hay ningún
   * turno activo. */
  streaming?: StreamingTurn | null;
  labels: MessageColumnLabels;
  className?: string;
}

/**
 * Columna de mensajes (tarea 3.1, `design/VISTAS/02-chat.md` vista 05):
 * renderiza el historial persistido más -- si lo hay -- el turno del
 * agente en curso, con markdown incremental (negritas, listas, tablas,
 * bloques de código con highlighting -- ver `MarkdownContent`, que también
 * cubre la sanitización anti-XSS de la tarea 3.2) y el cursor de bloque
 * parpadeante mientras `streaming.status === "streaming"`.
 *
 * Fuera de alcance a propósito (tareas 3.3/3.6, ver
 * `openspec/changes/d13-chat-conversacion/tasks.md`): indicador de
 * actividad de tool calls, auto-scroll/botón "nuevos mensajes", acciones
 * de turno (copiar/regenerar/👍/👎). Se deja la estructura lista para que
 * esas tareas agreguen sus propios elementos sin reescribir este
 * componente.
 */
export function MessageColumn({ messages, streaming, labels, className }: MessageColumnProps) {
  const isEmpty = messages.length === 0 && !streaming;

  return (
    <div className={["msg-column", className].filter(Boolean).join(" ")}>
      {isEmpty ? (
        <div className="msg-column__empty">
          <p>{labels.emptyGreeting}</p>
        </div>
      ) : (
        <ol className="msg-column__list">
          {messages.map((message) => (
            <li key={message.id}>
              <ChatMessageRow message={message} stoppedCaption={labels.stoppedCaption} />
            </li>
          ))}
          {streaming ? (
            <li>
              <StreamingMessageRow streaming={streaming} cursorAriaLabel={labels.cursorAriaLabel} />
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
  );
}

function ChatMessageRow({
  message,
  stoppedCaption,
}: {
  message: ChatMessageItem;
  stoppedCaption: string;
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
