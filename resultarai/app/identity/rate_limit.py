"""Rate limiting progresivo de login respaldado en Postgres (d11, tarea 2.4).

Cuenta intentos fallidos por cuenta en una ventana deslizante contra la tabla
``login_attempts`` (design Decision 4: consistente entre réplicas, sin memoria de
proceso ni Redis). El ``account_ref`` se normaliza (minúsculas, sin espacios)
antes de registrar y consultar, y se registra aunque la cuenta no exista, para
no revelar existencia de cuentas midiendo intentos.

El bloqueo se **libera solo por tiempo**: al avanzar el reloj, los intentos
viejos salen de la ventana y el conteo baja del umbral. El Admin (o un login
exitoso) puede liberar antes con :func:`clear_attempts`.

Variables de entorno (leídas por :meth:`RateLimitConfig.from_env`):

- ``IDENTITY_LOGIN_MAX_ATTEMPTS``: umbral de intentos por ventana (default 5).
- ``IDENTITY_LOGIN_WINDOW_SECONDS``: ventana en segundos (default 900 = 15 min).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, cast

from sqlalchemy import CursorResult, delete, func, select
from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.models import LoginAttempt, get_utc_now

__all__ = [
    "ACCOUNT_LOCKED",
    "LockStatus",
    "RateLimitConfig",
    "account_lock_status",
    "clear_attempts",
    "count_recent_attempts",
    "is_account_locked",
    "normalize_account_ref",
    "record_failed_attempt",
]

# Código de estado que devuelve la API cuando la cuenta está bloqueada
# (spec authentication: "responde con el código ACCOUNT_LOCKED").
ACCOUNT_LOCKED = "ACCOUNT_LOCKED"


@dataclass(frozen=True)
class RateLimitConfig:
    """Umbral y ventana del bloqueo progresivo, configurables por instancia."""

    max_attempts: int = 5
    window: timedelta = timedelta(minutes=15)

    @classmethod
    def from_env(cls) -> RateLimitConfig:
        """Construye la configuración desde variables de entorno."""
        max_attempts = os.environ.get("IDENTITY_LOGIN_MAX_ATTEMPTS")
        window_seconds = os.environ.get("IDENTITY_LOGIN_WINDOW_SECONDS")
        return cls(
            max_attempts=int(max_attempts) if max_attempts else 5,
            window=timedelta(seconds=int(window_seconds) if window_seconds else 900),
        )


@dataclass(frozen=True)
class LockStatus:
    """Estado de bloqueo de una cuenta en un instante dado."""

    locked: bool
    recent_attempts: int
    # Instante en que la cuenta vuelve a aceptar intentos (``None`` si no está
    # bloqueada): el intento más antiguo de la ventana más la duración de esta.
    locked_until: datetime | None


def normalize_account_ref(account_ref: str) -> str:
    """Normaliza el identificador de cuenta (minúsculas, sin espacios extremos)."""
    return account_ref.strip().lower()


def record_failed_attempt(
    db: DbSession,
    account_ref: str,
    origin: str,
    *,
    now: datetime | None = None,
) -> None:
    """Registra un intento de login fallido para ``account_ref``.

    Se registra con el ``account_ref`` normalizado aunque la cuenta no exista.
    ``now`` permite inyectar el instante (tests que "viajan en el tiempo").
    """
    db.add(
        LoginAttempt(
            account_ref=normalize_account_ref(account_ref),
            origin=origin,
            failed_at=now or get_utc_now(),
        )
    )
    db.flush()


def count_recent_attempts(
    db: DbSession,
    account_ref: str,
    config: RateLimitConfig,
    *,
    now: datetime | None = None,
) -> int:
    """Cuenta los intentos fallidos de ``account_ref`` dentro de la ventana."""
    now = now or get_utc_now()
    window_start = now - config.window
    stmt = (
        select(func.count())
        .select_from(LoginAttempt)
        .where(
            LoginAttempt.account_ref == normalize_account_ref(account_ref),
            LoginAttempt.failed_at >= window_start,
        )
    )
    return int(db.execute(stmt).scalar_one())


def is_account_locked(
    db: DbSession,
    account_ref: str,
    config: RateLimitConfig,
    *,
    now: datetime | None = None,
) -> bool:
    """Indica si ``account_ref`` está bloqueada (intentos en ventana ≥ umbral)."""
    return count_recent_attempts(db, account_ref, config, now=now) >= config.max_attempts


def account_lock_status(
    db: DbSession,
    account_ref: str,
    config: RateLimitConfig,
    *,
    now: datetime | None = None,
) -> LockStatus:
    """Devuelve el estado de bloqueo detallado de ``account_ref``.

    Cuando está bloqueada, ``locked_until`` es el instante en que el intento más
    antiguo dentro de la ventana sale de ella (momento en que el conteo baja del
    umbral, salvo nuevos fallos).
    """
    now = now or get_utc_now()
    normalized = normalize_account_ref(account_ref)
    window_start = now - config.window
    count = int(
        db.execute(
            select(func.count())
            .select_from(LoginAttempt)
            .where(
                LoginAttempt.account_ref == normalized,
                LoginAttempt.failed_at >= window_start,
            )
        ).scalar_one()
    )

    if count < config.max_attempts:
        return LockStatus(locked=False, recent_attempts=count, locked_until=None)

    oldest_in_window = db.execute(
        select(func.min(LoginAttempt.failed_at)).where(
            LoginAttempt.account_ref == normalized,
            LoginAttempt.failed_at >= window_start,
        )
    ).scalar_one()
    locked_until = oldest_in_window + config.window if oldest_in_window else None
    return LockStatus(locked=True, recent_attempts=count, locked_until=locked_until)


def clear_attempts(db: DbSession, account_ref: str) -> int:
    """Borra los intentos fallidos de ``account_ref`` (desbloqueo inmediato).

    Se invoca tras un login exitoso o cuando el Admin desbloquea la cuenta.
    Devuelve cuántos registros se eliminaron.
    """
    result = cast(
        CursorResult[Any],
        db.execute(
            delete(LoginAttempt).where(
                LoginAttempt.account_ref == normalize_account_ref(account_ref)
            )
        ),
    )
    db.flush()
    return result.rowcount
