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
