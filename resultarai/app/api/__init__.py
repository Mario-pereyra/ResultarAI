"""Inicialización de la API FastAPI y factory create_app (d11, sección 3)."""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.connection import get_db_session
from resultarai.adapters.persistence_postgres.models import User
from resultarai.adapters.tracing_langfuse.feedback import submit_feedback
from resultarai.app.api.admin import router as admin_router
from resultarai.app.api.attachments import router as attachments_router
from resultarai.app.api.auth import router as auth_router
from resultarai.app.api.chat import get_feedback_submitter, get_registries, get_response_generator
from resultarai.app.api.chat import router as chat_router
from resultarai.app.api.chat_stream import (
    get_streaming_response_generator,
    get_turn_stream_registry,
)
from resultarai.app.api.chat_stream import router as chat_stream_router
from resultarai.app.api.me import router as me_router
from resultarai.app.api.notifications import router as notifications_router
from resultarai.app.identity import (
    SESSION_COOKIE,
    SessionConfig,
    get_db,
    get_session_config,
    require_csrf,
    validate_session,
)
from resultarai.app.startup import bootstrap
from resultarai.app.use_cases.chat.stream_registry import TurnStreamRegistry
from resultarai.core.registries import Registries

__all__ = ["create_app"]


def csrf_guard(request: Request) -> None:
    """Enfuerza CSRF doble envío en todas las mutaciones excepto login y totp/verify."""
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        path = request.url.path.rstrip("/")
        if path not in ("/api/auth/login", "/api/auth/totp/verify"):
            require_csrf(request)


def wizard_guard(
    request: Request,
    db: Annotated[DbSession, Depends(get_db)],
    session_config: Annotated[SessionConfig, Depends(get_session_config)],
) -> None:
    """Bloquea cualquier ruta fuera de auth/wizard/agreement si el usuario
    tiene pasos pendientes.
    """
    path = request.url.path.rstrip("/")
    if path in (
        "/api/auth/login",
        "/api/auth/totp/verify",
        "/api/auth/logout",
        "/api/auth/password",
        "/api/me/totp/enroll",
        "/api/me/totp/enable",
        "/api/me/wizard/status",
        "/api/me/wizard/preferences",
        "/api/me/agreement/status",
        "/api/me/agreement/accept",
    ):
        return

    cookie_value = request.cookies.get(SESSION_COOKIE)
    if not cookie_value:
        return

    auth = validate_session(db, cookie_value, session_config)
    if not auth:
        return

    user = db.get(User, auth.user_id)
    if not user or user.status != "active":
        return

    from resultarai.app.use_cases.identity import get_wizard_status

    status = get_wizard_status(db, user)
    if status["pending_steps"]:
        if status["agreement_acceptance_pending"]:
            raise HTTPException(status_code=403, detail="AGREEMENT_PENDING")
        raise HTTPException(status_code=403, detail="WIZARD_PENDING")


def get_db_override() -> Iterator[DbSession]:
    """Generador inyectable para obtener la sesión de base de datos de Postgres."""
    with get_db_session() as session:
        yield session


@lru_cache(maxsize=1)
def _load_registries() -> Registries:
    """Ejecuta `bootstrap` una única vez y cachea el resultado para todo el proceso.

    Los manifiestos son estáticos por deployable (regla dura 6: sin manifiesto no
    existe); no hay necesidad de recargarlos por petición. `Path("manifests")` es
    relativa a la raíz del deployable, igual que asume `app/cli.py` para uso local.
    """
    return bootstrap(Path("manifests"))


def get_registries_override() -> Registries:
    """Override real de `get_registries`: los Registries de `bootstrap()`, cacheados."""
    return _load_registries()


def _feedback_submitter_override(*, trace_id: str, value: int, comment: str | None) -> None:
    """Override real de `get_feedback_submitter` (d13, endpoint de feedback):
    delega en `tracing_langfuse.feedback.submit_feedback` sin pasar `client`, para
    que el adapter resuelva por su cuenta modo real vs. mock
    (`get_langfuse_client`: mock automático bajo `PYTEST_CURRENT_TEST`/
    `LANGFUSE_MOCK`, cliente real con credenciales de entorno en producción). A
    diferencia de `get_response_generator`/`get_streaming_response_generator` (sin
    override de producción, ver `openspec/BACKLOG-DESCUBRIMIENTOS.md`), este
    adapter ya está implementado y probado -- no depende de ningún wiring
    pendiente del runtime/Policy Gate.
    """
    submit_feedback(trace_id=trace_id, value=value, comment=comment)


def _response_generator_override() -> object:
    """Override de producción de `get_response_generator`: compone el runtime de b06
    (graph default_chat_graph) con el gateway de b05 (LiteLLMClient) y el Policy Gate
    del core, usando los Registries cacheados de bootstrap().

    Inyecta DATA_NOT_INSTRUCTION_DECLARATION y strip_escalation_marker desde la capa
    app para respetar la jerarquía de imports (adapters no puede importar de app).
    """
    from resultarai.adapters.llm_litellm.client import LiteLLMClient
    from resultarai.adapters.runtime_langgraph.production_generators import (
        build_sync_graph_runner,
    )
    from resultarai.app.attachments.spotlight import DATA_NOT_INSTRUCTION_DECLARATION
    from resultarai.app.use_cases.chat._marker import strip_escalation_marker

    registries = _load_registries()
    llm_client = LiteLLMClient(model_profiles=registries.model_profiles)
    return build_sync_graph_runner(
        llm_client,
        registries,
        data_declaration=DATA_NOT_INSTRUCTION_DECLARATION,
        strip_marker=strip_escalation_marker,
    )


def _streaming_response_generator_override() -> object:
    """Override de producción de `get_streaming_response_generator`: compone el runtime
    de b06 (graph default_chat_graph) con el gateway de b05 (LiteLLMClient) y el Policy
    Gate del core, usando los Registries cacheados de bootstrap().

    Inyecta DATA_NOT_INSTRUCTION_DECLARATION y strip_escalation_marker desde la capa
    app para respetar la jerarquía de imports (adapters no puede importar de app).

    El adapter devuelve dicts crudos; esta función los envuelve en TurnFragment/
    TurnCompletion para satisfacer el protocolo StreamingResponseGenerator.
    """
    from resultarai.adapters.llm_litellm.client import LiteLLMClient
    from resultarai.adapters.runtime_langgraph.production_generators import (
        build_streaming_graph_runner,
    )
    from resultarai.app.attachments.spotlight import DATA_NOT_INSTRUCTION_DECLARATION
    from resultarai.app.use_cases.chat._marker import strip_escalation_marker
    from resultarai.app.use_cases.chat.streaming import TurnCompletion, TurnFragment

    registries = _load_registries()
    llm_client = LiteLLMClient(model_profiles=registries.model_profiles)
    raw_generator = build_streaming_graph_runner(
        llm_client,
        registries,
        data_declaration=DATA_NOT_INSTRUCTION_DECLARATION,
        strip_marker=strip_escalation_marker,
    )

    def _wrap(*, session: object, history: object) -> object:
        for item in raw_generator(session=session, history=history):
            if item["type"] == "fragment":
                yield TurnFragment(text=item["text"])
            elif item["type"] == "completion":
                yield TurnCompletion(
                    model_profile_id=item["model_profile_id"],
                    is_alternate_model=item["is_alternate_model"],
                    primary_model_profile_id=item.get("primary_model_profile_id"),
                    fallback_reason=item.get("fallback_reason"),
                    cache_hit_tokens=item.get("cache_hit_tokens"),
                    cache_miss_tokens=item.get("cache_miss_tokens"),
                    cost_usd=item.get("cost_usd"),
                    needs_pro=item.get("needs_pro", False),
                )

    return _wrap


def create_app() -> FastAPI:
    """Factory que construye e inicializa la aplicación FastAPI de la plataforma."""
    app = FastAPI(
        title="ResultarAI API",
        version="0.1.0",
        dependencies=[Depends(csrf_guard), Depends(wizard_guard)],
    )

    # Registro de routers
    app.include_router(auth_router)
    app.include_router(me_router)
    app.include_router(admin_router)
    app.include_router(notifications_router)
    app.include_router(chat_router)
    app.include_router(chat_stream_router)
    app.include_router(attachments_router)

    # Inyección de dependencias
    app.dependency_overrides[get_db] = get_db_override
    app.dependency_overrides[get_registries] = get_registries_override
    app.dependency_overrides[get_feedback_submitter] = _feedback_submitter_override
    app.dependency_overrides[get_response_generator] = _response_generator_override
    app.dependency_overrides[get_streaming_response_generator] = (
        _streaming_response_generator_override
    )
    # Una instancia de TurnStreamRegistry por app (no cacheada globalmente, a diferencia
    # de _load_registries): es estado mutable de proceso (buffers de turnos en curso),
    # no un catálogo estático de manifiestos, así que cada composición real -- o cada
    # `create_app()` de un test -- parte de un registro propio y vacío.
    turn_stream_registry = TurnStreamRegistry()
    app.dependency_overrides[get_turn_stream_registry] = lambda: turn_stream_registry

    return app
