"""Tests del escaneo de niveles de datos N2/N3 (d14, tareas 5.1-5.3 — ANEXO §4.4).

Dos capas de tests:

- **Unidad** (funciones puras `scan_for_secrets`/`scan_for_pii`/`is_sendable`): patrones N3
  (password/JWT/private key/URI/clave API), redaccion sin dato en claro, patrones extra de
  config, PII N2 con Presidio + reconocedores BO, y las reglas de sendabilidad.
- **Pipeline** (via `extract_attachment` con extractor fake, patron de `test_extraction.py`):
  secreto -> `blocked` con linea + fragmento redactado en `scan_result`; PII -> `ready` con
  `pii_findings` + `requires_test_data_confirmation` (no enviable); N3 gana sobre N2; texto
  limpio -> sin hallazgos y enviable.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.connection import get_db_session
from resultarai.adapters.persistence_postgres.models import Attachment
from resultarai.app.attachments import AttachmentsConfig, extract_attachment
from resultarai.app.attachments.data_scan import (
    is_sendable,
    scan_for_pii,
    scan_for_secrets,
)
from resultarai.core.ports.extraction import AttachmentKind, ExtractionInput
from tests.app.attachments.fakes import fake_extract_passthrough

_MIB = 1024 * 1024
_MEMORY_LIMIT = 384 * _MIB


def _config(tmp_path: Path, *, extra_secret_patterns: tuple[str, ...] = ()) -> AttachmentsConfig:
    return AttachmentsConfig(
        storage_dir=tmp_path / "attachments",
        tenant="test-tenant",
        extraction_timeout_seconds=10.0,
        extraction_memory_limit_bytes=_MEMORY_LIMIT,
        extra_secret_patterns=extra_secret_patterns,
    )


def _make_uploaded_attachment(db: DbSession, *, name: str, detected_type: str) -> Attachment:
    attachment = Attachment(
        session_id=None,
        message_id=None,
        uploaded_by="tester",
        original_name=name,
        declared_mime="text/plain",
        detected_type=detected_type,
        size_bytes=10,
        sha256=uuid.uuid4().hex + uuid.uuid4().hex,  # 64 hex chars
        storage_path=None,
        scan_result=None,
        status="uploaded",
        tenant="test-tenant",
    )
    db.add(attachment)
    db.flush()
    return attachment


def _passthrough_source(name: str, text: str) -> ExtractionInput:
    return ExtractionInput(kind=AttachmentKind.TEXT, filename=name, content=text.encode("utf-8"))


# ---------------------------------------------------------------------------------------
# N3 — secretos (unidad, tarea 5.1)
# ---------------------------------------------------------------------------------------


def test_n3_connection_password_redacted_with_line() -> None:
    """`Password=valor` se detecta con su linea y se redacta (nunca el secreto en claro)."""
    text = "\n".join([f"linea {i}" for i in range(1, 23)] + ['conn: "Password=hunter2;"']) + "\n"
    findings = scan_for_secrets(text)

    assert [f.secret_type for f in findings] == ["connection_password"]
    assert findings[0].line == 23
    assert findings[0].redacted == "Password=***"
    assert "hunter2" not in findings[0].redacted


def test_n3_jwt_and_private_key_detected() -> None:
    """Un JWT y una private key PEM se detectan y se guardan redactados."""
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0In0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    pk = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKC...\n-----END RSA PRIVATE KEY-----"

    jwt_findings = scan_for_secrets(f"auth token = {jwt}")
    assert [f.secret_type for f in jwt_findings] == ["jwt"]
    assert jwt_findings[0].redacted == "eyJ***"
    assert "SflKxw" not in jwt_findings[0].redacted

    pk_findings = scan_for_secrets(pk)
    assert [f.secret_type for f in pk_findings] == ["private_key"]
    assert pk_findings[0].redacted == "-----BEGIN RSA PRIVATE KEY-----"


def test_n3_connection_uri_masks_only_password() -> None:
    """Una URI `esquema://user:pass@host` enmascara solo la contrasena."""
    findings = scan_for_secrets("url = postgres://admin:s3cr3t@10.0.0.5:5432/prod")
    assert [f.secret_type for f in findings] == ["connection_uri"]
    assert findings[0].redacted == "postgres://admin:***@10.0.0.5:5432"
    assert "s3cr3t" not in findings[0].redacted


def test_n3_api_key_prefixes_detected() -> None:
    """Las claves API de proveedores conocidos se detectan por prefijo, redactadas."""
    assert scan_for_secrets("k=sk-abcdEFGH1234ijklMNOP5678qrst")[0].redacted == "sk-***"
    assert scan_for_secrets("id=AKIAIOSFODNN7EXAMPLE")[0].secret_type == "aws_access_key"


def test_n3_clean_text_has_no_findings() -> None:
    """Texto de negocio normal no produce hallazgos N3."""
    assert scan_for_secrets("minuta de la reunión\npunto 1: presupuesto trimestral\n") == []


def test_n3_extra_config_patterns_fully_redacted() -> None:
    """Un patron extra de config detecta y guarda su match TOTALMENTE redactado."""
    findings = scan_for_secrets("clave interna INTERNAL-9988 del sistema", ("INTERNAL-\\d+",))
    assert [f.secret_type for f in findings] == ["custom_1"]
    assert findings[0].redacted == "***"


def test_n3_invalid_extra_pattern_is_ignored() -> None:
    """Un patron extra invalido (typo de config) se ignora sin tumbar el escaneo."""
    assert scan_for_secrets("texto cualquiera", ("[unbalanced",)) == []


# ---------------------------------------------------------------------------------------
# N2 — PII (unidad, tarea 5.2)
# ---------------------------------------------------------------------------------------


def test_n2_detects_emails_and_bolivian_ci_with_context() -> None:
    """Presidio detecta emails y el reconocedor BO detecta el CI cuando hay contexto."""
    text = (
        "Contacto: juan.perez@example.com y maria.lopez@example.com\nCliente CI 7654321 fila 14\n"
    )
    findings = {f.entity_type: f for f in scan_for_pii(text)}

    assert findings["EMAIL_ADDRESS"].count == 2
    assert findings["BO_CI"].count == 1
    assert findings["BO_CI"].lines == (2,)


def test_n2_plain_number_without_context_is_not_flagged() -> None:
    """Un numero cualquiera sin contexto (CI/NIT/celular) NO se marca (menos falsos +)."""
    findings = {
        f.entity_type for f in scan_for_pii("El total vendido fue 7654321 unidades el mes.")
    }
    assert "BO_CI" not in findings
    assert "BO_NIT" not in findings


def test_n2_clean_text_has_no_findings() -> None:
    """Texto de negocio sin PII no produce hallazgos N2."""
    assert scan_for_pii("minuta de la reunión\npunto 1: presupuesto\n") == []


# ---------------------------------------------------------------------------------------
# is_sendable (unidad, helper de la tarea 6.3)
# ---------------------------------------------------------------------------------------


def _attachment(status: str, scan_result: dict[str, object] | None) -> Attachment:
    attachment = Attachment()
    attachment.status = status
    attachment.scan_result = scan_result
    return attachment


def test_is_sendable_rules() -> None:
    """bloqueado -> no; N2 sin confirmar -> no; ready limpio o N2 confirmado -> si."""
    assert is_sendable(_attachment("blocked", {"n3_findings": [{"secret_type": "jwt"}]})) is False
    assert is_sendable(_attachment("uploaded", None)) is False
    assert is_sendable(_attachment("error", None)) is False
    assert is_sendable(_attachment("ready", {"requires_test_data_confirmation": True})) is False
    assert is_sendable(_attachment("ready", None)) is True
    assert is_sendable(_attachment("ready", {"requires_test_data_confirmation": False})) is True


# ---------------------------------------------------------------------------------------
# Pipeline end-to-end (via extract_attachment, tareas 5.1-5.3)
# ---------------------------------------------------------------------------------------


def test_pipeline_secret_blocks_attachment(tmp_path: Path) -> None:
    """Escenario "secreto detectado bloquea el adjunto" (ANEXO §4.4).

    `Password=hunter2` en la linea 23 -> estado `blocked`, no enviable, con la linea y el
    fragmento redactado en `scan_result["n3_findings"]`.
    """
    config = _config(tmp_path)
    text = "\n".join([f"registro {i}" for i in range(1, 23)] + ["cfg: Password=hunter2"]) + "\n"

    with get_db_session() as db:
        attachment = _make_uploaded_attachment(db, name="config.txt", detected_type="text")
        outcome = extract_attachment(
            db,
            attachment,
            fake_extract_passthrough,
            _passthrough_source("config.txt", text),
            config,
        )

        assert outcome.attachment.status == "blocked"
        assert outcome.error is None
        assert outcome.result is not None  # la extraccion tuvo exito: el texto existe
        assert is_sendable(outcome.attachment) is False
        attachment_id = attachment.id

    with get_db_session() as db:
        stored = db.get(Attachment, attachment_id)
        assert stored is not None
        assert stored.status == "blocked"
        assert stored.scan_result is not None
        n3 = stored.scan_result["n3_findings"]
        assert n3[0]["secret_type"] == "connection_password"
        assert n3[0]["line"] == 23
        assert n3[0]["redacted"] == "Password=***"
        # El secreto en claro NUNCA se persiste.
        assert "hunter2" not in str(stored.scan_result)


def test_pipeline_jwt_blocks_attachment(tmp_path: Path) -> None:
    """Un JWT en la extraccion tambien deja el adjunto `blocked`."""
    config = _config(tmp_path)
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhZG1pbiJ9.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"

    with get_db_session() as db:
        attachment = _make_uploaded_attachment(db, name="log.txt", detected_type="text")
        outcome = extract_attachment(
            db,
            attachment,
            fake_extract_passthrough,
            _passthrough_source("log.txt", f"bearer {jwt}"),
            config,
        )
        assert outcome.attachment.status == "blocked"
        assert outcome.attachment.scan_result is not None
        assert outcome.attachment.scan_result["n3_findings"][0]["secret_type"] == "jwt"


def test_pipeline_pii_requires_confirmation(tmp_path: Path) -> None:
    """Escenario "PII detectada requiere confirmacion" (ANEXO §4.4), sin bloquear.

    2 emails + un CI con contexto -> `ready` con `pii_findings` +
    `requires_test_data_confirmation`, y NO enviable hasta confirmar.
    """
    config = _config(tmp_path)
    text = "Datos:\njuan.perez@example.com\nmaria.lopez@example.com\nCliente CI 7654321 fila 14\n"

    with get_db_session() as db:
        attachment = _make_uploaded_attachment(db, name="planilla.csv", detected_type="csv")
        outcome = extract_attachment(
            db,
            attachment,
            fake_extract_passthrough,
            _passthrough_source("planilla.csv", text),
            config,
        )

        assert outcome.attachment.status == "ready"  # N2 no bloquea
        assert is_sendable(outcome.attachment) is False  # pero no enviable sin confirmar
        attachment_id = attachment.id

    with get_db_session() as db:
        stored = db.get(Attachment, attachment_id)
        assert stored is not None
        assert stored.scan_result is not None
        assert stored.scan_result["requires_test_data_confirmation"] is True
        types = {f["entity_type"] for f in stored.scan_result["pii_findings"]}
        assert "EMAIL_ADDRESS" in types
        assert "BO_CI" in types
        # No hay `n3_findings` (no es un secreto) ni el dato en claro.
        assert "n3_findings" not in stored.scan_result
        assert "juan.perez@example.com" not in str(stored.scan_result)


def test_pipeline_n3_wins_over_n2(tmp_path: Path) -> None:
    """Escenario "N3 gana sobre N2": con secreto Y PII, el adjunto queda `blocked`.

    Al estar bloqueado no se pide confirmacion N2 (no es enviable de todos modos).
    """
    config = _config(tmp_path)
    text = "juan.perez@example.com\nCliente CI 7654321\nPassword=hunter2\n"

    with get_db_session() as db:
        attachment = _make_uploaded_attachment(db, name="mixto.txt", detected_type="text")
        outcome = extract_attachment(
            db, attachment, fake_extract_passthrough, _passthrough_source("mixto.txt", text), config
        )

        assert outcome.attachment.status == "blocked"
        assert is_sendable(outcome.attachment) is False
        scan_result = outcome.attachment.scan_result
        assert scan_result is not None
        assert "n3_findings" in scan_result
        assert "pii_findings" in scan_result  # se registra igual (telemetria)
        # No se exige confirmacion: bloqueado gana.
        assert scan_result.get("requires_test_data_confirmation", False) is False


def test_pipeline_clean_text_is_sendable(tmp_path: Path) -> None:
    """Texto limpio: `ready`, sin hallazgos N2/N3 y enviable; `scan_result` intacto."""
    config = _config(tmp_path)

    with get_db_session() as db:
        attachment = _make_uploaded_attachment(db, name="notas.txt", detected_type="text")
        outcome = extract_attachment(
            db,
            attachment,
            fake_extract_passthrough,
            _passthrough_source("notas.txt", "minuta de la reunión\npunto 1: presupuesto\n"),
            config,
        )

        assert outcome.attachment.status == "ready"
        assert is_sendable(outcome.attachment) is True
        assert outcome.attachment.scan_result is None
