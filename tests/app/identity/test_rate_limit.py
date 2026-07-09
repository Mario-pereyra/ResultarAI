"""Tests de rate limiting progresivo de login (d11, tarea 2.4).

Se "viaja en el tiempo" inyectando timestamps (``now``/``failed_at``), sin
``sleep``.
"""

from __future__ import annotations

from datetime import timedelta

from resultarai.adapters.persistence_postgres.connection import get_db_session
from resultarai.adapters.persistence_postgres.models import get_utc_now
from resultarai.app.identity.rate_limit import (
    RateLimitConfig,
    account_lock_status,
    clear_attempts,
    count_recent_attempts,
    is_account_locked,
    record_failed_attempt,
)

_CONFIG = RateLimitConfig(max_attempts=5, window=timedelta(minutes=15))
_ORIGIN = "203.0.113.7"


def test_consecutive_failures_lock_account() -> None:
    """Alcanzado el umbral de fallos, la cuenta queda bloqueada."""
    account = "lockme"
    t0 = get_utc_now()
    with get_db_session() as db:
        for _ in range(_CONFIG.max_attempts - 1):
            record_failed_attempt(db, account, _ORIGIN, now=t0)
        assert is_account_locked(db, account, _CONFIG, now=t0) is False
        record_failed_attempt(db, account, _ORIGIN, now=t0)
        assert is_account_locked(db, account, _CONFIG, now=t0) is True


def test_lock_releases_after_window() -> None:
    """Pasada la ventana, los intentos viejos salen y la cuenta se desbloquea."""
    account = "release"
    t0 = get_utc_now()
    with get_db_session() as db:
        for _ in range(_CONFIG.max_attempts):
            record_failed_attempt(db, account, _ORIGIN, now=t0)
        assert is_account_locked(db, account, _CONFIG, now=t0) is True

    later = t0 + _CONFIG.window + timedelta(minutes=1)
    with get_db_session() as db:
        assert is_account_locked(db, account, _CONFIG, now=later) is False


def test_clear_attempts_unlocks() -> None:
    """``clear_attempts`` libera la cuenta de inmediato."""
    account = "cleared"
    t0 = get_utc_now()
    with get_db_session() as db:
        for _ in range(_CONFIG.max_attempts):
            record_failed_attempt(db, account, _ORIGIN, now=t0)
        assert is_account_locked(db, account, _CONFIG, now=t0) is True
        removed = clear_attempts(db, account)
        assert removed == _CONFIG.max_attempts
        assert is_account_locked(db, account, _CONFIG, now=t0) is False


def test_account_ref_is_normalized() -> None:
    """El account_ref se normaliza al registrar y al consultar."""
    t0 = get_utc_now()
    with get_db_session() as db:
        record_failed_attempt(db, "  Lucia  ", _ORIGIN, now=t0)
        # Distinta caja y espacios: cuenta el mismo intento.
        assert count_recent_attempts(db, "LUCIA", _CONFIG, now=t0) == 1


def test_account_lock_status_reports_locked_until() -> None:
    """El estado detallado informa el instante de liberación."""
    account = "status"
    t0 = get_utc_now()
    with get_db_session() as db:
        for _ in range(_CONFIG.max_attempts):
            record_failed_attempt(db, account, _ORIGIN, now=t0)
        status = account_lock_status(db, account, _CONFIG, now=t0)
        assert status.locked is True
        assert status.recent_attempts == _CONFIG.max_attempts
        assert status.locked_until == t0 + _CONFIG.window
