/**
 * Doble de fetch de alta fidelidad para el contrato HTTP/SSE del chat
 * (d13-chat-conversacion, tarea 9.1 y harness reutilizable para 9.2/9.3).
 *
 * A diferencia de `sse-mock.ts` (que da las piezas SUELTAS para armar un
 * `fetch` mock a mano por test -- reader controlado, frame SSE, respuesta
 * duck-typed), este módulo es un backend simulado COMPLETO: mantiene estado
 * en memoria (sesiones, mensajes con `parent_id`, votos) y responde a los
 * endpoints reales de `resultarai/app/api/chat.py`/`chat_stream.py` con el
 * shape exacto documentado en sus docstrings (ver también
 * `tests/app/chat/test_streaming.py`/`test_feedback.py`, que son la fuente
 * de verdad cuando el docstring no alcanza). Se apoya en `sse-mock.ts` para
 * las dos rutas de streaming (`mockSseResponse`/`sseFrame`) en vez de
 * reimplementar el formateo de frames.
 *
 * ## Por qué un "handle" imperativo por turno, no un `script` declarativo
 *
 * La tarea 9.1 necesita observar estados INTERMEDIOS del streaming
 * (indicador de actividad ANTES del primer fragmento, cursor visible
 * DURANTE, cursor ausente tras `done`) -- un `script` de fragmentos
 * pre-cargado que se auto-reproduce no permite intercalar aserciones entre
 * cada fragmento. En cambio, cada turno iniciado por
 * `POST /sessions/{id}/messages/stream` expone un `TurnHandle` que el test
 * conduce a mano (`pushFragment`/`pushEscalation`/`complete`), igual que ya
 * hacen `chat-content.test.tsx`/`message-column.test.tsx` con
 * `createControlledReader` -- este módulo generaliza ese patrón a los OTROS
 * endpoints del flujo (sesiones, agente, feedback, escalación, regenerar,
 * reconexión) para que 9.1/9.2/9.3 no tengan que reimplementar un backend
 * falso cada uno.
 *
 * ## Uso típico
 *
 * ```ts
 * const double = createChatApiDouble({ role: "tecnico", escalationEnabled: true });
 * vi.stubGlobal("fetch", double.fetch);
 *
 * render(<SessionProvider value={sessionFor("tecnico")}>
 *   <ChatContent initialSessionId={null} labels={LABELS} />
 * </SessionProvider>);
 *
 * await user.type(textarea, "¿Qué parámetro controla...?");
 * await user.click(screen.getByRole("button", { name: "Enviar" }));
 *
 * expect(await screen.findByText("Consultando…")).toBeTruthy();
 * double.currentTurn!.pushFragment("La numeración ");
 * double.currentTurn!.pushFragment("se controla con **SX5**.");
 * await waitFor(() => expect(screen.getByTestId("stream-cursor")).toBeTruthy());
 * double.currentTurn!.complete({ telemetry: { cost_usd: 0.01 } });
 * await waitFor(() => expect(screen.queryByTestId("stream-cursor")).toBeNull());
 *
 * expect(double.getMessages()).toHaveLength(2); // user + assistant, una vez cada uno
 * ```
 *
 * Para pre-poblar una sesión ya existente (árboles con ramas, tarea 9.2) sin
 * pasar por el streaming, usar `seedSession`/`seedMessage`/`setActiveLeaf`
 * ANTES de montar `<ChatContent initialSessionId={...}>` -- mismo resultado
 * que los fixtures `branchedSessionDetail()`/`EDIT_TREE_DETAIL` de
 * `chat-content.test.tsx`, pero servido por `GET /sessions/{id}` real en vez
 * de un `Response` armado a mano por test.
 *
 * ## Simplificaciones deliberadas (documentadas, no discrepancias de contrato)
 *
 * - Sin heartbeats (`: heartbeat`): son comentarios de protocolo invisibles
 *   para `readSseFrames`/`EventSource.onmessage` (decisión 3 de `design.md`),
 *   nunca parte de los eventos de dominio que este change verifica.
 * - Sin modelo de "otro usuario"/ownership: los tests de este harness operan
 *   como un único usuario logueado (mismo alcance que `SessionProvider` en
 *   los tests de componente) -- los 404 de "sesión/turno ajeno" del backend
 *   real están cubiertos por `tests/app/chat/*.py`, no por este doble de UI.
 * - `title`/`origin_session_title`/`escalated_session_title` siempre `null`:
 *   ningún componente de este change los lee (confirmado en
 *   `chat-content.tsx::escalate`); si una tarea futura los necesita, agregar
 *   un campo a `CreateChatApiDoubleOptions`/`seedSession` en vez de fijarlos
 *   a un valor constante.
 */

import type { Role } from "@/lib/session-context";
import type { TurnEscalation } from "@/lib/chat/types";
import { mockSseResponse, sseFrame } from "./sse-mock";

// ---------------------------------------------------------------------------
// Tipos públicos
// ---------------------------------------------------------------------------

/** Telemetría cruda (sin filtrar por rol) de un turno de agente -- espejo
 * ampliado de `TurnTelemetry` (`lib/chat/types.ts`) con `trace_id` SIEMPRE
 * presente acá (el filtrado por rol, incluida la ausencia de `trace_id` para
 * Técnico, lo aplica `layerTurnMetadata` al construir cada respuesta -- ver
 * `resultarai/app/use_cases/chat/telemetry.py::layer_turn_metadata`). */
export interface RawTurnTelemetry {
  cost_usd: number;
  model_profile_id: string;
  primary_model_profile_id: string;
  fallback_reason: string | null;
  latency_ms: number;
  cache_hit_tokens: number;
  cache_miss_tokens: number;
  cache_write_tokens: number | null;
  trace_id: string;
}

export interface CompleteTurnOptions {
  /** El turno cerró por cancelación (tarea 1.7) -- no usado por Flujo B, pero
   * disponible para consistencia de contrato. Default `false`. */
  stopped?: boolean;
  isAlternateModel?: boolean;
  compacted?: boolean;
  /** Se combina sobre la telemetría por defecto (`cost_usd`/`latency_ms`/…)
   * -- pasar solo los campos que el test necesita afirmar. */
  telemetry?: Partial<RawTurnTelemetry>;
}

/**
 * Turno de agente en curso, devuelto al iniciar
 * `POST /sessions/{id}/messages/stream` (normal o edición). El test lo
 * conduce a mano -- ningún fragmento se entrega solo.
 */
export interface TurnHandle {
  readonly turnId: string;
  readonly userMessageId: string;
  readonly sessionId: string;
  /** Entrega un fragmento incremental (evento SSE `fragment`) -- el texto ya
   * se asume filtrado del marcador de escalación, igual que el contrato real
   * (`chat_stream.py`: el marcador nunca viaja en `fragment.data`). */
  pushFragment(text: string): void;
  /** Entrega el evento de escalación (SSE `escalation`, cero o una vez,
   * SIEMPRE antes de `complete`) -- independiente del texto de los
   * fragmentos, igual que el contrato real. */
  pushEscalation(escalation: TurnEscalation): void;
  /** Cierra el turno: persiste el mensaje `assistant` final (contenido =
   * concatenación de los fragmentos entregados), actualiza la hoja activa de
   * la sesión y empuja el evento SSE `done` con el shape exacto de
   * `TurnDoneMetadata`, ya filtrado por el rol configurado en el doble. */
  complete(options?: CompleteTurnOptions): { assistantMessageId: string };
  /** Atajo: un único fragmento + `complete()` -- para turnos que no son el
   * foco de la aserción (p. ej. el turno de un flujo de escalación en 9.3
   * cuyo interés real es la tarjeta, no el streaming en sí). */
  completeWithText(text: string, options?: CompleteTurnOptions): { assistantMessageId: string };
  /** Corta la conexión SIN `done` (simula un corte de red) -- el turno queda
   * "vivo" en el buffer para que `GET /turns/{id}/stream` pueda reconectar. */
  cutConnection(): void;
}

export interface QueuedRegenerateReply {
  text: string;
  telemetry?: Partial<RawTurnTelemetry>;
  isAlternateModel?: boolean;
  compacted?: boolean;
}

export interface PersistedMessage {
  id: string;
  sessionId: string;
  parentId: string | null;
  role: "user" | "assistant";
  content: string;
  status: string;
  createdAt: string;
}

export interface PersistedSession {
  id: string;
  agentId: string;
  modelProfile: string;
  forkedFromId: string | null;
  activeLeafId: string | null;
}

export interface FeedbackVoteRecord {
  messageId: string;
  vote: "up" | "down";
  comment: string | null;
  traceId: string;
}

export interface CreateChatApiDoubleOptions {
  /** Rol de la sesión de identidad -- decide el filtrado de `telemetry`
   * (ausente para Funcional, sin `trace_id` para Técnico) en TODA respuesta
   * que lleve `turn_metadata`, igual que `layer_turn_metadata`. Default
   * `"funcional"`. */
  role?: Role;
  /** `agent.escalation_enabled` de `GET /api/agents/{id}` (tareas 3.5/5.3).
   * Default `true`. */
  escalationEnabled?: boolean;
  /** Default `"default_chat"` (`DEFAULT_CHAT_AGENT_ID` de
   * `app/(shell)/chat/labels.ts`, el único agente con el que hoy se crean
   * sesiones nuevas). */
  agentId?: string;
  /** Default `"Chat por Defecto"` (`DEFAULT_CHAT_AGENT_DISPLAY_NAME`). */
  agentName?: string;
  starterPrompts?: string[];
  /** `model_profile` con el que se crean sesiones nuevas (stickiness, tarea
   * 1.1). Default `"deepseek-v4-flash"`. */
  modelProfile?: string;
  /** `model_profile` de destino de una escalación (tarea 1.8). Default
   * `"deepseek-v4-pro"`. */
  escalationTargetProfile?: string;
  /** `true` simula un agente no catalogado/no invocable: `GET /agents/{id}`
   * y `POST /sessions` (con ese `agent_id`) responden 404 (tarea 7.3). */
  agentDisabled?: boolean;
}

export interface SeedMessageInput {
  /** Id explícito (p. ej. `"u1"`, `"a2b"`) -- útil para fixtures de árboles
   * de ramas legibles, mismo estilo que `chat-content.test.tsx`. Sin id,
   * se genera uno (`msg-N`). */
  id?: string;
  sessionId: string;
  parentId: string | null;
  role: "user" | "assistant";
  content: string;
  status?: string;
  /** Solo aplica a `role: "assistant"` -- se filtra por rol igual que un
   * turno real vivido a través del streaming. */
  isAlternateModel?: boolean;
  compacted?: boolean;
  escalation?: TurnEscalation | null;
  telemetry?: Partial<RawTurnTelemetry>;
  /** `created_at` explícito (ISO) -- por default usa el reloj interno del
   * doble (orden de inserción determinístico, sin depender de `Date.now()`
   * real). */
  createdAt?: string;
}

export interface SeedSessionInput {
  id?: string;
  agentId?: string;
  modelProfile?: string;
  forkedFromId?: string | null;
}

export interface ChatApiDouble {
  /** Pasar a `vi.stubGlobal("fetch", double.fetch)`. */
  fetch: typeof fetch;
  role: Role;
  /** El turno MÁS RECIENTEMENTE iniciado (por cualquier sesión) que todavía
   * no cerró (`complete`/`cutConnection`) -- `null` si no hay ninguno. Cubre
   * el caso común de un solo turno en vuelo por test; para más de uno
   * simultáneo, usar `getTurn(turnId)`. */
  readonly currentTurn: TurnHandle | null;
  getTurn(turnId: string): TurnHandle | null;
  /** Encola la respuesta del PRÓXIMO `POST /messages/{id}/regenerate`
   * (no-streaming, tarea 1.3) -- FIFO. Sin nada encolado, usa un texto por
   * defecto genérico. */
  queueRegenerateReply(reply: QueuedRegenerateReply | string): void;
  /** Crea una sesión directamente en el estado (sin pasar por
   * `POST /sessions`) -- para precargar `GET /sessions/{id}` antes de montar
   * `<ChatContent initialSessionId={...}>`. Devuelve el id (el explícito, o
   * uno generado). */
  seedSession(input?: SeedSessionInput): string;
  /** Agrega un mensaje directamente al árbol de una sesión ya sembrada --
   * ver el docstring del módulo para el patrón de árboles de ramas. Devuelve
   * el id (el explícito, o uno generado). Actualiza la hoja activa de la
   * sesión al mensaje recién insertado (mismo criterio que el backend real:
   * "la hoja activa es el mensaje sin hijos creado más recientemente") --
   * usar `setActiveLeaf` después de sembrar si el orden de inserción no
   * coincide con la rama que debe quedar activa. */
  seedMessage(input: SeedMessageInput): string;
  /** Fuerza `active_leaf_id` de una sesión ya sembrada. */
  setActiveLeaf(sessionId: string, messageId: string | null): void;
  /** Mensajes persistidos, en orden de inserción -- de todas las sesiones, o
   * solo de `sessionId` si se pasa. */
  getMessages(sessionId?: string): PersistedMessage[];
  getSessions(): PersistedSession[];
  getVotes(): FeedbackVoteRecord[];
}

// ---------------------------------------------------------------------------
// Estado interno
// ---------------------------------------------------------------------------

interface MessageRow {
  id: string;
  sessionId: string;
  parentId: string | null;
  role: "user" | "assistant";
  content: string;
  status: string;
  createdAt: string;
  /** `null` para mensajes `user` (sin telemetría de turno que reportar, ver
   * `MessageResponse` de `chat.py`). Siempre poblado para `assistant`. */
  rawTurnMetadata: RawAssistantTurnMetadata | null;
}

interface RawAssistantTurnMetadata {
  is_alternate_model: boolean;
  compacted: boolean;
  escalation: TurnEscalation | null;
  telemetry: RawTurnTelemetry;
}

interface SessionRow {
  id: string;
  agentId: string;
  modelProfile: string;
  forkedFromId: string | null;
  activeLeafId: string | null;
}

interface StoredEvent {
  id: number;
  event: string;
  data: unknown;
}

/** Buffer de eventos SSE de UN turno -- espejo minimalista de
 * `TurnStreamBuffer` (`resultarai/app/use_cases/chat/stream_registry.py`):
 * soporta múltiples lectores independientes (el turno original + N
 * reconexiones) leyendo desde cualquier `Last-Event-ID`, cierre en `done` o
 * corte explícito. */
class SseEventBuffer {
  private events: StoredEvent[] = [];
  private waiters: Array<() => void> = [];
  closed = false;

  push(event: string, data: unknown): number {
    const id = this.events.length + 1;
    this.events.push({ id, event, data });
    if (event === "done") this.closed = true;
    this.notify();
    return id;
  }

  /** Corte de conexión sin `done` -- el turno queda "vivo" para reconectar. */
  cut(): void {
    this.closed = true;
    this.notify();
  }

  private notify(): void {
    const pending = this.waiters;
    this.waiters = [];
    for (const resolve of pending) resolve();
  }

  eventsAfter(lastId: number): StoredEvent[] {
    return this.events.filter((event) => event.id > lastId);
  }

  get lastEventId(): number {
    return this.events.at(-1)?.id ?? 0;
  }

  waitForNew(): Promise<void> {
    return new Promise((resolve) => this.waiters.push(resolve));
  }
}

/** Reader duck-typed compatible con `mockSseResponse` (mismo shape que
 * `createControlledReader().reader` de `sse-mock.ts`) que reproduce
 * `buffer` desde `fromId` y sigue en vivo hasta que cierre -- ver el
 * docstring del módulo para por qué NO se usa un `ReadableStream` real. */
function createBufferReader(buffer: SseEventBuffer, fromId: number) {
  const encoder = new TextEncoder();
  let cursor = fromId;
  return {
    async read(): Promise<{ done: boolean; value?: Uint8Array }> {
      for (;;) {
        const pending = buffer.eventsAfter(cursor);
        if (pending.length > 0) {
          const next = pending[0];
          cursor = next.id;
          return {
            done: false,
            value: encoder.encode(sseFrame(next.id, next.event, next.data)),
          };
        }
        if (buffer.closed) return { done: true };
        await buffer.waitForNew();
      }
    },
  };
}

interface BufferEntry {
  buffer: SseEventBuffer;
  sessionId: string;
  userMessageId: string;
}

const TECHNICAL_ROLES: ReadonlySet<Role> = new Set(["tecnico", "admin"]);

/** Espejo de `layer_turn_metadata` (`resultarai/app/use_cases/chat/telemetry.py`):
 * `is_alternate_model`/`compacted`/`escalation` SIEMPRE presentes; `telemetry`
 * solo para Técnico/Admin, con `trace_id` solo para Admin. */
function layerTurnMetadata(raw: RawAssistantTurnMetadata, role: Role): Record<string, unknown> {
  const base: Record<string, unknown> = {
    is_alternate_model: raw.is_alternate_model,
    compacted: raw.compacted,
    escalation: raw.escalation,
  };
  if (!TECHNICAL_ROLES.has(role)) return base;
  const { trace_id, ...rest } = raw.telemetry;
  return { ...base, telemetry: role === "admin" ? { ...rest, trace_id } : rest };
}

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function extractHeader(init: RequestInit | undefined, name: string): string | null {
  const headers = init?.headers;
  if (!headers) return null;
  if (headers instanceof Headers) return headers.get(name);
  if (Array.isArray(headers)) {
    const found = headers.find(([key]) => key.toLowerCase() === name.toLowerCase());
    return found ? found[1] : null;
  }
  const record = headers as Record<string, string>;
  const key = Object.keys(record).find((candidate) => candidate.toLowerCase() === name.toLowerCase());
  return key ? record[key] : null;
}

// ---------------------------------------------------------------------------
// Factory
// ---------------------------------------------------------------------------

export function createChatApiDouble(options: CreateChatApiDoubleOptions = {}): ChatApiDouble {
  const role: Role = options.role ?? "funcional";
  const agentId = options.agentId ?? "default_chat";
  const agentName = options.agentName ?? "Chat por Defecto";
  const starterPrompts = options.starterPrompts ?? [];
  const escalationEnabled = options.escalationEnabled ?? true;
  const agentDisabled = options.agentDisabled ?? false;
  const modelProfile = options.modelProfile ?? "deepseek-v4-flash";
  const escalationTargetProfile = options.escalationTargetProfile ?? "deepseek-v4-pro";

  const sessions = new Map<string, SessionRow>();
  const messages = new Map<string, MessageRow>();
  const messagesBySession = new Map<string, string[]>();
  const buffers = new Map<string, BufferEntry>();
  const turnHandles = new Map<string, TurnHandleImpl>();
  const votes: FeedbackVoteRecord[] = [];
  const regenerateQueue: QueuedRegenerateReply[] = [];
  const escalationByOrigin = new Map<string, string>();
  const seededMessageByEscalatedSession = new Map<string, string>();
  const counters = new Map<string, number>();
  let clock = 0;
  let currentTurnId: string | null = null;

  const BASE_TIME = Date.parse("2026-07-10T12:00:00.000Z");

  function nextId(kind: string): string {
    const current = (counters.get(kind) ?? 0) + 1;
    counters.set(kind, current);
    return `${kind}-${current}`;
  }

  function nowIso(): string {
    clock += 1;
    return new Date(BASE_TIME + clock * 1000).toISOString();
  }

  function defaultTelemetry(sessionId: string): RawTurnTelemetry {
    const session = sessions.get(sessionId);
    return {
      cost_usd: 0.001,
      model_profile_id: session?.modelProfile ?? modelProfile,
      primary_model_profile_id: session?.modelProfile ?? modelProfile,
      fallback_reason: null,
      latency_ms: 500,
      cache_hit_tokens: 0,
      cache_miss_tokens: 0,
      cache_write_tokens: null,
      trace_id: nextId("trace"),
    };
  }

  function persistMessage(
    input: {
      sessionId: string;
      parentId: string | null;
      role: "user" | "assistant";
      content: string;
      status: string;
      rawTurnMetadata: RawAssistantTurnMetadata | null;
    },
    explicitId?: string,
    explicitCreatedAt?: string,
  ): MessageRow {
    const id = explicitId ?? nextId("msg");
    const row: MessageRow = {
      id,
      sessionId: input.sessionId,
      parentId: input.parentId,
      role: input.role,
      content: input.content,
      status: input.status,
      createdAt: explicitCreatedAt ?? nowIso(),
      rawTurnMetadata: input.rawTurnMetadata,
    };
    messages.set(id, row);
    const list = messagesBySession.get(input.sessionId) ?? [];
    list.push(id);
    messagesBySession.set(input.sessionId, list);
    return row;
  }

  function createSessionRow(
    input: { agentId: string; modelProfile: string; forkedFromId: string | null },
    explicitId?: string,
  ): SessionRow {
    const id = explicitId ?? nextId("session");
    const row: SessionRow = {
      id,
      agentId: input.agentId,
      modelProfile: input.modelProfile,
      forkedFromId: input.forkedFromId,
      activeLeafId: null,
    };
    sessions.set(id, row);
    messagesBySession.set(id, []);
    return row;
  }

  function findOpenBufferForSession(sessionId: string): (BufferEntry & { turnId: string }) | null {
    for (const [turnId, entry] of buffers) {
      if (entry.sessionId === sessionId && !entry.buffer.closed) return { turnId, ...entry };
    }
    return null;
  }

  /**
   * Cuenta los mensajes posteriores a `messageId` EN SU RAMA ACTIVA -- espejo
   * exacto de `count_active_descendants`
   * (`resultarai/app/use_cases/chat/_branching.py`): en cada bifurcación baja
   * SOLO por el hijo con `created_at` más reciente, no por el subárbol
   * completo. Importa la diferencia: si `messageId` tiene más de un hijo
   * (ambas ramas ya recorridas por un edit/regenerate previo), el conteo NO
   * sube por la rama abandonada -- un conteo "subárbol completo" sobrestima
   * `reprocessed_count` apenas hay más de una rama de por medio.
   */
  function countActiveDescendants(messageId: string): number {
    const childrenByParent = new Map<string, MessageRow[]>();
    for (const message of messages.values()) {
      if (message.parentId) {
        const list = childrenByParent.get(message.parentId) ?? [];
        list.push(message);
        childrenByParent.set(message.parentId, list);
      }
    }
    let count = 0;
    let currentId = messageId;
    for (;;) {
      const children = childrenByParent.get(currentId);
      if (!children || children.length === 0) return count;
      const mostRecentChild = [...children].sort(
        (a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt) || b.id.localeCompare(a.id),
      )[0];
      count += 1;
      currentId = mostRecentChild.id;
    }
  }

  function countSiblingVersions(message: MessageRow): number {
    let count = 0;
    for (const other of messages.values()) {
      if (other.role === "assistant" && other.parentId === message.parentId) count += 1;
    }
    return count;
  }

  function toSessionTreeMessageResponse(message: MessageRow): Record<string, unknown> {
    const turnMetadata =
      message.role === "assistant" && message.rawTurnMetadata
        ? layerTurnMetadata(message.rawTurnMetadata, role)
        : null;
    return {
      id: message.id,
      parent_id: message.parentId,
      role: message.role,
      content: message.content,
      status: message.status,
      created_at: message.createdAt,
      turn_metadata: turnMetadata,
    };
  }

  function toMessageResponse(message: MessageRow): Record<string, unknown> {
    return {
      id: message.id,
      session_id: message.sessionId,
      parent_id: message.parentId,
      role: message.role,
      content: message.content,
      status: message.status,
      created_at: message.createdAt,
      turn_metadata:
        message.role === "assistant" && message.rawTurnMetadata
          ? layerTurnMetadata(message.rawTurnMetadata, role)
          : null,
    };
  }

  class TurnHandleImpl implements TurnHandle {
    private accumulatedText = "";
    private closed = false;

    constructor(
      readonly turnId: string,
      readonly userMessageId: string,
      readonly sessionId: string,
      private readonly buffer: SseEventBuffer,
      private readonly reprocessedCount: number,
    ) {}

    private assertOpen(): void {
      if (this.closed) {
        throw new Error(
          `api-double: el turno ${this.turnId} ya cerró (complete/cutConnection) -- no se puede seguir operando sobre él.`,
        );
      }
    }

    pushFragment(text: string): void {
      this.assertOpen();
      this.accumulatedText += text;
      this.buffer.push("fragment", { text });
    }

    pushEscalation(escalation: TurnEscalation): void {
      this.assertOpen();
      this.buffer.push("escalation", escalation);
      this.pendingEscalation = escalation;
    }

    private pendingEscalation: TurnEscalation | null = null;

    complete(completeOptions: CompleteTurnOptions = {}): { assistantMessageId: string } {
      this.assertOpen();
      this.closed = true;

      const telemetry: RawTurnTelemetry = {
        ...defaultTelemetry(this.sessionId),
        ...completeOptions.telemetry,
      };
      const rawTurnMetadata: RawAssistantTurnMetadata = {
        is_alternate_model: completeOptions.isAlternateModel ?? false,
        compacted: completeOptions.compacted ?? false,
        escalation: this.pendingEscalation,
        telemetry,
      };

      const assistantMessage = persistMessage({
        sessionId: this.sessionId,
        parentId: this.userMessageId,
        role: "assistant",
        content: this.accumulatedText,
        status: completeOptions.stopped ? "stopped" : "complete",
        rawTurnMetadata,
      });

      const session = sessions.get(this.sessionId);
      if (session) session.activeLeafId = assistantMessage.id;

      const layered = layerTurnMetadata(rawTurnMetadata, role);
      const payload = {
        turn_id: this.turnId,
        user_message_id: this.userMessageId,
        assistant_message_id: assistantMessage.id,
        reprocessed_count: this.reprocessedCount,
        stopped: completeOptions.stopped ?? false,
        ...layered,
      };
      this.buffer.push("done", payload);

      return { assistantMessageId: assistantMessage.id };
    }

    completeWithText(
      text: string,
      completeOptions?: CompleteTurnOptions,
    ): { assistantMessageId: string } {
      this.pushFragment(text);
      return this.complete(completeOptions);
    }

    cutConnection(): void {
      this.assertOpen();
      this.closed = true;
      this.buffer.cut();
    }
  }

  function handleCreateSession(body: { agent_id?: string }): Response {
    if (!body.agent_id || body.agent_id !== agentId || agentDisabled) {
      return jsonResponse(404, { detail: "Agente no encontrado o no disponible." });
    }
    const session = createSessionRow({ agentId: body.agent_id, modelProfile, forkedFromId: null });
    return jsonResponse(201, {
      id: session.id,
      agent_id: session.agentId,
      model_profile: session.modelProfile,
      created_at: nowIso(),
    });
  }

  function handleGetAgent(requestedAgentId: string): Response {
    if (requestedAgentId !== agentId || agentDisabled) {
      return jsonResponse(404, { detail: "Agente no encontrado o no disponible." });
    }
    return jsonResponse(200, {
      id: agentId,
      name: agentName,
      starter_prompts: starterPrompts,
      escalation_enabled: escalationEnabled,
    });
  }

  function handleGetSessionDetail(sessionId: string): Response {
    const session = sessions.get(sessionId);
    if (!session) return jsonResponse(404, { detail: "Sesión no encontrada." });

    const ids = messagesBySession.get(sessionId) ?? [];
    const treeMessages = ids.map((id) => toSessionTreeMessageResponse(messages.get(id) as MessageRow));
    const escalatedSessionIds = [...sessions.values()]
      .filter((candidate) => candidate.forkedFromId === sessionId)
      .map((candidate) => candidate.id);
    const inProgress = findOpenBufferForSession(sessionId);

    return jsonResponse(200, {
      id: session.id,
      agent_id: session.agentId,
      title: null,
      model_profile: session.modelProfile,
      forked_from_id: session.forkedFromId,
      escalated_session_ids: escalatedSessionIds,
      active_leaf_id: session.activeLeafId,
      messages: treeMessages,
      in_progress_turn: inProgress
        ? {
            turn_id: inProgress.turnId,
            user_message_id: inProgress.userMessageId,
            last_event_id: inProgress.buffer.lastEventId,
          }
        : null,
    });
  }

  function handleSendStream(
    sessionId: string,
    body: { text?: string; edits_message_id?: string },
  ): Response | ReturnType<typeof mockSseResponse> {
    const session = sessions.get(sessionId);
    if (!session) return jsonResponse(404, { detail: "Sesión no encontrada." });

    const openBuffer = findOpenBufferForSession(sessionId);
    if (openBuffer) return jsonResponse(409, { turn_id: openBuffer.turnId });

    let parentId: string | null;
    let reprocessedCount = 0;
    if (body.edits_message_id) {
      const original = messages.get(body.edits_message_id);
      if (!original) return jsonResponse(404, { detail: "Mensaje no encontrado." });
      if (original.sessionId !== sessionId || original.role !== "user") {
        return jsonResponse(403, { detail: "No se puede editar un mensaje que no es propio." });
      }
      parentId = original.parentId;
      reprocessedCount = countActiveDescendants(original.id);
    } else {
      parentId = session.activeLeafId;
    }

    const userMessage = persistMessage({
      sessionId,
      parentId,
      role: "user",
      content: body.text ?? "",
      status: "complete",
      rawTurnMetadata: null,
    });
    session.activeLeafId = userMessage.id;

    const turnId = nextId("turn_test");
    const buffer = new SseEventBuffer();
    buffers.set(turnId, { buffer, sessionId, userMessageId: userMessage.id });
    const handle = new TurnHandleImpl(turnId, userMessage.id, sessionId, buffer, reprocessedCount);
    turnHandles.set(turnId, handle);
    currentTurnId = turnId;

    return mockSseResponse(createBufferReader(buffer, 0), {
      status: 200,
      headers: { "X-Turn-Id": turnId, "X-User-Message-Id": userMessage.id },
    });
  }

  function handleReconnect(
    turnId: string,
    lastEventIdRaw: string | null,
  ): Response | ReturnType<typeof mockSseResponse> {
    const entry = buffers.get(turnId);
    if (!entry) return jsonResponse(404, { detail: "Turno no encontrado." });

    let lastEventId = 0;
    if (lastEventIdRaw !== null) {
      const parsed = Number.parseInt(lastEventIdRaw, 10);
      if (Number.isNaN(parsed)) return jsonResponse(400, { detail: "Last-Event-ID inválido." });
      lastEventId = parsed;
    }

    return mockSseResponse(createBufferReader(entry.buffer, lastEventId), {
      status: 200,
      headers: { "X-Turn-Id": turnId },
    });
  }

  function handleRegenerate(messageId: string): Response {
    const original = messages.get(messageId);
    if (!original) return jsonResponse(404, { detail: "Mensaje no encontrado." });
    if (original.role !== "assistant") {
      return jsonResponse(422, { detail: "Solo se puede regenerar una respuesta del agente." });
    }

    const queued = regenerateQueue.shift();
    const queuedInput: QueuedRegenerateReply =
      typeof queued === "string" ? { text: queued } : queued ?? { text: "(respuesta regenerada)" };

    const rawTurnMetadata: RawAssistantTurnMetadata = {
      is_alternate_model: queuedInput.isAlternateModel ?? false,
      compacted: queuedInput.compacted ?? false,
      escalation: null,
      telemetry: { ...defaultTelemetry(original.sessionId), ...queuedInput.telemetry },
    };

    const sibling = persistMessage({
      sessionId: original.sessionId,
      parentId: original.parentId,
      role: "assistant",
      content: queuedInput.text,
      status: "complete",
      rawTurnMetadata,
    });

    const session = sessions.get(original.sessionId);
    if (session) session.activeLeafId = sibling.id;

    const versionCount = countSiblingVersions(sibling);

    return jsonResponse(201, {
      message: toMessageResponse(sibling),
      version: versionCount,
      version_count: versionCount,
    });
  }

  function handleFeedback(
    messageId: string,
    body: { vote?: "up" | "down"; comment?: string },
  ): Response {
    const message = messages.get(messageId);
    if (!message) return jsonResponse(404, { detail: "Mensaje no encontrado." });
    if (message.role !== "assistant") {
      return jsonResponse(422, { detail: "Solo se puede calificar una respuesta del agente." });
    }
    if (body.vote !== "up" && body.vote !== "down") {
      return jsonResponse(422, { detail: "vote debe ser 'up' o 'down'." });
    }

    const traceId = message.rawTurnMetadata?.telemetry.trace_id ?? nextId("trace");
    votes.push({ messageId, vote: body.vote, comment: body.comment ?? null, traceId });

    return jsonResponse(201, { message_id: messageId, vote: body.vote, trace_id: traceId });
  }

  function handleEscalate(sessionId: string, body: { origin_message_id?: string }): Response {
    const origin = sessions.get(sessionId);
    if (!origin) return jsonResponse(404, { detail: "Sesión no encontrada." });
    if (!escalationEnabled) {
      return jsonResponse(403, { detail: "La escalación está deshabilitada para este agente." });
    }

    let originMessageId = body.origin_message_id ?? null;
    if (!originMessageId) {
      const ids = messagesBySession.get(sessionId) ?? [];
      const lastUser = [...ids].reverse().map((id) => messages.get(id) as MessageRow).find(
        (message) => message.role === "user",
      );
      if (!lastUser) {
        return jsonResponse(422, {
          detail: "La sesión no tiene ningún mensaje de usuario para re-plantear.",
        });
      }
      originMessageId = lastUser.id;
    }

    const originMessage = messages.get(originMessageId);
    if (!originMessage || originMessage.sessionId !== sessionId || originMessage.role !== "user") {
      return jsonResponse(422, {
        detail: "origin_message_id no corresponde a un mensaje de usuario de esta sesión.",
      });
    }

    const existingEscalatedId = escalationByOrigin.get(originMessageId);
    if (existingEscalatedId) {
      const escalated = sessions.get(existingEscalatedId) as SessionRow;
      return jsonResponse(200, {
        escalated_session_id: escalated.id,
        origin_session_id: sessionId,
        model_profile: escalated.modelProfile,
        seeded_message_id: seededMessageByEscalatedSession.get(escalated.id),
        created: false,
        origin_session_title: null,
        escalated_session_title: null,
      });
    }

    const escalatedSession = createSessionRow({
      agentId: origin.agentId,
      modelProfile: escalationTargetProfile,
      forkedFromId: sessionId,
    });
    const seeded = persistMessage({
      sessionId: escalatedSession.id,
      parentId: null,
      role: "user",
      content: originMessage.content,
      status: "complete",
      rawTurnMetadata: null,
    });
    escalatedSession.activeLeafId = seeded.id;
    escalationByOrigin.set(originMessageId, escalatedSession.id);
    seededMessageByEscalatedSession.set(escalatedSession.id, seeded.id);

    return jsonResponse(201, {
      escalated_session_id: escalatedSession.id,
      origin_session_id: sessionId,
      model_profile: escalatedSession.modelProfile,
      seeded_message_id: seeded.id,
      created: true,
      origin_session_title: null,
      escalated_session_title: null,
    });
  }

  const fetchImpl = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const rawUrl = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
    const method = (init?.method ?? "GET").toUpperCase();
    const parsedUrl = new URL(rawUrl, "http://localhost");
    const path = parsedUrl.pathname;
    const body: Record<string, unknown> = init?.body ? JSON.parse(init.body as string) : {};

    if (method === "POST" && path === "/api/sessions") {
      return handleCreateSession(body as { agent_id?: string });
    }

    const agentMatch = path.match(/^\/api\/agents\/([^/]+)$/);
    if (method === "GET" && agentMatch) return handleGetAgent(agentMatch[1]);

    const streamMatch = path.match(/^\/api\/sessions\/([^/]+)\/messages\/stream$/);
    if (method === "POST" && streamMatch) {
      return handleSendStream(streamMatch[1], body as { text?: string; edits_message_id?: string });
    }

    const regenerateMatch = path.match(/^\/api\/messages\/([^/]+)\/regenerate$/);
    if (method === "POST" && regenerateMatch) return handleRegenerate(regenerateMatch[1]);

    const escalateMatch = path.match(/^\/api\/sessions\/([^/]+)\/escalate$/);
    if (method === "POST" && escalateMatch) {
      return handleEscalate(escalateMatch[1], body as { origin_message_id?: string });
    }

    const feedbackMatch = path.match(/^\/api\/messages\/([^/]+)\/feedback$/);
    if (method === "POST" && feedbackMatch) {
      return handleFeedback(feedbackMatch[1], body as { vote?: "up" | "down"; comment?: string });
    }

    const reconnectMatch = path.match(/^\/api\/turns\/([^/]+)\/stream$/);
    if (method === "GET" && reconnectMatch) {
      const headerLastEventId = extractHeader(init, "Last-Event-ID");
      const queryLastEventId = parsedUrl.searchParams.get("last_event_id");
      return handleReconnect(reconnectMatch[1], headerLastEventId ?? queryLastEventId);
    }

    // Declarado AL FINAL a propósito: matchea `/api/sessions/{id}` de forma
    // literal (sin sufijo), así que debe evaluarse después de las rutas más
    // específicas de arriba (`/messages/stream`, `/escalate`) para no
    // interceptarlas -- mismo cuidado de orden que
    // `chat.py::search_sessions_endpoint` documenta para `/sessions/search`.
    const sessionDetailMatch = path.match(/^\/api\/sessions\/([^/]+)$/);
    if (method === "GET" && sessionDetailMatch) return handleGetSessionDetail(sessionDetailMatch[1]);

    throw new Error(`api-double: ruta no implementada en el doble de chat: ${method} ${path}`);
  }) as unknown as typeof fetch;

  return {
    fetch: fetchImpl,
    role,
    get currentTurn() {
      if (!currentTurnId) return null;
      return turnHandles.get(currentTurnId) ?? null;
    },
    getTurn(turnId: string) {
      return turnHandles.get(turnId) ?? null;
    },
    queueRegenerateReply(reply: QueuedRegenerateReply | string) {
      regenerateQueue.push(typeof reply === "string" ? { text: reply } : reply);
    },
    seedSession(input: SeedSessionInput = {}) {
      const session = createSessionRow(
        {
          agentId: input.agentId ?? agentId,
          modelProfile: input.modelProfile ?? modelProfile,
          forkedFromId: input.forkedFromId ?? null,
        },
        input.id,
      );
      return session.id;
    },
    seedMessage(input: SeedMessageInput) {
      const rawTurnMetadata: RawAssistantTurnMetadata | null =
        input.role === "assistant"
          ? {
              is_alternate_model: input.isAlternateModel ?? false,
              compacted: input.compacted ?? false,
              escalation: input.escalation ?? null,
              telemetry: { ...defaultTelemetry(input.sessionId), ...input.telemetry },
            }
          : null;
      const message = persistMessage(
        {
          sessionId: input.sessionId,
          parentId: input.parentId,
          role: input.role,
          content: input.content,
          status: input.status ?? "complete",
          rawTurnMetadata,
        },
        input.id,
        input.createdAt,
      );
      const session = sessions.get(input.sessionId);
      if (session) session.activeLeafId = message.id;
      return message.id;
    },
    setActiveLeaf(sessionId: string, messageId: string | null) {
      const session = sessions.get(sessionId);
      if (session) session.activeLeafId = messageId;
    },
    getMessages(sessionId?: string): PersistedMessage[] {
      const source = sessionId
        ? (messagesBySession.get(sessionId) ?? []).map((id) => messages.get(id) as MessageRow)
        : [...messages.values()];
      return source.map((message) => ({
        id: message.id,
        sessionId: message.sessionId,
        parentId: message.parentId,
        role: message.role,
        content: message.content,
        status: message.status,
        createdAt: message.createdAt,
      }));
    },
    getSessions(): PersistedSession[] {
      return [...sessions.values()].map((session) => ({
        id: session.id,
        agentId: session.agentId,
        modelProfile: session.modelProfile,
        forkedFromId: session.forkedFromId,
        activeLeafId: session.activeLeafId,
      }));
    },
    getVotes(): FeedbackVoteRecord[] {
      return [...votes];
    },
  };
}
