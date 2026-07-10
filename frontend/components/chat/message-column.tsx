"use client";

import type { ReactNode } from "react";
import { formatAbsoluteTime, formatRelativeTime } from "@/lib/chat/format-time";
import type { ChatRole, TurnEscalation, TurnTelemetry, VisibleToolCallView } from "@/lib/chat/types";
import { useAutoScroll } from "@/lib/chat/use-auto-scroll";
import type { Role } from "@/lib/session-context";
import { ActivityIndicator, type ActivityIndicatorLabels } from "./activity-indicator";
import { AlternateModelTag, type AlternateModelTagLabels } from "./alternate-model-tag";
import { FeedbackActions, type FeedbackActionsLabels } from "./feedback-actions";
import { MarkdownContent } from "./markdown-content";
import { ToolCallLine, type ToolCallLineLabels } from "./tool-call-line";
import { TurnTelemetryRow, type TurnTelemetryLabels } from "./turn-telemetry-row";

export interface ChatMessageItem {
  id: string;
  role: ChatRole;
  content: string;
  createdAt?: string;
  /** `"stopped"` cuando el turno se detuvo antes de completar (tarea 1.7). */
  status?: string;
  /** Telemetría del turno (tareas 4.2/4.3) -- SOLO presente para Técnico/Admin,
   * ver `TurnTelemetry`. Ausente (no `undefined` explícito, sino la clave
   * nunca poblada) para Funcional y para mensajes de usuario: decisión 7 de
   * `design.md`, la ausencia del dato es la señal que decide el render. */
  telemetry?: TurnTelemetry;
  /** `turn_metadata.is_alternate_model` (tarea 5.1) -- presente para los
   * tres roles, ver el docstring de `AlternateModelTag`. `undefined` para
   * mensajes `user` (nunca se les puebla) se trata igual que `false`. */
  isAlternateModel?: boolean;
  /** Tool calls del turno (tarea 5.2) -- ver `VisibleToolCallView` en
   * `lib/chat/types.ts`. Sin poblar todavía (streaming real de b06
   * pendiente, ver su docstring); el campo y el render ya quedan listos. */
  toolCalls?: VisibleToolCallView[];
  /** Evento de escalación del turno (tarea 5.3) -- presente SOLO si el turno
   * emitió el marcador `<<<NEEDS_PRO>>>`, ya traducido a evento de dominio por
   * `b05` (el marcador crudo nunca viaja en el texto). Su presencia es lo que
   * hace que `chat-content.tsx` renderice la tarjeta de escalación tras esta
   * respuesta (ver `renderEscalation` en `chat-content.tsx` y el gate por
   * `escalation_enabled`). */
  escalation?: TurnEscalation;
  /** id del mensaje de usuario del turno (tarea 5.3): el `origin_message_id`
   * exacto que se re-plantea al escalar. Se guarda del `done` del stream
   * (id real, no el eco optimista) en el flujo vivo, y del `parent_id` del
   * mensaje `assistant` al recargar. Solo relevante si `escalation` está
   * poblado. */
  escalationOriginUserMessageId?: string;
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
  /** Fila de telemetría por turno (tareas 4.2/4.3) -- ver `TurnTelemetryRow`. */
  telemetry: TurnTelemetryLabels;
  /** Etiqueta "modelo alterno" (tarea 5.1) -- ver `AlternateModelTag`. */
  alternateModel: AlternateModelTagLabels;
  /** Tool calls colapsadas/expandibles (tarea 5.2) -- ver `ToolCallLine`. */
  toolCall: ToolCallLineLabels;
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
  /** Rol de la sesión de identidad (tarea 5.2, `ToolCallLine`): decide
   * SOLO la visibilidad de la latencia de las tool calls (ver el docstring
   * de `ToolCallLine.role` para por qué eso no lo puede decidir la
   * ausencia del dato). Opcional y sin default forzado en el tipo -- si no
   * se pasa, se trata como el nivel mínimo de detalle (Funcional); ningún
   * mensaje de este change trae `toolCalls` poblado todavía (streaming
   * real de b06 pendiente), así que los callers existentes que no
   * necesitan tool calls no tienen que empezar a pasarlo. */
  role?: Role;
  /** Nota discreta al tope del flujo (tarea 5.3): la nota-enlace de VUELTA de
   * una sesión escalada hacia su origen (`forked_from_id`, vista 08). `null`
   * en una sesión normal. El caller decide qué mostrar -- `MessageColumn` no
   * conoce el modelo de escalación. */
  leadingNote?: ReactNode;
  /** Render de la tarjeta de escalación embebida DESPUÉS de un mensaje (tarea
   * 5.3, vista 08 §Layout): se invoca por cada mensaje ya persistido y el
   * caller devuelve la tarjeta (o `null`). Vive en el caller porque la máquina
   * de estados, el gate por `escalation_enabled` y la navegación no son
   * responsabilidad de la columna -- ver `renderEscalation` en
   * `chat-content.tsx`. */
  renderEscalation?: (message: ChatMessageItem) => ReactNode;
  /** Render del selector de versiones "‹ N/M ›" junto a un mensaje ramificado
   * (tarea 5.4, vista 09): se invoca por cada mensaje persistido y el caller
   * devuelve el `<VersionSelector>` (o `null` si el mensaje no tiene versiones
   * hermanas). Vive en el caller porque el modelo de navegación del árbol
   * (`versionNav`/`resolveVisiblePath` + el estado de versión elegida) no es
   * responsabilidad de la columna -- ver `renderVersionSelector` en
   * `chat-content.tsx`. La columna solo lo ancla junto al mensaje. */
  renderVersionSelector?: (message: ChatMessageItem) => ReactNode;
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
 * Tareas 5.1/5.2: cada mensaje `assistant` con `isAlternateModel` muestra
 * `AlternateModelTag` junto a la hora, y con `toolCalls` poblado muestra el
 * log de `ToolCallLine` colapsadas/expandibles antes de la respuesta -- ver
 * los docstrings de ambos componentes para el detalle de la capa por rol.
 *
 * Tarea 5.4: cuando el caller provee `renderVersionSelector`, cada mensaje
 * ramificado (usuario editado o respuesta regenerada) muestra el selector
 * "‹ N/M ›" anclado junto a la burbuja -- ver `VersionSelector`. Acciones de
 * copiar/regenerar quedan fuera de alcance todavía.
 */
export function MessageColumn({
  messages,
  streaming,
  labels,
  className,
  emptyStateExtra,
  role,
  leadingNote,
  renderEscalation,
  renderVersionSelector,
}: MessageColumnProps) {
  const isEmpty = messages.length === 0 && !streaming;
  // Tarea 5.2: sin `role` explícito, nivel mínimo de detalle -- ver el
  // docstring de la prop `role` de `MessageColumnProps`.
  const effectiveRole: Role = role ?? "funcional";

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
        {leadingNote}
        {isEmpty ? (
          <div className="msg-column__empty">
            <p>{labels.emptyGreeting}</p>
            {emptyStateExtra}
          </div>
        ) : (
          <ol className="msg-column__list">
            {messages.map((message) => (
              // `data-message-id` (tarea 5.4): ancla estable para el scroll al
              // mensaje ramificado al alternar de versión (ver `chat-content.tsx`)
              // y garantía de que la clave por id no re-monta el prefijo previo
              // al punto de bifurcación al cambiar de rama.
              <li key={message.id} data-message-id={message.id}>
                <ChatMessageRow
                  message={message}
                  stoppedCaption={labels.stoppedCaption}
                  feedbackLabels={labels.feedback}
                  telemetryLabels={labels.telemetry}
                  alternateModelLabels={labels.alternateModel}
                  toolCallLabels={labels.toolCall}
                  role={effectiveRole}
                  versionSelector={renderVersionSelector ? renderVersionSelector(message) : null}
                />
                {/* Tarea 5.3: la tarjeta de escalación entra DESPUÉS de la
                    respuesta del turno que la disparó (vista 08 §Layout). El
                    caller decide si hay tarjeta y en qué estado. */}
                {renderEscalation ? renderEscalation(message) : null}
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
  telemetryLabels,
  alternateModelLabels,
  toolCallLabels,
  role,
  versionSelector,
}: {
  message: ChatMessageItem;
  stoppedCaption: string;
  feedbackLabels: FeedbackActionsLabels;
  telemetryLabels: TurnTelemetryLabels;
  alternateModelLabels: AlternateModelTagLabels;
  toolCallLabels: ToolCallLineLabels;
  role: Role;
  /** Selector "‹ N/M ›" ya renderizado por el caller (tarea 5.4), o `null`
   * cuando el mensaje no tiene versiones hermanas. Se ancla debajo de la
   * burbuja, alineado a su borde (vista 09 §Layout). */
  versionSelector?: ReactNode;
}) {
  if (message.role === "user") {
    return (
      <div className="msg-row msg-row--user">
        <div className="msg-user-col">
          <div className="msg-bubble msg-bubble--user">
            <MarkdownContent content={message.content} variant="user" />
          </div>
          {versionSelector}
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
        {/* Tarea 5.2: log de tool calls del turno -- ANTES de la respuesta
            (mismo lugar donde vivía la línea de actividad en vivo mientras
            el turno estaba en curso, tarea 3.3). Sin poblar todavía, ver
            el docstring de `ChatMessageItem.toolCalls`. */}
        {message.toolCalls && message.toolCalls.length > 0 ? (
          <div className="tool-call-list">
            {message.toolCalls.map((call, index) => (
              <ToolCallLine
                key={`${message.id}-tool-${index}`}
                call={call}
                role={role}
                labels={toolCallLabels}
              />
            ))}
          </div>
        ) : null}
        <MarkdownContent content={message.content} variant="agent" />
        {/* Tarea 5.4: selector "‹ N/M ›" de una respuesta regenerada, debajo
            de la respuesta (vista 09). `null` si el turno no tiene versiones. */}
        {versionSelector}
        <div className="msg-meta">
          {message.status === "stopped" ? (
            <span className="msg-meta__stopped">{stoppedCaption}</span>
          ) : null}
          {message.createdAt ? (
            <time dateTime={message.createdAt} title={formatAbsoluteTime(message.createdAt)}>
              {formatRelativeTime(message.createdAt)}
            </time>
          ) : null}
          {/* Tarea 5.1: "junto a la hora" (vista 05 §1) -- ver docstring de
              `AlternateModelTag` para por qué la presencia de `telemetry`
              (no un chequeo de rol) decide cuánto detalle trae. */}
          {message.isAlternateModel ? (
            <AlternateModelTag
              isAlternateModel
              telemetry={message.telemetry}
              labels={alternateModelLabels}
            />
          ) : null}
          {/* Tareas 4.2/4.3: misma fila de metadatos del turno (vista 06 §2),
              nunca un panel aparte -- ver docstring de `TurnTelemetryRow`
              para por qué no hace falta un chequeo de rol acá. */}
          {message.telemetry ? (
            <TurnTelemetryRow telemetry={message.telemetry} labels={telemetryLabels} />
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
