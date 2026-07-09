"""Segundo factor TOTP y códigos de respaldo (d11, tarea 2.5).

TOTP con ``pyotp`` (RFC 6238, ADR-0008). El secreto Base32 se cifra en reposo con
``cryptography.Fernet`` antes de persistir (design Decision 6): esta capa nunca
guarda el secreto en claro ni lo escribe en logs ni en auditoría. Los códigos de
respaldo se muestran una sola vez y se guardan como hash Argon2id (igual que una
contraseña); cada uno sirve una única vez.

Variable de entorno (leída por :meth:`TotpConfig.from_env`):

- ``IDENTITY_TOTP_ENCRYPTION_KEY``: clave Fernet (urlsafe base64 de 32 bytes) para
  cifrar el secreto TOTP. **Obligatoria en producción.** Si falta, se genera una
  efímera y se avisa: aceptable solo en dev/tests (al reiniciar el proceso, los
  secretos ya cifrados dejan de ser descifrables).
"""

from __future__ import annotations

import os
import secrets
import warnings
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

import pyotp
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.models import (
    TotpBackupCode,
    TotpSecret,
    get_utc_now,
)
from resultarai.app.identity.passwords import hash_password, verify_password

__all__ = [
    "BACKUP_CODE_COUNT",
    "Enrollment",
    "TotpConfig",
    "enroll",
    "generate_backup_codes",
    "verify_backup_code",
    "verify_code",
]

# Cantidad de códigos de respaldo que se generan por enrolamiento.
BACKUP_CODE_COUNT = 10

# Emisor que aparece en el provisioning URI (nombre de la app en el autenticador).
_ISSUER = "ResultarAI"


@dataclass(frozen=True)
class TotpConfig:
    """Configuración de cifrado TOTP."""

    encryption_key: bytes = field(repr=False)
    issuer: str = _ISSUER

    @classmethod
    def from_env(cls) -> TotpConfig:
        """Construye la configuración desde ``IDENTITY_TOTP_ENCRYPTION_KEY``.

        Si la variable no está definida, genera una clave Fernet efímera y avisa:
        válido solo en dev/tests, nunca en producción.
        """
        raw = os.environ.get("IDENTITY_TOTP_ENCRYPTION_KEY")
        if raw:
            encryption_key = raw.encode("utf-8")
        else:
            encryption_key = Fernet.generate_key()
            warnings.warn(
                "IDENTITY_TOTP_ENCRYPTION_KEY no está definida: se generó una clave "
                "de cifrado efímera. Válido solo en dev/tests; en producción define "
                "esta variable o los secretos TOTP dejan de ser descifrables al "
                "reiniciar.",
                RuntimeWarning,
                stacklevel=2,
            )
        return cls(encryption_key=encryption_key)


@dataclass(frozen=True)
class Enrollment:
    """Datos de enrolamiento que se muestran una única vez al usuario.

    ``secret`` es la clave Base32 (para el ingreso manual) y ``provisioning_uri``
    es el ``otpauth://`` que se codifica en el QR.
    """

    secret: str
    provisioning_uri: str


def _fernet(config: TotpConfig) -> Fernet:
    """Instancia Fernet a partir de la clave de la configuración."""
    return Fernet(config.encryption_key)


def enroll(
    db: DbSession,
    user_id: UUID,
    account_name: str,
    config: TotpConfig,
    *,
    now: datetime | None = None,
) -> Enrollment:
    """Genera y persiste (cifrado) un secreto TOTP para ``user_id``.

    Devuelve la clave Base32 y el provisioning URI. Reemplaza cualquier secreto
    previo del usuario (re-enrolamiento). La activación efectiva del segundo
    factor la decide el llamador tras confirmar un código con :func:`verify_code`
    (la sección 3).
    """
    now = now or get_utc_now()
    secret = pyotp.random_base32()
    encrypted = _fernet(config).encrypt(secret.encode("utf-8"))

    existing = db.get(TotpSecret, user_id)
    if existing is None:
        db.add(TotpSecret(user_id=user_id, encrypted_secret=encrypted, enrolled_at=now))
    else:
        existing.encrypted_secret = encrypted
        existing.enrolled_at = now
    db.flush()

    provisioning_uri = pyotp.TOTP(
        secret, name=account_name, issuer=config.issuer
    ).provisioning_uri()
    return Enrollment(secret=secret, provisioning_uri=provisioning_uri)


def verify_code(
    db: DbSession,
    user_id: UUID,
    code: str,
    config: TotpConfig,
    *,
    valid_window: int = 1,
) -> bool:
    """Verifica un código TOTP contra el secreto cifrado de ``user_id``.

    ``valid_window=1`` tolera ±1 paso (±30 s) de desfase de reloj. Devuelve
    ``False`` si el usuario no tiene secreto o si el ciphertext no descifra.
    """
    row = db.get(TotpSecret, user_id)
    if row is None:
        return False
    try:
        secret = _fernet(config).decrypt(bytes(row.encrypted_secret)).decode("utf-8")
    except InvalidToken:
        return False
    return pyotp.TOTP(secret).verify(code, valid_window=valid_window)


def generate_backup_codes(
    db: DbSession,
    user_id: UUID,
    *,
    count: int = BACKUP_CODE_COUNT,
    now: datetime | None = None,
) -> list[str]:
    """Genera ``count`` códigos de respaldo de un solo uso para ``user_id``.

    Devuelve los códigos en claro **una única vez**; en la base solo quedan sus
    hashes Argon2id. Reemplaza los códigos previos del usuario (regeneración).
    """
    now = now or get_utc_now()
    db.execute(delete(TotpBackupCode).where(TotpBackupCode.user_id == user_id))

    codes: list[str] = []
    for _ in range(count):
        # Dos grupos de 5 hex separados por guion: legible y con entropía amplia.
        code = f"{secrets.token_hex(3)}-{secrets.token_hex(3)}"
        codes.append(code)
        db.add(
            TotpBackupCode(
                user_id=user_id,
                code_hash=hash_password(code),
                created_at=now,
            )
        )
    db.flush()
    return codes


def verify_backup_code(
    db: DbSession,
    user_id: UUID,
    code: str,
    *,
    now: datetime | None = None,
) -> bool:
    """Verifica y consume un código de respaldo de ``user_id``.

    Recorre los códigos aún no usados; al primer match marca ``used_at`` (consumo
    de un solo uso) y devuelve ``True``. Un código ya usado no vuelve a servir.
    Devuelve ``False`` si ningún código no-usado coincide.
    """
    stmt = select(TotpBackupCode).where(
        TotpBackupCode.user_id == user_id,
        TotpBackupCode.used_at.is_(None),
    )
    for row in db.execute(stmt).scalars():
        if verify_password(code, row.code_hash):
            row.used_at = now or get_utc_now()
            db.flush()
            return True
    return False
