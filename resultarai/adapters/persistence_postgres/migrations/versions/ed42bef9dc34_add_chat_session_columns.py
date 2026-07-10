"""add_chat_session_columns

Revision ID: ed42bef9dc34
Revises: 27343fca18bc
Create Date: 2026-07-09 21:23:07.145031

Migracion additiva de d13-chat-conversacion (tarea 1.1): agrega a `sessions` las
columnas de dueno/agente/titulo/ultima actividad que la API de chat necesita, y a
`messages` el estado del turno y sus metadatos. Las tareas siguientes del change
(1.2-2.5) reutilizan estas mismas columnas -- no se crean mas migraciones despues
de esta para d13.

`title_edited` lleva `server_default=false` solo en el `ADD COLUMN` (no en el modelo
ORM) para que la migracion no falle si `sessions` ya tiene filas: Postgres exige un
default al agregar una columna `NOT NULL` sobre una tabla no vacia. El default de
`False` en el modelo (`models.py`) sigue siendo el que aplica el ORM en cada INSERT
nuevo; el `server_default` de esta migracion es solo el backfill de las filas
existentes en el momento del upgrade.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "ed42bef9dc34"
down_revision: str | Sequence[str] | None = "27343fca18bc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "messages",
        sa.Column("status", sa.String(length=50), nullable=False, server_default="complete"),
    )
    op.add_column(
        "messages",
        sa.Column("turn_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("sessions", sa.Column("owner_user_id", sa.UUID(), nullable=True))
    op.add_column("sessions", sa.Column("agent_id", sa.String(length=255), nullable=True))
    op.add_column("sessions", sa.Column("title", sa.String(length=500), nullable=True))
    op.add_column(
        "sessions",
        sa.Column("title_edited", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("sessions", sa.Column("last_activity_at", sa.DateTime(), nullable=True))
    op.create_foreign_key(
        op.f("fk_sessions_owner_user_id_users"), "sessions", "users", ["owner_user_id"], ["id"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(op.f("fk_sessions_owner_user_id_users"), "sessions", type_="foreignkey")
    op.drop_column("sessions", "last_activity_at")
    op.drop_column("sessions", "title_edited")
    op.drop_column("sessions", "title")
    op.drop_column("sessions", "agent_id")
    op.drop_column("sessions", "owner_user_id")
    op.drop_column("messages", "turn_metadata")
    op.drop_column("messages", "status")
