import datetime
import uuid
from typing import Any

import uuid6
from sqlalchemy import (
    UUID,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.schema import MetaData

# Clean constraints naming convention as specified by the requirements
naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=naming_convention)


def get_utc_now() -> datetime.datetime:
    """Return a naive UTC datetime suitable for DB storage."""
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    metadata = metadata


class Session(Base):
    """Represents a conversation session."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    model_profile: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, default=get_utc_now
    )
    forked_from_id: Mapped[str | None] = mapped_column(
        String(255), ForeignKey("sessions.id"), nullable=True
    )
    state_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    forked_from: Mapped["Session | None"] = relationship("Session", remote_side=[id])
    messages: Mapped[list["Message"]] = relationship("Message", back_populates="session")

    __table_args__ = (UniqueConstraint("id", "model_profile", name="uq_sessions_id_model_profile"),)


class Message(Base):
    """Represents a single message in a conversation session."""

    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid6.uuid7)
    session_id: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id"), nullable=True
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    model_profile: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, default=get_utc_now
    )

    # Relationships
    session: Mapped["Session"] = relationship("Session", back_populates="messages")
    parent: Mapped["Message | None"] = relationship("Message", remote_side=[id])
    compaction_marker: Mapped["CompactionMarker | None"] = relationship(
        "CompactionMarker", back_populates="message"
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["session_id", "model_profile"],
            ["sessions.id", "sessions.model_profile"],
            name="fk_messages_session_id_model_profile_sessions",
        ),
    )


class CompactionMarker(Base):
    """Represents a marker indicating that a message has been compacted."""

    __tablename__ = "compaction_markers"

    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id"), primary_key=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, default=get_utc_now
    )

    # Relationships
    message: Mapped["Message"] = relationship("Message", back_populates="compaction_marker")


class Extraction(Base):
    """Represents a text extraction from a file."""

    __tablename__ = "extractions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid6.uuid7)
    tenant: Mapped[str] = mapped_column(String(255), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    full_text: Mapped[str] = mapped_column(Text, nullable=False)
    extractor_version: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, default=get_utc_now
    )

    __table_args__ = (UniqueConstraint("tenant", "sha256", name="uq_extractions_tenant_sha256"),)


class Attachment(Base):
    """Represents a file attachment."""

    __tablename__ = "attachments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid6.uuid7)
    session_id: Mapped[str | None] = mapped_column(
        String(255), ForeignKey("sessions.id"), nullable=True
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id"), nullable=True
    )
    uploaded_by: Mapped[str] = mapped_column(String(255), nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    declared_mime: Mapped[str] = mapped_column(String(255), nullable=False)
    detected_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_path: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    scan_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    tenant: Mapped[str] = mapped_column(String(255), nullable=False)
    extraction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("extractions.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, default=get_utc_now
    )

    # Relationships
    session: Mapped["Session | None"] = relationship("Session")
    message: Mapped["Message | None"] = relationship("Message")
    extraction: Mapped["Extraction | None"] = relationship("Extraction")

    __table_args__ = (
        CheckConstraint(
            "status IN ('uploaded', 'extracting', 'ready', 'blocked', 'error')",
            name="status",
        ),
    )


class MessageAttachment(Base):
    """Represents a message-attachment association with context information."""

    __tablename__ = "message_attachments"

    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id"), primary_key=True
    )
    attachment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("attachments.id"), primary_key=True
    )
    inserted_text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    truncated: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, default=get_utc_now
    )

    # Relationships
    message: Mapped["Message"] = relationship("Message")
    attachment: Mapped["Attachment"] = relationship("Attachment")


class AuditLog(Base):
    """Represents an audit log entry for security and governance decisions."""

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid6.uuid7)
    user: Mapped[str] = mapped_column(String(255), nullable=False)
    tenant: Mapped[str | None] = mapped_column(String(255), nullable=True)
    agent: Mapped[str] = mapped_column(String(255), nullable=False)
    skill: Mapped[str] = mapped_column(String(255), nullable=False)
    tool: Mapped[str] = mapped_column(String(255), nullable=False)
    operation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    timestamp: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, default=get_utc_now
    )
    environment: Mapped[str] = mapped_column(String(255), nullable=False)
    effect: Mapped[str] = mapped_column(String(50), nullable=False)
    applied_policy: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    corrects: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("audit_logs.id"), nullable=True
    )
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relationships
    corrected_event: Mapped["AuditLog | None"] = relationship("AuditLog", remote_side=[id])


# ---------------------------------------------------------------------------
# Identidad y acceso (d11-identidad-acceso, sección 1)
#
# Nota de diseño: estos modelos declaran únicamente las columnas y constraints
# a nivel de base de datos (que son lo que verifican los contract tests). No se
# definen relaciones ORM a propósito, para evitar configuraciones de mapper
# ambiguas (p. ej. `auth_sessions` tiene dos FKs a `users`: `user_id` y
# `revoked_by`); el adapter de persistencia de identidad, que llega en una
# sección posterior de d11, añadirá las relaciones que necesite.
# ---------------------------------------------------------------------------


class User(Base):
    """Cuenta de usuario local (sin SSO/LDAP; alta exclusiva por Admin)."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid6.uuid7)
    # `username` usa CITEXT para unicidad case-insensitive nativa (no revela
    # existencia por diferencias de mayúsculas). Requiere la extensión citext.
    username: Mapped[str] = mapped_column(CITEXT, nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    # `group_id` deliberadamente NO existe en `users`: la membresía de grupos es
    # una relación muchos-a-muchos cuya única fuente de verdad es `group_members`
    # (evita doble fuente de membresía; ver sección 1.5 del change d11).
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    preferred_language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    preferred_theme: Mapped[str | None] = mapped_column(String(20), nullable=True)
    totp_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, default=get_utc_now
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, default=get_utc_now, onupdate=get_utc_now
    )

    __table_args__ = (
        CheckConstraint("role IN ('admin', 'tecnico', 'funcional')", name="role"),
        CheckConstraint(
            "status IN ('active', 'suspended', 'deactivated')",
            name="status",
        ),
    )


class AuthSession(Base):
    """Sesión de identidad server-side revocable.

    El identificador (`id`) es el hash SHA-256 (hex, 64 chars) del token de
    sesión de alta entropía que viaja firmado en la cookie. Nunca se persiste el
    token en claro: una filtración de la base no expone tokens de sesión usables
    (patrón "tratar el token de sesión como una contraseña" de OWASP). El hash
    rápido es adecuado porque el token ya tiene entropía suficiente.

    Se llama `auth_sessions` (no `sessions`) porque `sessions` ya está tomada por
    las sesiones de conversación de b04.
    """

    __tablename__ = "auth_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, default=get_utc_now
    )
    last_seen_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, default=get_utc_now
    )
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    __table_args__ = (
        Index("ix_auth_sessions_user_id", "user_id"),
        Index("ix_auth_sessions_expires_at", "expires_at"),
    )


class TotpSecret(Base):
    """Secreto TOTP cifrado en reposo (una fila por usuario).

    `encrypted_secret` guarda el ciphertext producido por la capa de aplicación
    con `cryptography.Fernet`; esta capa nunca ve ni almacena el Base32 en claro.
    """

    __tablename__ = "totp_secrets"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True
    )
    encrypted_secret: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    enrolled_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, default=get_utc_now
    )


class TotpBackupCode(Base):
    """Código de respaldo TOTP de un solo uso (hasheado con Argon2id)."""

    __tablename__ = "totp_backup_codes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid6.uuid7)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    used_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, default=get_utc_now
    )

    __table_args__ = (Index("ix_totp_backup_codes_user_id", "user_id"),)


class LoginAttempt(Base):
    """Intento de login fallido, para rate limiting progresivo respaldado en DB.

    `account_ref` es el nombre de usuario normalizado aunque la cuenta no exista,
    para no revelar existencia de cuentas al medir intentos.
    """

    __tablename__ = "login_attempts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid6.uuid7)
    account_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    origin: Mapped[str] = mapped_column(String(255), nullable=False)
    failed_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, default=get_utc_now
    )

    __table_args__ = (Index("ix_login_attempts_account_ref_failed_at", "account_ref", "failed_at"),)


class Group(Base):
    """Grupo/equipo; base jerárquica para las cuotas de d16."""

    __tablename__ = "groups"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid6.uuid7)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, default=get_utc_now
    )


class GroupMember(Base):
    """Membresía usuario-grupo (única fuente de verdad de la pertenencia)."""

    __tablename__ = "group_members"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid6.uuid7)
    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("groups.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    added_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, default=get_utc_now
    )

    __table_args__ = (
        UniqueConstraint("group_id", "user_id", name="uq_group_members_group_id_user_id"),
    )


class UsageAgreementVersion(Base):
    """Versión identificable del texto del acuerdo de uso."""

    __tablename__ = "usage_agreement_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid6.uuid7)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # Número monotónico: ordena versiones y permite comparar "aceptación anterior
    # a la vigente" con una simple comparación numérica.
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    published_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, default=get_utc_now
    )
    published_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )


class UsageAgreementAcceptance(Base):
    """Aceptación de una versión concreta del acuerdo por un usuario."""

    __tablename__ = "usage_agreement_acceptances"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid6.uuid7)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usage_agreement_versions.id"), nullable=False
    )
    accepted_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, default=get_utc_now
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "version_id",
            name="uq_usage_agreement_acceptances_user_id_version_id",
        ),
    )


class IdentityAuditEvent(Base):
    """Auditoría append-only de mutaciones de identidad y aceptaciones de acuerdo.

    Tabla propia (repliegue previsto por el design Decision 8): `audit_logs` de
    b04 es Policy-Gate-shaped (agent/skill/tool/effect obligatorios) y no admite
    eventos de identidad sin campos ficticios. Mismo mecanismo append-only que
    `audit_logs`: trigger `prevent_update_or_delete()` (sin UPDATE ni DELETE).
    `details` nunca contiene secretos (contraseñas, secretos TOTP, tokens).
    """

    __tablename__ = "identity_audit_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid6.uuid7)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    target_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timestamp: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, default=get_utc_now
    )
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class Notification(Base):
    """Notificación dirigida a un usuario concreto (d12)."""

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid6.uuid7)
    recipient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    deep_link: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    read_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, default=get_utc_now
    )

    __table_args__ = (
        Index("ix_notifications_recipient_created", "recipient_id", "created_at"),
        Index("ix_notifications_recipient_read", "recipient_id", "read_at"),
    )

