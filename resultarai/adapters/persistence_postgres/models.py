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
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
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
