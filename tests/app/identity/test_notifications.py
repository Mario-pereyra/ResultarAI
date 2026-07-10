"""Tests for notification registry and emission (d12, Section 2)."""

from __future__ import annotations

import pytest

from resultarai.adapters.persistence_postgres.connection import get_db_session
from resultarai.app.use_cases.notifications.emit import emit_notification
from resultarai.app.use_cases.notifications.types import NOTIFICATION_TYPES
from tests.app.identity.conftest import make_user


def test_notification_types_registry_status() -> None:
    """Valida los tipos declarados, su flag implemented y schemas."""
    expected_types = {
        "quota_release_requested": True,
        "quota_release_resolved": True,
        "hitl_approval_pending": False,
        "hitl_card_expired": False,
        "workflow_finished": False,
        "catalog_news": False,
    }

    for type_name, expected_implemented in expected_types.items():
        assert type_name in NOTIFICATION_TYPES
        assert NOTIFICATION_TYPES[type_name].implemented == expected_implemented
        assert NOTIFICATION_TYPES[type_name].payload_schema is not None


def test_emit_notification_success() -> None:
    """Emisión desde un caso de uso externo a un destinatario válido."""
    user_id = make_user("recipient-user", role="admin")

    with get_db_session() as db:
        notif = emit_notification(
            db=db,
            notification_type="quota_release_requested",
            recipient_id=user_id,
            payload={
                "requestor_username": "other-user",
                "quota_name": "API calls",
                "current_consumption": 105.5,
            },
            deep_link="/admin/quotas",
        )
        db.commit()

        assert notif.id is not None
        assert notif.type == "quota_release_requested"
        assert notif.payload["requestor_username"] == "other-user"
        assert notif.deep_link == "/admin/quotas"


def test_emit_notification_rejected_unregistered() -> None:
    """Emisión rechazada para un tipo no registrado."""
    user_id = make_user("notif-unreg")

    with (
        get_db_session() as db,
        pytest.raises(ValueError, match="Tipo de notificación no registrado"),
    ):
        emit_notification(
            db=db,
            notification_type="unknown_type",
            recipient_id=user_id,
            payload={},
        )


def test_emit_notification_rejected_role_validation() -> None:
    """Emisión rechazada si el destinatario no cumple el rol esperado."""
    user_id = make_user("non-admin-user", role="tecnico")

    with (
        get_db_session() as db,
        pytest.raises(ValueError, match="no cumple con los requisitos del rol"),
    ):
        emit_notification(
            db=db,
            notification_type="quota_release_requested",
            recipient_id=user_id,
            payload={
                "requestor_username": "other-user",
                "quota_name": "API calls",
                "current_consumption": 105.5,
            },
        )
