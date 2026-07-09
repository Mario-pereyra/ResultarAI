"""Hashing, verificación y política de contraseñas (d11, tarea 2.1).

Capa delgada sobre ``argon2-cffi`` (ADR-0008): nunca criptografía artesanal y
nunca comparación manual de strings. El hashing usa Argon2id con los parámetros
por defecto de ``argon2-cffi``, que cumplen la recomendación vigente de OWASP
(Password Storage Cheat Sheet): a la fecha ``m=65536`` KiB, ``t=3`` iteraciones,
``p=4`` de paralelismo. Se usan los defaults de la librería a propósito: se
mantienen actualizados con las versiones y ``needs_rehash`` migra los hashes
viejos cuando esos parámetros cambien.
"""

from __future__ import annotations

import secrets
import string

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

__all__ = [
    "MIN_PASSWORD_LENGTH",
    "PasswordPolicyError",
    "generate_temporary_password",
    "hash_password",
    "needs_rehash",
    "password_policy_violations",
    "validate_password_policy",
    "verify_password",
]

# Longitud mínima de contraseña (design Decision 7).
MIN_PASSWORD_LENGTH = 12

# Instancia compartida: construir un ``PasswordHasher`` solo fija parámetros
# numéricos (sin I/O), por lo que es seguro a nivel de módulo y reutilizarlo
# evita recalcular la configuración en cada hash.
_HASHER = PasswordHasher()

# Conjunto de símbolos que cuenta como "símbolo" para la política y del que se
# extrae al generar contraseñas temporales (subconjunto seguro de puntuación).
_SYMBOLS = "!@#$%^&*()-_=+[]{};:,.?"


class PasswordPolicyError(ValueError):
    """La contraseña no cumple la política del servidor.

    ``violations`` lista, en español y de forma accionable, cada requisito
    incumplido, para que la UI muestre exactamente qué falta corregir.
    """

    def __init__(self, violations: list[str]) -> None:
        self.violations = violations
        super().__init__("; ".join(violations))


def hash_password(password: str) -> str:
    """Devuelve el hash Argon2id codificado de ``password``."""
    return _HASHER.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verifica ``password`` contra ``password_hash`` en tiempo constante.

    Usa la verificación de ``argon2-cffi`` (comparación en tiempo constante);
    jamás compara strings a mano. Devuelve ``False`` ante desajuste o ante un
    hash malformado, nunca propaga la excepción de la librería al llamador.
    """
    try:
        return _HASHER.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """Indica si ``password_hash`` se generó con parámetros desactualizados.

    Envuelve ``PasswordHasher.check_needs_rehash``: cuando devuelve ``True``, el
    llamador debería rehashear la contraseña (típicamente tras un login exitoso,
    momento en que dispone del texto plano) para migrarla a los parámetros
    vigentes.
    """
    return _HASHER.check_needs_rehash(password_hash)


def password_policy_violations(password: str) -> list[str]:
    """Devuelve la lista de requisitos de política que ``password`` incumple.

    Función pura (sin efectos): útil para el medidor de fortaleza y para
    ``validate_password_policy``. Lista vacía significa que cumple la política.
    """
    violations: list[str] = []
    if len(password) < MIN_PASSWORD_LENGTH:
        violations.append(f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres.")
    if not any(c.isupper() for c in password):
        violations.append("La contraseña debe incluir al menos una letra mayúscula.")
    if not any(c.islower() for c in password):
        violations.append("La contraseña debe incluir al menos una letra minúscula.")
    if not any(c.isdigit() for c in password):
        violations.append("La contraseña debe incluir al menos un número.")
    if not any(c in string.punctuation for c in password):
        violations.append("La contraseña debe incluir al menos un símbolo.")
    return violations


def validate_password_policy(password: str) -> None:
    """Valida ``password`` contra la política del servidor (design Decision 7).

    Única fuente de verdad de la política (≥12 caracteres, con mayúscula,
    minúscula, número y símbolo); el medidor de fortaleza de la UI es solo ayuda
    visual. Lanza :class:`PasswordPolicyError` con el detalle accionable si algún
    requisito falta; no devuelve nada si la contraseña es válida.
    """
    violations = password_policy_violations(password)
    if violations:
        raise PasswordPolicyError(violations)


def generate_temporary_password(length: int = 16) -> str:
    """Genera una contraseña temporal aleatoria que cumple la política.

    Usa ``secrets`` (CSPRNG). Garantiza al menos una mayúscula, una minúscula, un
    número y un símbolo, y una longitud ``>= MIN_PASSWORD_LENGTH``. Pensada para
    el alta por Admin y el reset (contraseña de un solo uso que fuerza el cambio
    en el primer acceso).
    """
    length = max(length, MIN_PASSWORD_LENGTH)
    # Un carácter garantizado de cada categoría requerida por la política.
    required = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice(_SYMBOLS),
    ]
    pool = string.ascii_letters + string.digits + _SYMBOLS
    remaining = [secrets.choice(pool) for _ in range(length - len(required))]
    chars = required + remaining
    # Mezcla criptográficamente segura para no dejar las categorías garantizadas
    # siempre al inicio.
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)
