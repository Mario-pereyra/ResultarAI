"""Tests de sesiones server-side firmadas (d11, tarea 2.2).

Casos: sesión válida, expirada por inactividad, expirada por máximo absoluto,
revocada y firma corrupta. Todas menos la válida deben rechazarse (devolver
``None``).
"""

from __future__ import annotations

from datetime import timedelta

from resultarai.adapters.persistence_postgres.connection import get_db_session
from resultarai.adapters.persistence_postgres.models import AuthSession, get_utc_now
from resultarai.app.identity.sessions import (
    SessionConfig,
    create_session,
    revoke_all_sessions,
    revoke_session,
    validate_session,
)
from tests.app.identity.conftest import make_user

_CONFIG = SessionConfig(
    signing_key="sessions-test-signing-key",
    idle_timeout=timedelta(minutes=30),
    absolute_lifetime=timedelta(hours=8),
)


def test_valid_session_validates_and_slides_last_seen() -> None:
    """Una sesión válida resuelve el usuario y refresca ``last_seen_at``."""
    user_id = make_user("sess-valid")
    t0 = get_utc_now()

    with get_db_session() as db:
        created = create_session(db, user_id, _CONFIG, now=t0)

    validate_at = t0 + timedelta(minutes=5)
    with get_db_session() as db:
        row = validate_session(db, created.cookie_value, _CONFIG, now=validate_at)
        assert row is not None
        assert row.user_id == user_id
        assert row.last_seen_at == validate_at  # expiración deslizante


def test_session_expired_by_inactivity_is_rejected() -> None:
    """Superado el idle_timeout desde last_seen_at, la sesión se rechaza."""
    user_id = make_user("sess-idle")
    t0 = get_utc_now()
    with get_db_session() as db:
        created = create_session(db, user_id, _CONFIG, now=t0)

    # 31 min sin actividad > idle_timeout (30 min); aún dentro del máximo absoluto.
    validate_at = t0 + timedelta(minutes=31)
    with get_db_session() as db:
        assert validate_session(db, created.cookie_value, _CONFIG, now=validate_at) is None


def test_session_expired_by_absolute_lifetime_is_rejected() -> None:
    """Superado el máximo absoluto se rechaza aunque haya actividad reciente."""
    user_id = make_user("sess-absolute")
    t0 = get_utc_now()
    with get_db_session() as db:
        created = create_session(db, user_id, _CONFIG, now=t0)

    validate_at = t0 + _CONFIG.absolute_lifetime + timedelta(minutes=1)
    # last_seen_at reciente: así el rechazo se debe al máximo absoluto, no al idle.
    with get_db_session() as db:
        row = db.get(AuthSession, created.session_id)
        assert row is not None
        row.last_seen_at = validate_at - timedelta(minutes=1)

    with get_db_session() as db:
        assert validate_session(db, created.cookie_value, _CONFIG, now=validate_at) is None


def test_revoked_session_is_rejected() -> None:
    """Una sesión revocada se rechaza en la siguiente validación."""
    user_id = make_user("sess-revoked")
    admin_id = make_user("sess-admin", role="admin")
    t0 = get_utc_now()
    with get_db_session() as db:
        created = create_session(db, user_id, _CONFIG, now=t0)

    with get_db_session() as db:
        assert revoke_session(db, created.session_id, revoked_by=admin_id) is True

    with get_db_session() as db:
        assert validate_session(db, created.cookie_value, _CONFIG, now=t0) is None
    # Revocar de nuevo es idempotente (ya revocada -> False).
    with get_db_session() as db:
        assert revoke_session(db, created.session_id) is False


def test_corrupt_signature_is_rejected() -> None:
    """Un valor de cookie con firma manipulada se rechaza."""
    user_id = make_user("sess-corrupt")
    t0 = get_utc_now()
    with get_db_session() as db:
        created = create_session(db, user_id, _CONFIG, now=t0)

    last = created.cookie_value[-1]
    tampered = created.cookie_value[:-1] + ("A" if last != "A" else "B")
    with get_db_session() as db:
        assert validate_session(db, tampered, _CONFIG, now=t0) is None


def test_revoke_all_sessions_keeps_exception() -> None:
    """``revoke_all_sessions`` revoca todas menos la exceptuada."""
    user_id = make_user("sess-multi")
    t0 = get_utc_now()
    with get_db_session() as db:
        keep = create_session(db, user_id, _CONFIG, now=t0)
        drop = create_session(db, user_id, _CONFIG, now=t0)

    with get_db_session() as db:
        revoked = revoke_all_sessions(db, user_id, except_session=keep.session_id)
        assert revoked == 1

    with get_db_session() as db:
        assert validate_session(db, keep.cookie_value, _CONFIG, now=t0) is not None
        assert validate_session(db, drop.cookie_value, _CONFIG, now=t0) is None
