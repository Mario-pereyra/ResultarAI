/**
 * Tipos compartidos del dominio de chat en el frontend (d13-chat-conversacion,
 * tareas 3.1/3.2). Reflejan literalmente el contrato de
 * `resultarai/app/api/chat.py` / `chat_stream.py` -- ver los docstrings de
 * esos módulos para el detalle de cada campo.
 */

export type ChatRole = "user" | "assistant";

/** `data` del evento SSE `escalation` (`chat_stream.py`). */
export interface TurnEscalation {
  reason: string;
  target_profile: string | null;
}

/** Estado de gobernanza de una Tool call visible -- espejo de
 * `ToolCallStatus` (`resultarai/core/audit/visibility.py`, contrato
 * `tool-call-visibility` de c09-mcp-tools): `allow` -> `executed`,
 * `escalate_hitl` -> `pending_approval`, `deny` -> `denied`. */
export type ToolCallStatus = "executed" | "pending_approval" | "denied";

/**
 * Espejo de `VisibleToolCallView` (`resultarai/core/audit/visibility.py`,
 * función `render_for_role`, tarea 5.2 del frontend): la vista de una Tool
 * call visible YA renderizada para el rol de la sesión. `parameters` viaja
 * `null` para Funcional (filtrado server-side por `render_for_role`, mismo
 * criterio de "ausencia decide" que `TurnTelemetry` -- ver su docstring).
 *
 * OJO -- asimetría documentada con `TurnTelemetry`: `duration_ms` viaja
 * POBLADO para TODOS los roles (el contrato `tool-call-visibility` de c09
 * no lo filtra por rol, a diferencia de `parameters`), así que la capa
 * "latencia solo Técnico/Admin" del requirement `chat-experience` "Tool
 * calls colapsadas y expandibles por capa de rol" la aplica el componente
 * consumidor (`components/chat/tool-call-line.tsx`), gateando
 * explícitamente por rol de sesión -- no por presencia del dato. Ver el
 * docstring de ese componente.
 *
 * Sin consumidor real todavía: el streaming SSE (`chat_stream.py`) no
 * emite tool calls hoy -- el generador real de `b06-runtime-grafos` no
 * está cableado (hueco ya documentado para `turns.py`/`streaming.py` en
 * `resultarai/app/use_cases/chat/telemetry.py` y en
 * `openspec/BACKLOG-DESCUBRIMIENTOS.md`, que agrega ahí la nota de que el
 * SSE necesitará un evento `tool_call` -- o incluirlas en el `done` --
 * cuando se cablee el runtime). Este tipo y el campo opcional `tool_calls`
 * de `TurnDoneMetadata`/`ChatMessageItem` (`components/chat/message-column.tsx`)
 * dejan el contrato listo para ese momento, con fixtures conformes a c09
 * usadas en `components/chat/tool-call-line.test.tsx`.
 */
export interface VisibleToolCallView {
  tool_name: string;
  status: ToolCallStatus;
  status_label: string;
  simple_description: string;
  parameters: Record<string, unknown> | null;
  result_preview: string | null;
  duration_ms: number | null;
}

/**
 * Capa de telemetría de un turno (tarea 4.1 del backend, `telemetry.py`
 * `layer_turn_metadata`): SOLO presente para Técnico/Admin -- ver
 * `TurnDoneMetadata.telemetry`. `trace_id` solo viaja para Admin.
 */
export interface TurnTelemetry {
  cost_usd: number | null;
  model_profile_id: string | null;
  primary_model_profile_id: string | null;
  fallback_reason: string | null;
  latency_ms: number | null;
  cache_hit_tokens: number | null;
  cache_miss_tokens: number | null;
  cache_write_tokens: number | null;
  /** Solo Admin (enlace "ver traza", tarea 4.3). */
  trace_id?: string;
}

/**
 * `data` del evento SSE `done` (`chat_stream.py`): metadatos del turno,
 * filtrados por rol server-side (tarea 4.1 -- decisión 7 de design.md: el
 * backend no confía en el cliente para ocultar telemetría). `telemetry`
 * está AUSENTE de la clave (no `null`/`{}`) cuando el rol es Funcional: la
 * ausencia es la señal, tareas 4.x la consumen así.
 */
export interface TurnDoneMetadata {
  turn_id: string;
  user_message_id: string;
  assistant_message_id: string;
  reprocessed_count: number;
  stopped: boolean;
  is_alternate_model: boolean;
  compacted: boolean;
  escalation: TurnEscalation | null;
  telemetry?: TurnTelemetry;
  /** Tool calls del turno (tarea 5.2) -- ver el docstring de
   * `VisibleToolCallView` arriba: sin poblar todavía, a la espera del
   * cableado de `b06-runtime-grafos`. */
  tool_calls?: VisibleToolCallView[];
}

/** Un mensaje del árbol completo de la sesión (`GET /sessions/{id}`, tarea 2.3). */
export interface SessionTreeMessage {
  id: string;
  parent_id: string | null;
  role: string;
  content: string;
  status: string;
  created_at: string;
  turn_metadata: Record<string, unknown> | null;
}

/** Turno en streaming en curso visto desde otra pestaña/dispositivo (tarea 2.5). */
export interface InProgressTurn {
  turn_id: string;
  user_message_id: string;
  last_event_id: number;
}

/** Respuesta de `GET /sessions/{id}` (tarea 2.3). */
export interface SessionDetail {
  id: string;
  agent_id: string | null;
  title: string | null;
  model_profile: string;
  forked_from_id: string | null;
  escalated_session_ids: string[];
  active_leaf_id: string | null;
  messages: SessionTreeMessage[];
  in_progress_turn: InProgressTurn | null;
}

/** Respuesta de `POST /sessions` (tarea 1.1). */
export interface CreatedSession {
  id: string;
  agent_id: string | null;
  model_profile: string;
  created_at: string;
}

/**
 * Respuesta de `POST /sessions/{id}/escalate` (tarea 1.8 del backend / 5.3 de
 * la UI): espejo de `EscalateSessionResponse` de `resultarai/app/api/chat.py`.
 * El endpoint responde `201` si creó la sesión escalada y `200` si devolvió
 * una ya existente (segunda llamada idempotente sobre el mismo turno de
 * origen -- doble clic / doble pestaña): `created` distingue ambos casos, pero
 * la UI navega a `escalated_session_id` en los dos por igual (misma sesión de
 * destino, sin tarjeta de error). Incluye el título de AMBAS sesiones para
 * armar la nota-enlace bidireccional de la vista 08 sin una consulta extra.
 */
export interface EscalateSessionResponse {
  escalated_session_id: string;
  origin_session_id: string;
  model_profile: string;
  seeded_message_id: string;
  created: boolean;
  origin_session_title: string | null;
  escalated_session_title: string | null;
}
