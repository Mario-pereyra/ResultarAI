"""Vista de telemetría por turno, filtrada por el rol de la sesión de identidad.

d13-chat-conversacion, tarea 4.1. Requirement `chat-experience`, "Capa de telemetría
por turno para Técnico/Admin": Técnico/Admin ven costo, perfil, latencia y chips de
cache por turno (además del `trace_id` que arma el enlace "ver traza", solo Admin);
Funcional NO ve esa capa "en absoluto". Decisión 7 de `design.md` y riesgo 4: **el
backend no confía en el frontend** -- lo que decide qué ve cada rol es la AUSENCIA de
la clave `telemetry` en el JSON entregado (nunca `null` ni `{}`), no un flag que la UI
podría ignorar u ocultar solo con CSS.

Este módulo es el punto único donde se aplica ese filtrado, para que los tres puntos
de salida del turno (evento `done` del SSE en `streaming.py`, la respuesta de
`POST /sessions/{id}/messages` y `/messages/{id}/regenerate` en `turns.py`/`app/api/
chat.py`, y `GET /sessions/{id}` en `history.py`/`app/api/chat.py`) construyan
EXACTAMENTE el mismo shape a partir del mismo dict crudo -- sin reimplementar la
lógica de "qué clave va según qué rol" en cada uno.

**Shape crudo (`RawTurnMetadata`), persistido en `Message.turn_metadata` de un
mensaje `assistant`:** lo arma `build_raw_turn_metadata`, invocado tanto por
`streaming.py` (con los datos reales de `TurnCompletion`) como por `turns.py` (camino
síncrono). `cache_write_tokens` NUNCA es un parámetro de ese builder: el contrato
`LLMResponse` de `b05-gateway-modelos` no lo expone todavía, así que viaja siempre en
`None` hasta que ese contrato lo incluya (hueco documentado en
`openspec/BACKLOG-DESCUBRIMIENTOS.md`; el chip "write" de la vista 06 queda sin dato
hasta entonces).

**Desvío documentado -- el camino síncrono (`turns.py`) tiene menos datos que el de
streaming.** `ResponseGenerator` (`turns.py`) es un callable que devuelve únicamente
`str` (a diferencia de `StreamingResponseGenerator`, que termina en un
`TurnCompletion` con `cost_usd`/`cache_hit_tokens`/etc.) -- decisión deliberada de las
tareas 1.2/1.3 para no acoplar el contrato síncrono al de streaming. Consecuencia:
`turns.py` solo puede poblar `model_profile_id` (de `session.model_profile`) y
`latency_ms` (medido alrededor de la invocación); `is_alternate_model` queda en
`False`, y `cost_usd`/`cache_hit_tokens`/`cache_miss_tokens`/`fallback_reason`/
`primary_model_profile_id` quedan en `None` -- no porque la vista los oculte (Técnico/
Admin sí los ven, solo que en `None`), sino porque el generador síncrono no expone esa
información hoy. Anotado en `openspec/BACKLOG-DESCUBRIMIENTOS.md`.

**`trace_id` (solo Admin).** Mismo desvío ya documentado en `feedback.py`
(`_resolve_trace_id`): ningún camino de persistencia de `d13` escribe hoy un
`trace_id` real de Langfuse en `turn_metadata` (`b06-runtime-grafos` todavía no abre
una traza por turno). `layer_turn_metadata` prioriza `raw["trace_id"]` si existiera y,
si no, cae al `fallback_trace_id` que cada caller pasa (el id del propio mensaje de
agente evaluado -- mismo criterio que `feedback.py`), para que el día que `b06`
complete ese campo este módulo lo recoja sin cambios.

No vive en `core/` (regla dura 1): aunque es una función pura sin I/O, opera sobre el
concepto de "rol de sesión de identidad" (`app/identity`), una noción de aplicación,
no del núcleo hexagonal.
"""

from __future__ import annotations

from typing import Any, TypedDict

__all__ = [
    "TECHNICAL_ROLES",
    "RawTurnMetadata",
    "build_raw_turn_metadata",
    "is_technical_role",
    "layer_turn_metadata",
]


class RawTurnMetadata(TypedDict):
    """Shape crudo persistido en `Message.turn_metadata` de un mensaje `assistant`.

    Ver docstring de módulo: `cache_write_tokens` siempre `None` (hueco de `b05`);
    en el camino síncrono de `turns.py`, además `cost_usd`/`cache_hit_tokens`/
    `cache_miss_tokens`/`fallback_reason`/`primary_model_profile_id` quedan en
    `None` y `is_alternate_model` en `False` (el generador síncrono no expone esos
    datos, ver docstring de módulo).
    """

    model_profile_id: str
    is_alternate_model: bool
    primary_model_profile_id: str | None
    fallback_reason: str | None
    cache_hit_tokens: int | None
    cache_miss_tokens: int | None
    cache_write_tokens: int | None
    cost_usd: float | None
    latency_ms: int | None
    compacted: bool
    escalation: dict[str, Any] | None


# Roles que ven la capa de telemetría (requirement "Capa de telemetría por turno para
# Técnico/Admin"). `admin` ve además `telemetry.trace_id` (ver `layer_turn_metadata`).
TECHNICAL_ROLES = frozenset({"tecnico", "admin"})
_ADMIN_ROLE = "admin"


def is_technical_role(role: str) -> bool:
    """`True` para `tecnico`/`admin` -- los dos roles que ven la capa de telemetría."""
    return role in TECHNICAL_ROLES


def build_raw_turn_metadata(
    *,
    model_profile_id: str,
    is_alternate_model: bool = False,
    primary_model_profile_id: str | None = None,
    fallback_reason: str | None = None,
    cache_hit_tokens: int | None = None,
    cache_miss_tokens: int | None = None,
    cost_usd: float | None = None,
    latency_ms: int | None = None,
    compacted: bool = False,
    escalation: dict[str, Any] | None = None,
) -> RawTurnMetadata:
    """Construye el dict crudo a persistir en `Message.turn_metadata` (mensaje
    `assistant`).

    Único punto que arma este shape -- lo invocan tanto `streaming.py` (con los datos
    reales del `TurnCompletion` del runtime) como `turns.py` (camino síncrono, con
    menos datos disponibles, ver docstring de módulo). `cache_write_tokens` no es un
    parámetro a propósito: siempre viaja en `None` hasta que `LLMResponse` de `b05`
    lo exponga.
    """
    return {
        "model_profile_id": model_profile_id,
        "is_alternate_model": is_alternate_model,
        "primary_model_profile_id": primary_model_profile_id,
        "fallback_reason": fallback_reason,
        "cache_hit_tokens": cache_hit_tokens,
        "cache_miss_tokens": cache_miss_tokens,
        "cache_write_tokens": None,
        "cost_usd": cost_usd,
        "latency_ms": latency_ms,
        "compacted": compacted,
        "escalation": escalation,
    }


def layer_turn_metadata(
    raw: RawTurnMetadata | dict[str, Any] | None,
    *,
    role: str,
    fallback_trace_id: str,
) -> dict[str, Any]:
    """Produce la vista de metadatos de turno filtrada por `role` (tarea 4.1).

    **Siempre presentes, para los tres roles** (tarea 5.1, indicador de compaction,
    evento de escalación -- ninguno de estos es telemetría "técnica"): `is_alternate_model`,
    `compacted`, `escalation`. `raw=None` (turno sin metadatos crudos, p. ej. un
    fail-safe) se trata igual que un dict vacío: `is_alternate_model=False`,
    `compacted=False`, `escalation=None`.

    **Solo Técnico/Admin:** la clave `telemetry`, con `cost_usd`, `model_profile_id`,
    `primary_model_profile_id`, `fallback_reason`, `latency_ms`, `cache_hit_tokens`,
    `cache_miss_tokens`, `cache_write_tokens`. Para Funcional la clave `telemetry` NO
    aparece en el dict devuelto -- ni `None` ni `{}` -- decisión 7 de `design.md`: la
    AUSENCIA de la clave es la señal, no un valor que el cliente deba interpretar.

    **Solo Admin:** `telemetry["trace_id"]`, con el mismo fallback que
    `feedback._resolve_trace_id` -- `raw["trace_id"]` si ya existiera (ver docstring
    de módulo), si no `fallback_trace_id` (el id del propio mensaje de agente).
    """
    metadata: dict[str, Any] = dict(raw) if raw else {}

    view: dict[str, Any] = {
        "is_alternate_model": bool(metadata.get("is_alternate_model", False)),
        "compacted": bool(metadata.get("compacted", False)),
        "escalation": metadata.get("escalation"),
    }

    if not is_technical_role(role):
        return view

    telemetry: dict[str, Any] = {
        "cost_usd": metadata.get("cost_usd"),
        "model_profile_id": metadata.get("model_profile_id"),
        "primary_model_profile_id": metadata.get("primary_model_profile_id"),
        "fallback_reason": metadata.get("fallback_reason"),
        "latency_ms": metadata.get("latency_ms"),
        "cache_hit_tokens": metadata.get("cache_hit_tokens"),
        "cache_miss_tokens": metadata.get("cache_miss_tokens"),
        "cache_write_tokens": metadata.get("cache_write_tokens"),
    }
    if role == _ADMIN_ROLE:
        trace_id = metadata.get("trace_id")
        telemetry["trace_id"] = str(trace_id) if trace_id else fallback_trace_id

    view["telemetry"] = telemetry
    return view
