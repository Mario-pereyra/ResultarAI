"""Sesiones server-side firmadas y revocables (d11, tarea 2.2).

Modelo (design Decisions 2 y 3, ADR-0008):

- El token de sesión es de alta entropía (``secrets.token_urlsafe``). En la base
  se guarda solo su SHA-256 en hex como ``AuthSession.id`` (nunca el token en
  claro): una filtración de la base no expone tokens usables.
- La cookie transporta el token **firmado** con ``itsdangerous`` (detecta
  manipulación sin ir a la base). La validez real (revocada / expirada / activa)
  se resuelve siempre contra la fila server-side, lo que habilita revocación
  inmediata.
- Doble expiración: por inactividad (``idle_timeout`` desde ``last_seen_at``) y
  por máximo absoluto (``absolute_lifetime`` desde ``created_at``, materializado
  en ``expires_at``), lo que ocurra primero.

Variables de entorno (leídas por :meth:`SessionConfig.from_env`):

- ``IDENTITY_SESSION_SIGNING_KEY``: clave de firma de la cookie. **Obligatoria en
  producción.** Si falta, se genera una efímera y se emite un warning (solo apto
  para dev/tests: al reiniciar el proceso invalida todas las cookies emitidas).
- ``IDENTITY_SESSION_IDLE_TIMEOUT_SECONDS``: timeout de inactividad (default 1800
  = 30 min).
- ``IDENTITY_SESSION_ABSOLUTE_LIFETIME_SECONDS``: vida máxima absoluta (default
  28800 = 8 h).
- ``IDENTITY_COOKIE_SECURE``: ``true``/``false`` para el atributo ``Secure`` de la
  cookie (default ``true``; poner ``false`` solo en dev sobre HTTP).
"""

from __future__ import annotations

import hashlib
import os
import secrets
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import Response
from itsdangerous import BadData, URLSafeTimedSerializer
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.models import AuthSession, get_utc_now

__all__ = [
    "SESSION_COOKIE",
    "CreatedSession",
    "SessionConfig",
    "clear_session_cookie",
    "create_session",
    "revoke_all_sessions",
    "revoke_session",
    "set_session_cookie",
    "validate_session",
]

# Nombre de la cookie de sesión (la sección 3 la reutiliza).
SESSION_COOKIE = "resultarai_session"

# Bytes de entropía del token de sesión (256 bits).
_TOKEN_BYTES = 32

# ``salt`` del serializador: separa el dominio de firma de otros usos de la misma
# clave; no es secreto.
_SIGNER_SALT = "resultarai.session"


def _env_int(name: str, default: int) -> int:
    """Lee un entero de entorno con default; ignora valores no numéricos."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    """Lee un booleano de entorno (``true``/``1`` -> True)."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class SessionConfig:
    """Configuración de sesión con defaults sanos y override por entorno."""

    signing_key: str = field(repr=False)
    idle_timeout: timedelta = timedelta(minutes=30)
    absolute_lifetime: timedelta = timedelta(hours=8)
    cookie_secure: bool = True

    @classmethod
    def from_env(cls) -> SessionConfig:
        """Construye la configuración desde variables de entorno.

        Si ``IDENTITY_SESSION_SIGNING_KEY`` no está definida, genera una clave
        efímera y avisa: aceptable en dev/tests, nunca en producción.
        """
        signing_key = os.environ.get("IDENTITY_SESSION_SIGNING_KEY")
        if not signing_key:
            signing_key = secrets.token_urlsafe(_TOKEN_BYTES)
            warnings.warn(
                "IDENTITY_SESSION_SIGNING_KEY no está definida: se generó una clave "
                "de firma efímera. Válido solo en dev/tests; en producción define "
                "esta variable o todas las sesiones se invalidan al reiniciar.",
                RuntimeWarning,
                stacklevel=2,
            )
        return cls(
            signing_key=signing_key,
            idle_timeout=timedelta(seconds=_env_int("IDENTITY_SESSION_IDLE_TIMEOUT_SECONDS", 1800)),
            absolute_lifetime=timedelta(
                seconds=_env_int("IDENTITY_SESSION_ABSOLUTE_LIFETIME_SECONDS", 28800)
            ),
            cookie_secure=_env_bool("IDENTITY_COOKIE_SECURE", True),
        )


@dataclass(frozen=True)
class CreatedSession:
    """Resultado de crear una sesión.

    ``cookie_value`` es el token firmado a poner en la cookie; ``session_id`` es
    el hash SHA-256 hex que identifica la fila server-side; ``expires_at`` es el
    máximo absoluto (útil como ``max_age`` de la cookie).
    """

    cookie_value: str
    session_id: str
    expires_at: datetime


def _hash_token(token: str) -> str:
    """Devuelve el SHA-256 hex del token (identificador server-side)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _serializer(config: SessionConfig) -> URLSafeTimedSerializer:
    """Serializador firmante para el token de la cookie."""
    return URLSafeTimedSerializer(config.signing_key, salt=_SIGNER_SALT)


def create_session(
    db: DbSession,
    user_id: UUID,
    config: SessionConfig,
    *,
    now: datetime | None = None,
) -> CreatedSession:
    """Crea una sesión server-side y devuelve el valor firmado de la cookie.

    Persiste una fila ``auth_sessions`` cuyo ``id`` es el SHA-256 del token; el
    token en claro solo existe firmado dentro de ``cookie_value``.
    """
    now = now or get_utc_now()
    token = secrets.token_urlsafe(_TOKEN_BYTES)
    session_id = _hash_token(token)
    expires_at = now + config.absolute_lifetime
    db.add(
        AuthSession(
            id=session_id,
            user_id=user_id,
            created_at=now,
            last_seen_at=now,
            expires_at=expires_at,
        )
    )
    db.flush()
    return CreatedSession(
        cookie_value=_serializer(config).dumps(token),
        session_id=session_id,
        expires_at=expires_at,
    )


def validate_session(
    db: DbSession,
    cookie_value: str,
    config: SessionConfig,
    *,
    now: datetime | None = None,
) -> AuthSession | None:
    """Valida la cookie y devuelve la fila de sesión activa, o ``None``.

    Rechaza (devuelve ``None``) si la firma no valida, si la sesión no existe,
    si fue revocada, si superó el máximo absoluto o si expiró por inactividad.
    Si es válida, refresca ``last_seen_at`` (expiración deslizante).
    """
    now = now or get_utc_now()
    try:
        token = _serializer(config).loads(cookie_value)
    except BadData:
        return None
    if not isinstance(token, str):
        return None

    row = db.get(AuthSession, _hash_token(token))
    if row is None:
        return None
    if row.revoked_at is not None:
        return None
    if now >= row.expires_at:  # máximo absoluto
        return None
    if now - row.last_seen_at > config.idle_timeout:  # inactividad
        return None

    row.last_seen_at = now
    db.flush()
    return row


def revoke_session(
    db: DbSession,
    session_id: str,
    *,
    revoked_by: UUID | None = None,
    now: datetime | None = None,
) -> bool:
    """Revoca una sesión por su ``session_id`` (hash). Idempotente.

    ``revoked_by`` es el Admin que revoca (``None`` en un logout propio).
    Devuelve ``True`` si esta llamada la revocó, ``False`` si no existía o ya
    estaba revocada.
    """
    row = db.get(AuthSession, session_id)
    if row is None or row.revoked_at is not None:
        return False
    row.revoked_at = now or get_utc_now()
    row.revoked_by = revoked_by
    db.flush()
    return True


def revoke_all_sessions(
    db: DbSession,
    user_id: UUID,
    *,
    except_session: str | None = None,
    revoked_by: UUID | None = None,
    now: datetime | None = None,
) -> int:
    """Revoca todas las sesiones activas de ``user_id``.

    ``except_session`` (un ``session_id``) se preserva —p. ej. la sesión que
    origina un cambio de contraseña—. Devuelve cuántas sesiones se revocaron.
    """
    now = now or get_utc_now()
    stmt = select(AuthSession).where(
        AuthSession.user_id == user_id,
        AuthSession.revoked_at.is_(None),
    )
    revoked = 0
    for row in db.execute(stmt).scalars():
        if except_session is not None and row.id == except_session:
            continue
        row.revoked_at = now
        row.revoked_by = revoked_by
        revoked += 1
    db.flush()
    return revoked


def set_session_cookie(
    response: Response,
    cookie_value: str,
    config: SessionConfig,
    *,
    max_age: int | None = None,
) -> None:
    """Fija la cookie de sesión con atributos seguros.

    ``Secure`` (según config), ``HttpOnly`` y ``SameSite=Lax`` (design Decision
    2). Centraliza los atributos para que los endpoints no los repitan.
    """
    if max_age is None:
        max_age = int(config.absolute_lifetime.total_seconds())
    response.set_cookie(
        key=SESSION_COOKIE,
        value=cookie_value,
        max_age=max_age,
        secure=config.cookie_secure,
        httponly=True,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    """Elimina la cookie de sesión del lado del cliente (tras logout)."""
    response.delete_cookie(key=SESSION_COOKIE, path="/")
