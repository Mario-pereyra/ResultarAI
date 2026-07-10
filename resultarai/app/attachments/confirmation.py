"""Confirmacion auditada de datos de prueba para adjuntos con PII N2 (d14, tarea 5.2).

Cuando el escaneo N2 (`data_scan.scan_for_pii`) detecta PII, el adjunto queda `ready`
pero con `scan_result["requires_test_data_confirmation"] = True`: no es enviable hasta que
el **dueno** confirme "son datos de prueba" (ANEXO §4.4, coherente con la politica §3.3 de
solo-datos-de-prueba hacia la IA). Este modulo es el caso de uso de esa confirmacion:

1. Exige que exista una confirmacion **pendiente** (si no, `NoPendingConfirmationError`):
   un adjunto sin PII, ya confirmado, o bloqueado por N3 no tiene nada que confirmar.
2. Registra la confirmacion en el **audit log append-only** (`log_identity_audit_event`
   -> `identity_audit_events`): quien, cuando, que adjunto y un resumen de los hallazgos
   (tipo -> cantidad, sin el dato en claro).
3. Marca la confirmacion en `scan_result` (`test_data_confirmation` + baja el flag
   `requires_test_data_confirmation`), sin migrar el schema de `b04` (JSONB existente).

**Decision del audit log (documentada):** se usa `identity_audit_events` via
`log_identity_audit_event`, NO la tabla `audit_logs` de `b04`. Razones: (a) es el UNICO
audit append-only que hoy se ESCRIBE en el codigo (mismo trigger `prevent_update_or_delete`
que `audit_logs`); (b) `audit_logs` es Policy-Gate-shaped (agent/skill/tool/effect
obligatorios) y su propio design (d11 Decision 8) establecio que los eventos de gobernanza
que NO son decisiones del Policy Gate no deben rellenar esos campos con valores ficticios —
esta confirmacion es una **atestacion del usuario** (analoga a la aceptacion de un acuerdo,
que `identity_audit_events` ya registra), no una llamada a tool; (c) no requiere migracion.

Cancelar = simplemente no confirmar (el frontend quita el adjunto). El bloqueo del ENVIO de
un adjunto N2 sin confirmar lo hace `data_scan.is_sendable` (que consume la tarea 6.3).
"""

from __future__ import annotations

import datetime

from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.models import Attachment, User, get_utc_now
from resultarai.app.identity import log_identity_audit_event

__all__ = ["NoPendingConfirmationError", "confirm_test_data"]

# Tipo de evento del audit log para la confirmacion de datos de prueba (tarea 5.2).
AUDIT_EVENT_TYPE = "attachment_test_data_confirmed"

_REQUIRES_CONFIRMATION_KEY = "requires_test_data_confirmation"
_CONFIRMATION_KEY = "test_data_confirmation"
_PII_FINDINGS_KEY = "pii_findings"


class NoPendingConfirmationError(Exception):
    """El adjunto no tiene una confirmacion N2 pendiente (sin PII, ya confirmada o N3)."""


def confirm_test_data(
    db: DbSession,
    attachment: Attachment,
    user: User,
    *,
    now: datetime.datetime | None = None,
) -> Attachment:
    """Confirma que el adjunto contiene solo datos de prueba; audita y marca `scan_result`.

    Precondicion: `attachment` tiene `requires_test_data_confirmation=True` (confirmacion
    pendiente). Si no, levanta `NoPendingConfirmationError`. La autorizacion (solo el dueno)
    es del router; aca se asume ya verificada. No hace `db.commit()` (la transaccion es de
    quien inyecta `db`).
    """
    scan_result = dict(attachment.scan_result or {})
    if not scan_result.get(_REQUIRES_CONFIRMATION_KEY, False):
        raise NoPendingConfirmationError

    findings_summary = _summarize_pii(scan_result.get(_PII_FINDINGS_KEY))
    timestamp = now or get_utc_now()

    log_identity_audit_event(
        db,
        event_type=AUDIT_EVENT_TYPE,
        actor_user_id=user.id,
        target_ref=str(attachment.id),
        details={
            "tenant": attachment.tenant,
            "session_id": attachment.session_id,
            "findings_summary": findings_summary,
        },
        now=timestamp,
    )

    # Baja el flag de pendiente y deja el registro de la confirmacion en el propio adjunto.
    # Se reasigna el dict completo (SQLAlchemy no rastrea mutaciones in-place de JSONB).
    scan_result[_REQUIRES_CONFIRMATION_KEY] = False
    scan_result[_CONFIRMATION_KEY] = {
        "confirmed_by": str(user.id),
        "confirmed_at": timestamp.isoformat(),
        "findings_summary": findings_summary,
    }
    attachment.scan_result = scan_result
    db.flush()
    return attachment


def _summarize_pii(pii_findings: object) -> dict[str, int]:
    """Resumen tipo -> cantidad a partir de `scan_result["pii_findings"]` (sin dato en claro)."""
    summary: dict[str, int] = {}
    if isinstance(pii_findings, list):
        for finding in pii_findings:
            if isinstance(finding, dict):
                entity_type = finding.get("entity_type")
                count = finding.get("count")
                if isinstance(entity_type, str) and isinstance(count, int):
                    summary[entity_type] = count
    return summary
