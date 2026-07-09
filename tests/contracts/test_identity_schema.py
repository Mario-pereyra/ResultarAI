"""Contract tests del esquema de identidad y acceso (d11, sección 1).

Verifican, contra el Postgres de Docker, que la migración
``724789ea8df4_create_identity_schema`` aplica limpio, que las tablas son
consultables, que los constraints (CHECK de role/status, unicidad de membresía y
de aceptaciones, unicidad case-insensitive de username) funcionan, que el índice
de ``auth_sessions`` por ``user_id`` es usable, que ``identity_audit_events`` es
append-only, y que la cadena de migración hace roundtrip downgrade/upgrade.
"""

import datetime
import pathlib
import uuid
from collections.abc import Generator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from resultarai.adapters.persistence_postgres.connection import get_db_session
from resultarai.adapters.persistence_postgres.models import (
    AuthSession,
    Group,
    GroupMember,
    IdentityAuditEvent,
    LoginAttempt,
    TotpBackupCode,
    TotpSecret,
    UsageAgreementAcceptance,
    UsageAgreementVersion,
    User,
)

# Revisión inmediatamente anterior a la del esquema de identidad (b04 head).
_DOWN_REVISION = "ddacc8ae120e"

_IDENTITY_TABLES = (
    "users",
    "auth_sessions",
    "totp_secrets",
    "totp_backup_codes",
    "login_attempts",
    "groups",
    "group_members",
    "usage_agreement_versions",
    "usage_agreement_acceptances",
    "identity_audit_events",
)


@pytest.fixture(autouse=True)
def cleanup_identity() -> Generator[None, None, None]:
    """Vacía las tablas de identidad antes y después de cada test.

    TRUNCATE no dispara los triggers BEFORE UPDATE/DELETE por fila, por lo que
    también limpia ``identity_audit_events`` (append-only), igual que hace el
    cleanup de b04 con ``audit_logs``.
    """
    statement = text("TRUNCATE TABLE " + ", ".join(_IDENTITY_TABLES) + " CASCADE")
    with get_db_session() as session:
        session.execute(statement)
        session.commit()

    yield

    with get_db_session() as session:
        session.execute(statement)
        session.commit()


def _make_user(
    username: str,
    *,
    role: str = "funcional",
    status: str = "active",
) -> str:
    """Crea un usuario mínimo válido y devuelve su id como string."""
    with get_db_session() as session:
        user = User(
            username=username,
            display_name=username.title(),
            role=role,
            password_hash="$argon2id$fake-hash-for-tests",
            status=status,
        )
        session.add(user)
        session.flush()
        return str(user.id)


def test_all_identity_tables_present() -> None:
    """Las 10 tablas de identidad existen y son consultables."""
    with get_db_session() as session:
        for table in _IDENTITY_TABLES:
            regclass = session.execute(
                text("SELECT to_regclass(:name)"), {"name": f"public.{table}"}
            ).scalar()
            assert regclass is not None, f"falta la tabla {table}"


def test_user_persist_and_defaults() -> None:
    """Un usuario nuevo persiste con los defaults esperados."""
    with get_db_session() as session:
        user = User(
            username="Lucia",
            display_name="Lucía",
            role="admin",
            password_hash="$argon2id$fake",
            status="active",
        )
        session.add(user)
        session.flush()
        user_id = user.id

    with get_db_session() as session:
        loaded = session.get(User, user_id)
        assert loaded is not None
        assert loaded.username == "Lucia"
        assert loaded.role == "admin"
        assert loaded.status == "active"
        assert loaded.email is None
        assert loaded.preferred_language is None
        assert loaded.preferred_theme is None
        assert loaded.must_change_password is False
        assert loaded.totp_required is False
        assert loaded.created_at is not None
        assert loaded.updated_at is not None


def test_user_role_check_constraint() -> None:
    """Un rol fuera de {admin, tecnico, funcional} es rechazado."""

    def insert_bad_role() -> None:
        with get_db_session() as session:
            session.add(
                User(
                    username="badrole",
                    display_name="Bad Role",
                    role="superuser",
                    password_hash="$argon2id$fake",
                    status="active",
                )
            )

    with pytest.raises(IntegrityError) as exc_info:
        insert_bad_role()
    assert (
        "ck_users_role" in str(exc_info.value) or "check constraint" in str(exc_info.value).lower()
    )


def test_user_status_check_constraint() -> None:
    """Un status fuera de {active, suspended, deactivated} es rechazado."""

    def insert_bad_status() -> None:
        with get_db_session() as session:
            session.add(
                User(
                    username="badstatus",
                    display_name="Bad Status",
                    role="funcional",
                    password_hash="$argon2id$fake",
                    status="zombie",
                )
            )

    with pytest.raises(IntegrityError) as exc_info:
        insert_bad_status()
    assert (
        "ck_users_status" in str(exc_info.value)
        or "check constraint" in str(exc_info.value).lower()
    )


def test_username_unique_case_insensitive() -> None:
    """El username es único sin distinguir mayúsculas (CITEXT)."""
    _make_user("Lucia")

    def insert_same_username_other_case() -> None:
        with get_db_session() as session:
            session.add(
                User(
                    username="lucia",
                    display_name="Otra Lucia",
                    role="funcional",
                    password_hash="$argon2id$fake",
                    status="active",
                )
            )

    with pytest.raises(IntegrityError) as exc_info:
        insert_same_username_other_case()
    assert "uq_users_username" in str(exc_info.value)


def test_group_membership_unique() -> None:
    """Una membresía (group_id, user_id) no puede duplicarse."""
    user_id = _make_user("miembro")

    with get_db_session() as session:
        group = Group(name="Equipo Contabilidad")
        session.add(group)
        session.flush()
        group_id = group.id

        session.add(GroupMember(group_id=group_id, user_id=user_id))

    def insert_duplicate_membership() -> None:
        with get_db_session() as session:
            session.add(GroupMember(group_id=group_id, user_id=user_id))

    with pytest.raises(IntegrityError) as exc_info:
        insert_duplicate_membership()
    assert "uq_group_members_group_id_user_id" in str(exc_info.value)


def test_group_name_unique() -> None:
    """El nombre de grupo es único."""
    with get_db_session() as session:
        session.add(Group(name="Ventas"))

    def insert_duplicate_group() -> None:
        with get_db_session() as session:
            session.add(Group(name="Ventas"))

    with pytest.raises(IntegrityError) as exc_info:
        insert_duplicate_group()
    assert "uq_groups_name" in str(exc_info.value)


def test_auth_session_persist_and_revoke() -> None:
    """Una sesión de identidad persiste y admite marcarse como revocada."""
    user_id = _make_user("sessionuser")
    admin_id = _make_user("adminrevoker", role="admin")

    now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
    session_hash = "a" * 64  # SHA-256 hex simulado del token de sesión

    with get_db_session() as session:
        auth = AuthSession(
            id=session_hash,
            user_id=user_id,
            expires_at=now + datetime.timedelta(hours=8),
        )
        session.add(auth)

    with get_db_session() as session:
        loaded = session.get(AuthSession, session_hash)
        assert loaded is not None
        assert str(loaded.user_id) == user_id
        assert loaded.revoked_at is None
        assert loaded.revoked_by is None
        assert loaded.created_at is not None
        assert loaded.last_seen_at is not None

    # Revocar (el auth_sessions es mutable, a diferencia de las tablas de audit).
    with get_db_session() as session:
        loaded = session.get(AuthSession, session_hash)
        assert loaded is not None
        loaded.revoked_at = now
        loaded.revoked_by = uuid.UUID(admin_id)

    with get_db_session() as session:
        loaded = session.get(AuthSession, session_hash)
        assert loaded is not None
        assert loaded.revoked_at is not None
        assert str(loaded.revoked_by) == admin_id


def test_auth_sessions_user_id_index_used() -> None:
    """La consulta por ``user_id`` usa el índice ``ix_auth_sessions_user_id``."""
    user_id = _make_user("indexuser")
    now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
    with get_db_session() as session:
        session.add(
            AuthSession(
                id="b" * 64,
                user_id=user_id,
                expires_at=now + datetime.timedelta(hours=8),
            )
        )

    with get_db_session() as session:
        # Deshabilitar seqscan fuerza al planner a usar el índice si existe uno
        # aplicable, lo que prueba que el índice está presente y es utilizable.
        session.execute(text("SET LOCAL enable_seqscan = off"))
        rows = session.execute(
            text("EXPLAIN SELECT id FROM auth_sessions WHERE user_id = :uid"),
            {"uid": user_id},
        ).fetchall()
        plan = "\n".join(str(row[0]) for row in rows)
        assert "ix_auth_sessions_user_id" in plan, plan


def test_usage_agreement_acceptance_unique() -> None:
    """Una aceptación (user_id, version_id) no puede duplicarse."""
    admin_id = _make_user("publisher", role="admin")
    user_id = _make_user("accepter")

    with get_db_session() as session:
        version = UsageAgreementVersion(
            text="Acuerdo de uso v1",
            version_number=1,
            published_by=admin_id,
        )
        session.add(version)
        session.flush()
        version_id = version.id

        session.add(UsageAgreementAcceptance(user_id=user_id, version_id=version_id))

    def insert_duplicate_acceptance() -> None:
        with get_db_session() as session:
            session.add(UsageAgreementAcceptance(user_id=user_id, version_id=version_id))

    with pytest.raises(IntegrityError) as exc_info:
        insert_duplicate_acceptance()
    assert "uq_usage_agreement_acceptances_user_id_version_id" in str(exc_info.value)


def test_usage_agreement_version_number_unique() -> None:
    """El número monotónico de versión del acuerdo es único."""
    admin_id = _make_user("publisher2", role="admin")

    with get_db_session() as session:
        session.add(UsageAgreementVersion(text="v1", version_number=1, published_by=admin_id))

    def insert_duplicate_version_number() -> None:
        with get_db_session() as session:
            session.add(
                UsageAgreementVersion(text="v1-bis", version_number=1, published_by=admin_id)
            )

    with pytest.raises(IntegrityError) as exc_info:
        insert_duplicate_version_number()
    assert "uq_usage_agreement_versions_version_number" in str(exc_info.value)


def test_totp_secret_and_backup_codes_persist() -> None:
    """El secreto TOTP cifrado y los códigos de respaldo persisten."""
    user_id = _make_user("totpuser")
    secret = b"gAAAAABfake-fernet-ciphertext-bytes"

    with get_db_session() as session:
        session.add(TotpSecret(user_id=user_id, encrypted_secret=secret))
        session.add(TotpBackupCode(user_id=user_id, code_hash="$argon2id$fake-backup"))

    with get_db_session() as session:
        loaded_secret = session.get(TotpSecret, user_id)
        assert loaded_secret is not None
        assert bytes(loaded_secret.encrypted_secret) == secret
        assert loaded_secret.enrolled_at is not None

        codes = session.query(TotpBackupCode).filter_by(user_id=user_id).all()
        assert len(codes) == 1
        assert codes[0].used_at is None
        assert codes[0].code_hash == "$argon2id$fake-backup"


def test_login_attempt_persist_without_existing_account() -> None:
    """Un intento fallido se registra con account_ref aunque la cuenta no exista."""
    with get_db_session() as session:
        session.add(LoginAttempt(account_ref="cuenta-inexistente", origin="203.0.113.7"))

    with get_db_session() as session:
        attempts = session.query(LoginAttempt).filter_by(account_ref="cuenta-inexistente").all()
        assert len(attempts) == 1
        assert attempts[0].origin == "203.0.113.7"
        assert attempts[0].failed_at is not None


def test_identity_audit_event_persist() -> None:
    """Un evento de auditoría de identidad persiste con details en JSONB."""
    admin_id = _make_user("auditor", role="admin")
    target_id = _make_user("target")
    details = {"assigned_role": "tecnico", "note": "alta desde consola"}

    with get_db_session() as session:
        event = IdentityAuditEvent(
            event_type="user.created",
            actor_user_id=admin_id,
            target_ref=target_id,
            details=details,
        )
        session.add(event)
        session.flush()
        event_id = event.id

    with get_db_session() as session:
        loaded = session.get(IdentityAuditEvent, event_id)
        assert loaded is not None
        assert loaded.event_type == "user.created"
        assert str(loaded.actor_user_id) == admin_id
        assert loaded.target_ref == target_id
        assert loaded.details == details
        assert loaded.timestamp is not None


def test_identity_audit_event_append_only() -> None:
    """UPDATE y DELETE sobre identity_audit_events fallan (append-only)."""
    admin_id = _make_user("auditor2", role="admin")

    with get_db_session() as session:
        event = IdentityAuditEvent(event_type="group.member_added", actor_user_id=admin_id)
        session.add(event)
        session.flush()
        event_id = event.id

    def try_update() -> None:
        with get_db_session() as session:
            loaded = session.get(IdentityAuditEvent, event_id)
            assert loaded is not None
            loaded.event_type = "modified"

    with pytest.raises(DBAPIError) as exc_info:
        try_update()
    assert "prevent_update_or_delete" in str(exc_info.value) or "append-only" in str(exc_info.value)

    def try_delete() -> None:
        with get_db_session() as session:
            loaded = session.get(IdentityAuditEvent, event_id)
            assert loaded is not None
            session.delete(loaded)

    with pytest.raises(DBAPIError) as exc_info:
        try_delete()
    assert "prevent_update_or_delete" in str(exc_info.value) or "append-only" in str(exc_info.value)


def _alembic_config() -> Config:
    """Config de Alembic apuntando al alembic.ini de la raíz del repo."""
    repo_root = pathlib.Path(__file__).resolve().parents[2]
    return Config(str(repo_root / "alembic.ini"))


def test_migration_downgrade_upgrade_roundtrip() -> None:
    """La migración de identidad hace roundtrip downgrade -> upgrade limpio."""
    config = _alembic_config()
    try:
        command.downgrade(config, _DOWN_REVISION)
        with get_db_session() as session:
            for table in _IDENTITY_TABLES:
                regclass = session.execute(
                    text("SELECT to_regclass(:name)"), {"name": f"public.{table}"}
                ).scalar()
                assert regclass is None, f"la tabla {table} debería haberse eliminado"

        command.upgrade(config, "head")
        with get_db_session() as session:
            for table in _IDENTITY_TABLES:
                regclass = session.execute(
                    text("SELECT to_regclass(:name)"), {"name": f"public.{table}"}
                ).scalar()
                assert regclass is not None, f"la tabla {table} debería haberse recreado"
    finally:
        # Garantiza que la base queda en head para el resto de la suite.
        command.upgrade(config, "head")
