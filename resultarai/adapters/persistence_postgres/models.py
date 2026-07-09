import datetime
import uuid

import uuid6
from sqlalchemy import (
    UUID,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    Text,
    UniqueConstraint,
)
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
