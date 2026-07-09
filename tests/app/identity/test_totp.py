"""Tests de segundo factor TOTP y códigos de respaldo (d11, tarea 2.5)."""

from __future__ import annotations

import datetime

import pyotp
from cryptography.fernet import Fernet

from resultarai.adapters.persistence_postgres.connection import get_db_session
from resultarai.app.identity.totp import (
    BACKUP_CODE_COUNT,
    TotpConfig,
    enroll,
    generate_backup_codes,
    verify_backup_code,
    verify_code,
)
from tests.app.identity.conftest import make_user

# Clave Fernet explícita: los tests generan la suya (no dependen del entorno).
_CONFIG = TotpConfig(encryption_key=Fernet.generate_key())


def test_enroll_then_verify_valid_code() -> None:
    """El enrolamiento produce un secreto verificable y un provisioning URI."""
    user_id = make_user("totp-enroll")
    with get_db_session() as db:
        enrollment = enroll(db, user_id, "totp-enroll", _CONFIG)

    assert enrollment.provisioning_uri.startswith("otpauth://totp/")
    assert "ResultarAI" in enrollment.provisioning_uri

    # El test genera el código con pyotp desde el secreto devuelto.
    current_code = pyotp.TOTP(enrollment.secret).now()
    with get_db_session() as db:
        assert verify_code(db, user_id, current_code, _CONFIG) is True


def test_verify_rejects_wrong_code() -> None:
    """Un código fuera de la ventana temporal se rechaza."""
    user_id = make_user("totp-wrong")
    with get_db_session() as db:
        enrollment = enroll(db, user_id, "totp-wrong", _CONFIG)

    # Código generado 10 pasos atrás: fuera de la ventana ±1, inválido ahora.
    past = datetime.datetime.now(datetime.UTC) - datetime.timedelta(seconds=300)
    stale_code = pyotp.TOTP(enrollment.secret).at(past)
    with get_db_session() as db:
        assert verify_code(db, user_id, stale_code, _CONFIG) is False


def test_verify_code_without_enrollment_is_false() -> None:
    """Sin secreto enrolado, la verificación devuelve False (no lanza)."""
    user_id = make_user("totp-none")
    with get_db_session() as db:
        assert verify_code(db, user_id, "123456", _CONFIG) is False


def test_backup_codes_single_use() -> None:
    """Un código de respaldo sirve una sola vez; otro distinto sigue sirviendo."""
    user_id = make_user("totp-backup")
    with get_db_session() as db:
        codes = generate_backup_codes(db, user_id)

    assert len(codes) == BACKUP_CODE_COUNT
    assert len(set(codes)) == BACKUP_CODE_COUNT  # todos distintos

    with get_db_session() as db:
        assert verify_backup_code(db, user_id, codes[0]) is True
    # El mismo código ya no vale.
    with get_db_session() as db:
        assert verify_backup_code(db, user_id, codes[0]) is False
    # Otro código distinto sí vale.
    with get_db_session() as db:
        assert verify_backup_code(db, user_id, codes[1]) is True


def test_generate_backup_codes_replaces_previous() -> None:
    """Regenerar códigos invalida el conjunto anterior."""
    user_id = make_user("totp-regen")
    with get_db_session() as db:
        first = generate_backup_codes(db, user_id)
    with get_db_session() as db:
        generate_backup_codes(db, user_id)
    # Un código del primer conjunto ya no existe tras regenerar.
    with get_db_session() as db:
        assert verify_backup_code(db, user_id, first[0]) is False
