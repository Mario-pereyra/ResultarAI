"use client";

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import type { ActivityIndicatorLabels } from "@/components/chat/activity-indicator";
import type { AlternateModelTagLabels } from "@/components/chat/alternate-model-tag";
import { Composer, type ComposerHandle, type ComposerLabels } from "@/components/chat/composer";
import { EscalationCard, type EscalationCardLabels } from "@/components/chat/escalation-card";
import type { FeedbackActionsLabels } from "@/components/chat/feedback-actions";
import {
  GatewayOfflineCard,
  type GatewayOfflineCardLabels,
} from "@/components/chat/gateway-offline-card";
import { MessageColumn, type ChatMessageItem } from "@/components/chat/message-column";
import { EditMessageButton, MessageEdit, type MessageEditLabels } from "@/components/chat/message-edit";
import { QuotaCard, type QuotaCardLabels } from "@/components/chat/quota-card";
import { SessionTaximeter, type SessionTaximeterLabels } from "@/components/chat/session-taximeter";
import { StarterSuggestions } from "@/components/chat/starter-suggestions";
import type { ToolCallLineLabels } from "@/components/chat/tool-call-line";
import type { TurnTelemetryLabels } from "@/components/chat/turn-telemetry-row";
import { VersionSelector, type VersionSelectorLabels } from "@/components/chat/version-selector";
import { Skeleton } from "@/components/ui/skeleton";
import { csrfHeaders } from "@/lib/csrf";
import { classifyTurnError } from "@/lib/chat/classify-turn-error";
import {
  countMessagesAfter,
  resolveVisiblePath,
  versionNav,
  type BranchChoices,
  type SessionBranchTree,
} from "@/lib/chat/session-tree";
import type {
  CreatedSession,
  EscalateSessionResponse,
  SessionDetail,
  SessionTreeMessage,
  TurnEscalation,
  TurnTelemetry,
  VisibleToolCallView,
} from "@/lib/chat/types";
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
  /** Etiqueta "modelo alterno" (tarea 5.1) -- ver `AlternateModelTag`. */
  alternateModel: AlternateModelTagLabels;
  /** Tool calls colapsadas/expandibles (tarea 5.2) -- ver `ToolCallLine`. */
  toolCall: ToolCallLineLabels;
  /** Selector de versiones "‹ N/M ›" de ramas (tarea 5.4) -- ver `VersionSelector`. */
  versionSelector: VersionSelectorLabels;
  /** Tarjeta de escalación a Pro (tarea 5.3) -- ver `EscalationCard`. */
  escalation: EscalationCardLabels;
  /** Nota-enlace de VUELTA en una sesión escalada hacia su origen (tarea 5.3,
   * vista 08, bidireccional): «Esta conversación continúa una consulta
   * anterior — abrir». Se muestra al tope del flujo cuando la sesión tiene
   * `forked_from_id`. */
  escalationOriginLink: string;
  /** Edición inline de un mensaje de usuario (tarea 5.5) -- ver `MessageEdit`. */
  messageEdit: MessageEditLabels;
  /** Indicador discreto de compaction (tarea 5.6) -- ver `CompactionIndicator`. */
  compactionIndicator: string;
  /** Tarjeta `GATEWAY_OFFLINE` embebida en el flujo (tarea 6.1) -- ver
   * `GatewayOfflineCard`. */
  gatewayOffline: GatewayOfflineCardLabels;
  /** Tarjeta `QUOTA` embebida en el flujo (tarea 6.2, estado UI únicamente,
   * ver el no-objetivo del proposal) -- ver `QuotaCard`. */
  quota: QuotaCardLabels;
  /** Motivo inline del composer deshabilitado por `QUOTA` (tarea 6.2, vista
   * 10 §Interacciones) -- ver `Composer.disabledReason`. */
  quotaComposerDisabledReason: string;
  /** Motivo inline del composer deshabilitado por agente no invocable
   * (tarea 7.3, vista 12 §Interacciones: "sesión cuyo agente fue
   * desactivado: se puede leer pero no continuar, composer deshabilitado
   * con motivo") -- ver `Composer.disabledReason`. */
  agentDisabledComposerReason: string;
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
 * Lee `is_alternate_model` de `turn_metadata` (tarea 5.1) -- a diferencia de
 * `telemetry`, esta clave SIEMPRE está presente para los tres roles
 * (`layer_turn_metadata`, ver `resultarai/app/use_cases/chat/telemetry.py`),
 * así que acá alcanza con leerla directo (`false` para `turn_metadata: null`,
 * mensajes de usuario o una sesión sin ese turno todavía).
 */
function extractIsAlternateModel(turnMetadata: Record<string, unknown> | null): boolean {
  if (!turnMetadata) return false;
  return Boolean(turnMetadata.is_alternate_model);
}

/**
 * Lee `compacted` de `turn_metadata` (tarea 5.6) -- misma garantía que
 * `is_alternate_model`: `layer_turn_metadata` SIEMPRE la incluye para los
 * tres roles, así que alcanza con leerla directo (`false` para
 * `turn_metadata: null` o mensajes de usuario).
 */
function extractCompacted(turnMetadata: Record<string, unknown> | null): boolean {
  if (!turnMetadata) return false;
  return Boolean(turnMetadata.compacted);
}

/**
 * Lee `tool_calls` de `turn_metadata` (tarea 5.2) -- ver el docstring de
 * `VisibleToolCallView` en `lib/chat/types.ts`: ningún camino de
 * persistencia de d13 lo puebla todavía (streaming real de b06 pendiente),
 * así que esto hoy siempre devuelve `undefined`; queda listo para cuando
 * `turn_metadata.tool_calls` empiece a llegar del backend.
 */
function extractToolCalls(
  turnMetadata: Record<string, unknown> | null,
): VisibleToolCallView[] | undefined {
  if (!turnMetadata) return undefined;
  const raw = turnMetadata.tool_calls;
  if (!Array.isArray(raw)) return undefined;
  return raw as VisibleToolCallView[];
}

/**
 * Lee `escalation` de `turn_metadata` (tarea 5.3) -- `layer_turn_metadata`
 * (`resultarai/app/use_cases/chat/telemetry.py`) SIEMPRE incluye la clave
 * `escalation` para los tres roles, con valor `null` cuando el turno no emitió
 * el marcador `<<<NEEDS_PRO>>>`. Devuelve `undefined` (no `null`) cuando no hay
 * escalación, para que `ChatMessageItem.escalation` quede sin poblar y la
 * tarjeta no se monte (mismo criterio de "ausencia, no valor vacío").
 */
function extractEscalation(
  turnMetadata: Record<string, unknown> | null,
): TurnEscalation | undefined {
  if (!turnMetadata) return undefined;
  const raw = turnMetadata.escalation;
  if (!raw || typeof raw !== "object") return undefined;
  return raw as TurnEscalation;
}

/**
 * Traduce un mensaje del árbol de la sesión (`GET /sessions/{id}`) a su
 * `ChatMessageItem` de UI. Se usa tanto al cargar la sesión como al alternar de
 * versión (tarea 5.4): en ambos casos el `id` viaja tal cual, así la clave de
 * React mantiene montado el prefijo previo al punto de bifurcación cuando cambia
 * la rama (solo se re-monta lo posterior).
 */
function treeMessageToChatItem(message: SessionTreeMessage): ChatMessageItem {
  return {
    id: message.id,
    role: message.role === "user" ? "user" : "assistant",
    content: message.content,
    createdAt: message.created_at,
    status: message.status,
    telemetry: extractTelemetry(message.turn_metadata),
    isAlternateModel: extractIsAlternateModel(message.turn_metadata),
    toolCalls: extractToolCalls(message.turn_metadata),
    escalation: extractEscalation(message.turn_metadata),
    compacted: extractCompacted(message.turn_metadata),
    // El origen re-planteado al escalar es el mensaje de usuario del turno = el
    // `parent_id` de esta respuesta (id real, persistido).
    escalationOriginUserMessageId: message.parent_id ?? undefined,
  };
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
 *
 * Tareas 6.1/6.2 (tarjetas de error accionables, vista 10 -- subconjunto
 * `GATEWAY_OFFLINE`/`QUOTA`) -- decisión sobre `components/shell/gateway-error.tsx`:
 * NO se reutiliza. Ese componente (`d10-design-system-shell`, tarea 5.6) es
 * el banner GLOBAL del shell activado por `useSession().gateway.status`
 * (una cookie de dev, `?gateway=offline`) para cuando el gateway del modelo
 * está caído EN GENERAL -- vive fuera del flujo de mensajes y no conoce
 * turnos, countdown ni reintento con backoff. La tarjeta de esta tarea es
 * otra cosa: el resultado de UN turno puntual (`use-turn-stream.ts`),
 * embebida DENTRO del flujo de mensajes en el lugar de la respuesta
 * fallida (vista 10 §Propósito), con su propio countdown/backoff y sin
 * relación con el estado global de sesión. Comparten la clase `.error-card`
 * (`app/globals.css` §5.13, la MISMA anatomía visual) y el patrón de
 * redacción por rol, pero forzar una abstracción común entre un banner de
 * shell sin estado de turno y una tarjeta de turno con countdown hubiera
 * acoplado dos ciclos de vida no relacionados -- ver el docstring de
 * `components/chat/error-card.tsx` para el detalle.
 *
 * Clasificación de errores (`lib/chat/classify-turn-error.ts`): un turno que
 * termina en `turnStream.status === "error"` se clasifica por
 * `turnStream.error.status` -- `GATEWAY_OFFLINE` para una respuesta 502/503
 * del POST del turno o una falla de red que agotó los reintentos internos
 * del hook (`error.status === null`); `QUOTA` para un `402`, la señal
 * simulada/inyectada hasta que `d16-cuotas-liberaciones` implemente el
 * enforcement real (ver el docstring de `classifyTurnError`). Cualquier otro
 * error sigue mostrando el aviso genérico `chat-shell__error` de siempre.
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
  // Tarea 5.3 (GATE ABSOLUTO): `agent.escalation_enabled` del mismo
  // `GET /api/agents/{id}`. Arranca en `false` (fail-closed): hasta que el
  // agente resuelva --o si la lectura falla-- la tarjeta de escalación NO se
  // monta jamás, aunque llegue el evento. Defensa en profundidad: el backend
  // ya suprime el marcador; esta bandera es la re-verificación de la UI.
  const [escalationEnabled, setEscalationEnabled] = useState(false);
  // Tarea 7.3 (historial vista 12, "sesión con agente deshabilitado"): `true`
  // cuando `GET /api/agents/{id}` respondió 404 para el agente REAL de la
  // sesión -- ver `effectiveAgentId` y el efecto de `loadAgent` más abajo.
  // La sesión sigue siendo LEGIBLE (los mensajes ya cargados no dependen de
  // esto); solo el composer queda deshabilitado con motivo (ver el render).
  const [composerDisabledByAgent, setComposerDisabledByAgent] = useState(false);
  // Agente REAL de la sesión ya persistida (`detail.agent_id` de
  // `GET /sessions/{id}`), distinto de `labels.agentId` (fijo en
  // "default_chat", el único agente con el que HOY se crean sesiones
  // nuevas -- selector de catálogo real es `d15`). Para una sesión nueva
  // (`sessionId` todavía `null`) no hay agente real que resolver todavía:
  // `effectiveAgentId` (más abajo) cae a `labels.agentId`.
  const [sessionAgentId, setSessionAgentId] = useState<string | null>(null);
  // Tarea 5.3 (persistencia): ids de sesiones escaladas desde esta sesión
  // (`escalated_session_ids` del detalle) y origen de esta sesión si ella misma
  // nació de una escalación (`forked_from_id`, para la nota-enlace de vuelta
  // bidireccional). Ambos vienen de `GET /sessions/{id}`; vacíos en una sesión
  // nueva.
  const [escalatedSessionIds, setEscalatedSessionIds] = useState<string[]>([]);
  const [forkedFromId, setForkedFromId] = useState<string | null>(null);

  // Tarea 5.4 (selector de versiones): árbol COMPLETO de la sesión (todas las
  // ramas, no solo la activa) tal como llega de `GET /sessions/{id}`, más su hoja
  // activa. `messages` (arriba) es la rama VISIBLE derivada de este árbol; se
  // guarda el árbol aparte para resolver `versionNav`/`resolveVisiblePath` al
  // alternar sin volver a pedir el detalle.
  const [treeMessages, setTreeMessages] = useState<SessionTreeMessage[]>([]);
  const [activeLeafId, setActiveLeafId] = useState<string | null>(null);
  // Versión elegida por punto de bifurcación (estado LOCAL): alternar solo agrega
  // o reemplaza una entrada acá; el árbol NUNCA se muta, así la rama no
  // seleccionada queda intacta y es recuperable con un ‹/›.
  const [branchChoices, setBranchChoices] = useState<BranchChoices>(() => new Map());
  // Ancla de scroll al alternar (tarea 5.4): id del mensaje ramificado recién
  // seleccionado + un nonce para re-disparar el efecto aunque el id se repita.
  const [branchScroll, setBranchScroll] = useState<{ messageId: string; nonce: number } | null>(
    null,
  );

  // Evita plegar el mismo turno dos veces si el efecto de abajo se
  // re-ejecuta (p. ej. por un re-render intermedio antes de que
  // `turnStream.reset()` termine de aplicarse).
  const foldedTurnIdRef = useRef<string | null>(null);

  // Tarea 5.5 (edición de mensaje -> rama nueva): id del mensaje de usuario
  // actualmente en edición, o `null` en reposo. Controla (vía `MessageColumn`)
  // qué burbuja muta a textarea y qué mensajes posteriores se atenúan.
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null);
  // `true` mientras el turno EN CURSO de `turnStream` es una edición (en vez
  // de un envío normal) -- decide, en el efecto de "pliegue" de abajo, si el
  // cierre del turno se resuelve recargando la sesión completa (edición) o
  // agregando un mensaje más al final (envío normal). Es un ref, no un
  // `useState`, porque `sendTurn` es la MISMA función para ambos casos
  // (decisión 4 de `design.md`) y este flag solo necesita sobrevivir entre el
  // click en "Crear rama" y el evento `done` correspondiente, sin disparar
  // renders propios.
  const editTurnRef = useRef(false);

  // Tarea 6.1 (tarjeta GATEWAY_OFFLINE): intentos consecutivos de
  // GATEWAY_OFFLINE sobre el turno pendiente actual (backoff 5→15→60 s, ver
  // `useRetryBackoff`). `0` = sin tarjeta montada. Se resetea a `0` en cada
  // envío NUEVO del usuario (`handleSubmit`, un problema distinto empieza su
  // propio backoff desde cero) y cuando el turno finalmente cierra bien (el
  // efecto de "pliegue" de abajo). Un reintento (automático o manual) NO lo
  // resetea -- reintentar reutiliza el MISMO turno pendiente.
  const [gatewayRetryAttempt, setGatewayRetryAttempt] = useState(0);
  // Texto pendiente de reintento: el MISMO contenido que falló, capturado en
  // el momento del envío (`handleSubmit`) para que el reintento (automático
  // o "Reintentar ahora") lo reenvíe sin que el usuario tenga que re-tipearlo
  // -- el eco de ese mensaje ya está en `messages` desde el envío original,
  // así que reintentar NUNCA vuelve a pushearlo (sin duplicar, tarea 6.1).
  const pendingRetryTextRef = useRef<string | null>(null);

  const loadSession = useCallback(
    async (id: string) => {
      setLoadingSession(true);
      setLoadError(false);
      try {
        const res = await fetch(`/api/sessions/${id}`);
        if (!res.ok) throw new Error("No se pudo cargar la sesión.");
        const detail = (await res.json()) as SessionDetail;
        // Tarea 5.4: se guarda el árbol completo y se resetea la elección de
        // versiones -- al (re)cargar se muestra la rama activa (default), que tras
        // una edición/regeneración es justo la versión nueva (`active_leaf_id`).
        const tree: SessionBranchTree = {
          messages: detail.messages,
          activeLeafId: detail.active_leaf_id,
        };
        const emptyChoices: BranchChoices = new Map();
        setTreeMessages(detail.messages);
        setActiveLeafId(detail.active_leaf_id);
        setBranchChoices(emptyChoices);
        // Tarea 5.5: (re)cargar la sesión sale de cualquier edición en curso
        // -- tras confirmar una edición, la recarga de acá abajo YA muestra
        // la rama nueva como activa, así que no hay nada que seguir editando.
        setEditingMessageId(null);
        setMessages(resolveVisiblePath(tree, emptyChoices).map(treeMessageToChatItem));
        // Tarea 5.3: metadatos de escalación de la sesión (persistencia +
        // nota-enlace de vuelta). Ver `renderEscalation` y `leadingNote`.
        setEscalatedSessionIds(detail.escalated_session_ids);
        setForkedFromId(detail.forked_from_id);
        // Tarea 7.3: agente REAL de la sesión (puede diferir de
        // `labels.agentId` cuando el selector de catálogo -- `d15` -- deje de
        // ser un único agente fijo) -- dispara el efecto de `loadAgent` de
        // abajo con el id correcto para decidir si el composer queda
        // deshabilitado.
        setSessionAgentId(detail.agent_id);

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

  // Tarea 7.3: agente contra el que se resuelve `GET /api/agents/{id}` --
  // el REAL de la sesión ya cargada (`sessionAgentId`, seteado por
  // `loadSession` desde `detail.agent_id`) si existe; si no (sesión nueva
  // todavía sin crear, o `detail.agent_id` nulo), cae a `labels.agentId`
  // (fijo en "default_chat" hasta que exista selector de catálogo, `d15`).
  const effectiveAgentId = sessionAgentId ?? labels.agentId;

  // Tarea 3.5 (sugerencias de inicio) + tarea 7.3 (agente deshabilitado):
  // resuelve el agente de la sesión. Un 404 (`get_agent_endpoint`: agente no
  // catalogado o no invocable -- draft/deprecated/inactive) es la señal de
  // "sesión con agente deshabilitado" de la vista 12 (§Interacciones): la
  // sesión se puede LEER (`messages` ya viene de `loadSession`, independiente
  // de este efecto) pero el composer queda deshabilitado con motivo (ver el
  // render, `composerDisabledByAgent`). Cualquier OTRO error de red/servidor
  // falla en silencio (sin sugerencias, sin deshabilitar el composer): no es
  // la misma señal que un 404 explícito y no debería bloquear al usuario por
  // un problema transitorio.
  useEffect(() => {
    let cancelled = false;
    async function loadAgent() {
      try {
        const res = await fetch(`/api/agents/${effectiveAgentId}`);
        if (res.status === 404) {
          if (!cancelled) {
            setStarterPrompts([]);
            setEscalationEnabled(false);
            setComposerDisabledByAgent(true);
          }
          return;
        }
        if (!res.ok) return;
        const data = (await res.json()) as {
          starter_prompts: string[];
          escalation_enabled: boolean;
        };
        if (!cancelled) {
          setStarterPrompts(data.starter_prompts);
          // Tarea 5.3 (GATE ABSOLUTO): solo con el agente confirmando
          // `escalation_enabled: true` la tarjeta podrá montarse. Si la lectura
          // falla, queda en `false` (fail-closed) y nunca se muestra.
          setEscalationEnabled(data.escalation_enabled);
          setComposerDisabledByAgent(false);
        }
      } catch {
        // Sin sugerencias no rompe el chat: la vista 05 sigue funcional.
        // `escalationEnabled` queda en `false`: la escalación no se ofrece.
        // `composerDisabledByAgent` NO se toca acá (ver el docstring de
        // arriba: una falla de red no es la misma señal que un 404 explícito).
      }
    }
    void loadAgent();
    return () => {
      cancelled = true;
    };
  }, [effectiveAgentId]);

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

    // Tarea 6.1: el turno cerró bien -- cualquier backoff de GATEWAY_OFFLINE
    // en curso para este mensaje ya no aplica (el próximo fallo, si lo hay,
    // es un problema NUEVO que empieza su propio backoff desde el paso 1).
    setGatewayRetryAttempt(0);
    pendingRetryTextRef.current = null;

    const metadata = turnStream.doneMetadata;

    // Tarea 5.5 (edición -> rama nueva): un turno de edición NO se pliega
    // como un mensaje más al final de `messages` -- eso dejaría la rama
    // vieja posterior colgando junto a la respuesta nueva (la vista visible
    // no es un simple append, es UNA rama distinta). En vez de reconstruir
    // el árbol a mano acá, se RECARGA la sesión completa con `loadSession`
    // -- el MISMO camino que ya prueba la tarea 5.4: el backend ya persistió
    // la rama nueva como hoja activa, así que recargar resuelve el árbol y
    // muestra el selector "N/M" correcto sin duplicar esa lógica. El
    // `reprocessed_count` de este `metadata` es autoritativo pero llega
    // TARDE para el aviso -- ese ya se mostró (estimado client-side) antes
    // de confirmar, ver `message-edit.tsx` y `countMessagesAfter`.
    if (editTurnRef.current) {
      editTurnRef.current = false;
      setEditingMessageId(null);
      turnStream.reset();
      if (sessionId) {
        router.replace(`/chat/${sessionId}`);
        // `loadSession` recarga desde el servidor tras un evento externo
        // (acá, el cierre del turno de edición) -- mismo patrón ya aceptado
        // en el efecto de `initialSessionId` de arriba, no un cascading
        // render evitable con un cálculo derivado.
        // eslint-disable-next-line react-hooks/set-state-in-effect
        void loadSession(sessionId);
      }
      return;
    }

    const finalText = turnStream.text;
    // Tarea 5.3: la escalación puede llegar en el `done` o como evento SSE
    // `escalation` aparte -- se toma de cualquiera de los dos (el hook conserva
    // `turnStream.escalation` hasta el `reset` de abajo). Se pliega junto al
    // mensaje para que la tarjeta se monte tras esta respuesta.
    const escalation = metadata.escalation ?? turnStream.escalation ?? undefined;
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
          isAlternateModel: metadata.is_alternate_model,
          toolCalls: metadata.tool_calls,
          escalation: escalation ?? undefined,
          // id REAL del mensaje de usuario del turno (no el eco optimista):
          // el `origin_message_id` exacto a re-plantear si el usuario escala.
          escalationOriginUserMessageId: metadata.user_message_id,
          // Tarea 5.6: `compacted` viaja siempre (los tres roles) -- si este
          // turno disparó la compaction del runtime, el indicador discreto
          // se monta justo antes de ESTA respuesta.
          compacted: metadata.compacted,
        },
      ];
    });

    if (sessionId) router.replace(`/chat/${sessionId}`);
    turnStream.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [turnStream.status, turnStream.doneMetadata]);

  // Tarea 5.5: un turno de edición que TERMINA EN ERROR no debe quedar
  // marcado como "edición en curso" para el próximo intento -- se limpia el
  // flag, pero `editingMessageId` se deja intacto a propósito (vista 09
  // §Estados "Error al crear rama": "el texto editado no se pierde, el
  // textarea persiste"). El aviso de error genérico (`showSendError`, ver
  // el render de abajo) ya cubre la notificación.
  //
  // Tarea 6.1 (clasificación de GATEWAY_OFFLINE): un turno de EDICIÓN que
  // falla usa ese mismo aviso genérico (vista 09), nunca la tarjeta
  // GATEWAY_OFFLINE de esta tarea -- por eso se sale temprano (`wasEdit`)
  // ANTES de clasificar, sin incrementar `gatewayRetryAttempt`. Para un
  // envío normal, cada fallo `GATEWAY_OFFLINE` nuevo (el objeto `error`
  // cambia de identidad en cada `setError`, ver `use-turn-stream.ts`)
  // incrementa el intento consecutivo -- `GatewayOfflineCard` traduce ese
  // número al paso de backoff (`useRetryBackoff`). `QUOTA` no necesita
  // tracking acá: se deriva directo de `turnStream.error` en el render (ver
  // `quotaCode` más abajo) porque, a diferencia de GATEWAY_OFFLINE, nunca se
  // reintenta solo (el composer queda deshabilitado, así que no hay forma de
  // que el usuario dispare un nuevo intento que necesite un contador).
  useEffect(() => {
    if (turnStream.status !== "error") return;
    const wasEdit = editTurnRef.current;
    editTurnRef.current = false;
    if (wasEdit) return;
    if (classifyTurnError(turnStream.error) === "GATEWAY_OFFLINE") {
      // Sincroniza con `turnStream.error` (sistema externo a este
      // componente), no "ajusta" un estado derivable en el render: mismo
      // criterio ya aceptado arriba para `loadSession`.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setGatewayRetryAttempt((n) => n + 1);
    }
  }, [turnStream.status, turnStream.error]);

  // Tarea 5.4: al alternar de versión, el scroll queda anclado al mensaje
  // ramificado (vista 09 §Interacciones). Corre DESPUÉS del commit (la nueva
  // porción posterior de la rama ya está en el DOM), busca la fila por su
  // `data-message-id` estable y la trae a la vista. Mismo patrón medible en
  // jsdom que `use-auto-scroll.ts`: `scrollIntoView` es mockeable sobre el
  // elemento real (jsdom no implementa scroll, así que se guarda el chequeo de
  // que exista para no romper en tests que no lo mockean).
  useEffect(() => {
    if (!branchScroll) return;
    const anchor = document.querySelector<HTMLElement>(
      `[data-message-id="${branchScroll.messageId}"]`,
    );
    if (anchor && typeof anchor.scrollIntoView === "function") {
      anchor.scrollIntoView({ block: "start", behavior: "auto" });
    }
  }, [branchScroll]);

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
    // Tarea 6.1: un envío NUEVO es un problema distinto -- su propio backoff
    // arranca desde cero, y este es el texto que un eventual reintento debe
    // reenviar (`retryPendingTurn`, más abajo).
    setGatewayRetryAttempt(0);
    pendingRetryTextRef.current = text;
    setMessages((prev) => [...prev, { id: nextLocalMessageId(), role: "user", content: text }]);
    await turnStream.sendTurn(id, text);
  }

  function handleStop() {
    void turnStream.cancelTurn();
  }

  /**
   * Reenvía el turno pendiente con el MISMO texto que falló (tarea 6.1,
   * `GatewayOfflineCard.onRetry` -- disparado por el countdown al llegar a
   * 0 o por "Reintentar ahora"). A diferencia de `handleSubmit`, NO agrega
   * un mensaje nuevo a `messages`: el eco del intento original ya está ahí
   * (pusheado una única vez en `handleSubmit`), y -- ver el docstring de
   * `classifyTurnError` -- un `GATEWAY_OFFLINE` significa que el POST
   * anterior nunca llegó a procesarse en el backend, así que este reintento
   * es la primera vez que ese contenido se persiste: nunca duplica un
   * mensaje ya guardado.
   */
  function retryPendingTurn() {
    const text = pendingRetryTextRef.current;
    if (!sessionId || !text) return;
    void turnStream.sendTurn(sessionId, text);
  }

  // Tarea 3.5: click en una sugerencia SOLO precarga el composer y le da
  // foco -- nunca crea la sesión ni envía el turno (eso queda para que el
  // usuario confirme con Enter/"Enviar").
  function handleStarterSelect(text: string) {
    setComposerText(text);
    composerRef.current?.focus();
  }

  // Tarea 5.5: activa la edición inline de `message` (vista 09 §Estados
  // "Editando"). Bloqueada mientras hay un turno en curso -- editar abre un
  // segundo `sendTurn` sobre el mismo `turnStream`, que no soporta dos
  // turnos concurrentes (ver `use-turn-stream.ts`).
  function handleStartEdit(message: ChatMessageItem) {
    if (isStreamingTurn) return;
    setSendError(false);
    setEditingMessageId(message.id);
  }

  // Cancelar (botón o Esc dentro de `MessageEdit`): vuelve a la burbuja de
  // lectura SIN llamar a ningún endpoint -- ninguna rama se crea.
  function handleCancelEdit() {
    setEditingMessageId(null);
  }

  // Confirmar ("Crear rama"): mismo `sendTurn` del envío normal, con
  // `edits_message_id` (decisión 4 de `design.md`) -- el flujo de rama nueva
  // + selector de versiones ya funciona por la tarea 5.4 una vez que la
  // sesión se recarga (ver el efecto de "pliegue" más arriba, rama
  // `editTurnRef.current`). `editingMessageId` se deja intacto acá: solo se
  // limpia al cerrar el turno (éxito) o lo hace el usuario cancelando
  // (error, vista 09 "el texto editado no se pierde").
  async function handleConfirmEdit(messageId: string, text: string) {
    if (!sessionId) return;
    setSendError(false);
    editTurnRef.current = true;
    await turnStream.sendTurn(sessionId, text, { editsMessageId: messageId });
  }

  // Tarea 5.3: crea la sesión escalada a Pro. Se invoca EXCLUSIVAMENTE desde el
  // click en "Continuar con Pro" de `EscalationCard` (nunca automáticamente).
  // El backend es idempotente (201 al crear, 200 si ya existía por doble clic /
  // doble pestaña): en ambos casos devolvemos el id de destino y la tarjeta
  // navega ahí sin distinguir el caso ni mostrar error.
  async function escalate(
    originUserMessageId: string | undefined,
  ): Promise<{ escalatedSessionId: string }> {
    if (!sessionId) throw new Error("No hay sesión para escalar.");
    const res = await fetch(`/api/sessions/${sessionId}/escalate`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...csrfHeaders() },
      // `origin_message_id` explícito cuando lo conocemos (el mensaje de
      // usuario exacto del turno); si falta, el backend re-plantea el último
      // mensaje de usuario de la rama activa.
      body: JSON.stringify(originUserMessageId ? { origin_message_id: originUserMessageId } : {}),
    });
    if (!res.ok) throw new Error("No se pudo escalar la sesión.");
    const data = (await res.json()) as EscalateSessionResponse;
    return { escalatedSessionId: data.escalated_session_id };
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

  // Tareas 6.1/6.2: un turno terminado en error NUNCA pasa por este bloque
  // -- no tiene texto parcial útil que mostrar como streaming, ver
  // `errorCardNode`/`errorCard` de `MessageColumn` más abajo, que ocupa el
  // MISMO lugar en la lista.
  const streaming =
    turnStream.status === "streaming" || turnStream.status === "done"
      ? { text: turnStream.text, status: turnStream.status }
      : null;

  // Tarea 6.1: la tarjeta GATEWAY_OFFLINE se mantiene montada mientras haya
  // al menos un intento fallido registrado para el turno pendiente --
  // INCLUSO durante un reintento en vuelo (`turnStream.status` vuelve a
  // "streaming" un instante mientras se reenvía), para no mostrar dos veces
  // la misma tarjeta ni un indicador de actividad genérico en el medio
  // (vista 10 §Estados: "Reintentando ... la tarjeta no se duplica").
  const showGatewayOfflineCard = gatewayRetryAttempt > 0;
  // Tarea 6.2: QUOTA no tiene reintento -- el composer queda deshabilitado,
  // así que no hay forma de que el usuario dispare un nuevo intento; alcanza
  // con derivarlo directo del error actual del turno (nunca se vuelve a
  // "streaming"/"done" sin que algo externo a este change lo resuelva).
  const quotaBlocked =
    turnStream.status === "error" && classifyTurnError(turnStream.error) === "QUOTA";

  const errorCardNode = showGatewayOfflineCard ? (
    // `key={gatewayRetryAttempt}` (no solo la prop `attempt`): fuerza un
    // REMONTE completo en cada fallo nuevo -- `useRetryBackoff` lee
    // `attempt` una sola vez al montar (ver su docstring), a propósito,
    // para no depender de un efecto que "reajuste" estado derivado de una
    // prop. Sin este `key`, React reutilizaría la MISMA instancia del
    // componente entre fallos consecutivos y el countdown se quedaría
    // pegado en el valor del primer intento.
    <GatewayOfflineCard
      key={gatewayRetryAttempt}
      attempt={gatewayRetryAttempt}
      role={user.role}
      labels={labels.gatewayOffline}
      onRetry={retryPendingTurn}
    />
  ) : quotaBlocked ? (
    <QuotaCard role={user.role} labels={labels.quota} />
  ) : null;

  // Derivado durante el render (no vía efecto): un error de streaming se
  // refleja apenas cambia `turnStream.status`, sin el "cascading render"
  // de espejar ese estado en un `useState` propio actualizado por efecto.
  // Tareas 6.1/6.2: un error YA clasificado (GATEWAY_OFFLINE/QUOTA) muestra
  // su propia tarjeta embebida (`errorCardNode`) en vez de este aviso
  // genérico -- ambos caminos son mutuamente excluyentes.
  const showSendError =
    sendError || (turnStream.status === "error" && !errorCardNode);
  const isStreamingTurn = turnStream.status === "streaming";

  // Tarea 4.2: "+ los done en vivo" -- el turno recién cerrado por SSE ya
  // tiene `doneMetadata.telemetry`, pero el efecto que lo pliega dentro de
  // `messages` corre un render después (ver el `useEffect` de arriba). Sin
  // este empalme, el taxímetro "parpadearía" un frame por detrás del último
  // costo mientras ese efecto todavía no corrió.
  const doneMetadata = turnStream.doneMetadata;
  // Vista 06 §2: el taxímetro acumula TODAS las ramas de la sesión — también las
  // descartadas por edición/regeneración ("se pagaron"). `treeMessages` trae el
  // árbol completo; en una sesión nueva aún sin recarga el árbol está vacío y se
  // cae a la rama visible (único costo existente en ese momento).
  const costSourceMessages: ReadonlyArray<{
    id: string;
    telemetry?: TurnTelemetry | undefined;
  }> =
    treeMessages.length > 0
      ? treeMessages.map((message) => ({
          id: message.id,
          telemetry: extractTelemetry(message.turn_metadata),
        }))
      : messages;
  const liveTelemetry =
    turnStream.status === "done" &&
    doneMetadata &&
    !costSourceMessages.some((message) => message.id === doneMetadata.assistant_message_id)
      ? doneMetadata.telemetry
      : undefined;
  const taximeterTotals = sumTelemetry([
    ...costSourceMessages.map((message) => message.telemetry),
    liveTelemetry,
  ]);
  const showTaximeterBar = user.role === "tecnico" || user.role === "admin";

  // Tarea 5.3: la tarjeta de escalación se renderiza tras la respuesta del
  // ÚLTIMO turno que emitió el marcador (una a la vez, coherente con "la
  // conversación siguió y la tarjeta anterior queda inerte" de la vista 08).
  // Solo mira los mensajes ya plegados: el gate por `escalation_enabled` de
  // más abajo es lo que decide si finalmente se monta.
  const lastEscalationMessageId = escalationEnabled
    ? [...messages].reverse().find((message) => message.escalation)?.id ?? null
    : null;

  /**
   * Alterna a la versión `targetId` del punto de bifurcación `parentKey`
   * (tarea 5.4). Reemplaza la elección en el estado LOCAL, re-deriva la rama
   * VISIBLE con `resolveVisiblePath` (sin mutar el árbol -> la otra rama queda
   * intacta) y ancla el scroll al mensaje ramificado recién seleccionado.
   *
   * Como el `id` del prefijo previo al punto de bifurcación no cambia, la clave
   * de React re-monta SOLO la porción posterior de la rama; lo anterior se
   * conserva montado.
   */
  function handleSelectVersion(parentKey: string, targetId: string) {
    const nextChoices = new Map(branchChoices);
    nextChoices.set(parentKey, targetId);
    setBranchChoices(nextChoices);
    setMessages(
      resolveVisiblePath({ messages: treeMessages, activeLeafId }, nextChoices).map(
        treeMessageToChatItem,
      ),
    );
    setBranchScroll((prev) => ({ messageId: targetId, nonce: (prev?.nonce ?? 0) + 1 }));
  }

  /**
   * Devuelve el selector "‹ N/M ›" para `message`, o `null` si el mensaje no
   * tiene versiones hermanas (tarea 5.4). Lo resuelve contra el árbol COMPLETO
   * (`treeMessages`), no contra la rama visible: un mensaje del prefijo común
   * sigue teniendo su grupo de hermanos correcto. Los mensajes vivos/optimistas
   * (turno en streaming aún no persistido) no están en el árbol -> `versionNav`
   * devuelve `null` y no muestran selector, que es lo correcto (un turno nuevo
   * todavía no tiene versiones alternativas).
   */
  function renderVersionSelector(message: ChatMessageItem): ReactNode {
    const nav = versionNav(treeMessages, message.id);
    if (!nav || nav.count <= 1) return null;
    const { parentKey, prevId, nextId } = nav;
    return (
      <VersionSelector
        index={nav.index}
        count={nav.count}
        onPrev={prevId ? () => handleSelectVersion(parentKey, prevId) : undefined}
        onNext={nextId ? () => handleSelectVersion(parentKey, nextId) : undefined}
        labels={labels.versionSelector}
      />
    );
  }

  /**
   * Devuelve la tarjeta de escalación para `message`, o `null`.
   *
   * GATE ABSOLUTO (defensa en profundidad): sin `escalationEnabled` no se monta
   * NADA -- ver `lastEscalationMessageId`, que ya es `null` en ese caso. Solo
   * la más reciente de las respuestas con escalación la muestra.
   *
   * Persistencia tras recarga (tarea 5.3 punto 5, aproximación documentada):
   * el detalle expone `escalated_session_ids` pero NO un mapeo turno->sesión
   * escalada ni el título de destino. Aproximación elegida: si la sesión tiene
   * al menos una sesión escalada, la tarjeta arranca en estado `escalated`
   * (nota-enlace hacia `escalated_session_ids[0]`); si no, en reposo. El
   * refinamiento (mapear cada turno con SU sesión escalada y su título) queda
   * anotado en `openspec/BACKLOG-DESCUBRIMIENTOS.md`.
   */
  function renderEscalation(message: ChatMessageItem): ReactNode {
    if (message.id !== lastEscalationMessageId || !message.escalation) return null;
    const persistedEscalatedId = escalatedSessionIds[0] ?? null;
    return (
      <EscalationCard
        reason={message.escalation.reason}
        targetProfile={message.escalation.target_profile}
        labels={labels.escalation}
        initialStatus={persistedEscalatedId ? "escalated" : "idle"}
        escalatedSessionId={persistedEscalatedId}
        onEscalate={() => escalate(message.escalationOriginUserMessageId)}
        onNavigateEscalated={(id) => router.push(`/chat/${id}`)}
      />
    );
  }

  // Tarea 5.5: botón "Editar" para `message`, o `null` si no aplica. Solo
  // mensajes de USUARIO ya persistidos (presentes en `treeMessages`) son
  // editables -- un eco optimista todavía sin id real (`local-…`, ver
  // `nextLocalMessageId`) no tiene un `edits_message_id` válido que mandarle
  // al backend todavía.
  function renderEditAction(message: ChatMessageItem): ReactNode {
    if (message.role !== "user") return null;
    if (!treeMessages.some((treeMessage) => treeMessage.id === message.id)) return null;
    return (
      <EditMessageButton
        label={labels.messageEdit.action}
        onClick={() => handleStartEdit(message)}
      />
    );
  }

  // Tarea 5.5: edición inline para `message`, SOLO cuando es el mensaje en
  // `editingMessageId`. `reprocessCount` se calcula sobre `messages` -- la
  // rama VISIBLE ya resuelta (ver el docstring de `countMessagesAfter` para
  // la relación con el `reprocessed_count` autoritativo del servidor).
  function renderMessageEdit(message: ChatMessageItem): ReactNode {
    if (message.id !== editingMessageId) return null;
    return (
      <MessageEdit
        originalText={message.content}
        reprocessCount={countMessagesAfter(messages, message.id)}
        pending={editTurnRef.current && turnStream.status === "streaming"}
        labels={labels.messageEdit}
        onConfirm={(text) => void handleConfirmEdit(message.id, text)}
        onCancel={handleCancelEdit}
      />
    );
  }

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
        role={user.role}
        labels={{
          emptyGreeting: labels.emptyGreeting,
          stoppedCaption: labels.stoppedCaption,
          streamingDoneAnnouncement: labels.streamingDoneAnnouncement,
          cursorAriaLabel: labels.cursorAriaLabel,
          activity: labels.activity,
          newMessages: labels.newMessages,
          feedback: labels.feedback,
          telemetry: labels.telemetry,
          alternateModel: labels.alternateModel,
          toolCall: labels.toolCall,
          compaction: labels.compactionIndicator,
        }}
        editingMessageId={editingMessageId}
        renderEditAction={renderEditAction}
        renderMessageEdit={renderMessageEdit}
        emptyStateExtra={
          starterPrompts.length > 0 ? (
            <StarterSuggestions prompts={starterPrompts} onSelect={handleStarterSelect} />
          ) : null
        }
        leadingNote={
          // Tarea 5.3 (nota-enlace de VUELTA, bidireccional): esta sesión nació
          // de una escalación -> enlace a su origen (`forked_from_id`).
          forkedFromId ? (
            <button
              type="button"
              className="escalate-card__origin-link"
              onClick={() => router.push(`/chat/${forkedFromId}`)}
            >
              <span className="escalate-card__branch-icon" aria-hidden="true">
                ↳
              </span>
              {labels.escalationOriginLink}
            </button>
          ) : null
        }
        renderEscalation={renderEscalation}
        renderVersionSelector={renderVersionSelector}
        errorCard={errorCardNode}
      />
      {showSendError ? (
        <p className="chat-shell__error" role="alert">
          {labels.sendError}
        </p>
      ) : null}
      <Composer
        ref={composerRef}
        labels={labels.composer}
        // Tarea 5.5: mientras se edita un mensaje, el composer normal queda
        // inactivo -- evita un segundo `sendTurn` concurrente sobre el mismo
        // `turnStream` (que solo sostiene un turno en curso a la vez). Tarea
        // 6.2: QUOTA además lo bloquea con un motivo propio (vista 10
        // §Interacciones: "es bloqueo, no solo error de turno"). Tarea 7.3:
        // agente no invocable también lo bloquea con motivo propio (vista 12
        // §Interacciones) -- la sesión sigue siendo legible, solo el composer
        // se apaga.
        disabled={editingMessageId !== null || quotaBlocked || composerDisabledByAgent}
        disabledReason={
          quotaBlocked
            ? labels.quotaComposerDisabledReason
            : composerDisabledByAgent
              ? labels.agentDisabledComposerReason
              : undefined
        }
        streaming={isStreamingTurn}
        value={composerText}
        onChange={setComposerText}
        onSubmit={handleSubmit}
        onStop={handleStop}
      />
    </div>
  );
}
