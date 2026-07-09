"""Tests de hashing y política de contraseñas (d11, tarea 2.1). Unit puro."""

from __future__ import annotations

import pytest

from resultarai.app.identity.passwords import (
    MIN_PASSWORD_LENGTH,
    PasswordPolicyError,
    generate_temporary_password,
    hash_password,
    needs_rehash,
    password_policy_violations,
    validate_password_policy,
    verify_password,
)

_VALID_PASSWORD = "Contrasena1!segura"


def test_hash_is_argon2id_and_not_plaintext() -> None:
    """El hash es Argon2id y no contiene la contraseña en claro."""
    hashed = hash_password(_VALID_PASSWORD)
    assert hashed.startswith("$argon2id$")
    assert _VALID_PASSWORD not in hashed


def test_verify_password_roundtrip() -> None:
    """La contraseña correcta verifica; una incorrecta no."""
    hashed = hash_password(_VALID_PASSWORD)
    assert verify_password(_VALID_PASSWORD, hashed) is True
    assert verify_password("otra-cosa-distinta", hashed) is False


def test_verify_password_malformed_hash_is_false() -> None:
    """Un hash malformado no lanza; devuelve False."""
    assert verify_password(_VALID_PASSWORD, "no-es-un-hash-valido") is False


def test_needs_rehash_false_for_fresh_hash() -> None:
    """Un hash recién generado con los parámetros vigentes no necesita rehash."""
    assert needs_rehash(hash_password(_VALID_PASSWORD)) is False


def test_valid_password_passes_policy() -> None:
    """Una contraseña que cumple la política no lanza ni reporta violaciones."""
    assert password_policy_violations(_VALID_PASSWORD) == []
    validate_password_policy(_VALID_PASSWORD)  # no debe lanzar


def test_short_password_violates_length() -> None:
    """Una contraseña corta reporta el requisito de longitud."""
    violations = password_policy_violations("Ab1!x")
    assert any(str(MIN_PASSWORD_LENGTH) in v for v in violations)


def test_policy_reports_each_missing_category() -> None:
    """Cada categoría faltante produce una violación accionable."""
    # Solo minúsculas y suficiente longitud: faltan mayúscula, número y símbolo.
    violations = password_policy_violations("abcdefghijklmno")
    joined = " ".join(violations)
    assert "mayúscula" in joined
    assert "número" in joined
    assert "símbolo" in joined


def test_validate_password_policy_raises_with_violations() -> None:
    """``validate_password_policy`` lanza con el detalle de lo que falta."""
    with pytest.raises(PasswordPolicyError) as exc_info:
        validate_password_policy("corta")
    assert exc_info.value.violations
    assert len(exc_info.value.violations) >= 1


def test_generate_temporary_password_satisfies_policy() -> None:
    """La contraseña temporal generada cumple la política y respeta la longitud."""
    for _ in range(20):
        temp = generate_temporary_password()
        assert len(temp) >= MIN_PASSWORD_LENGTH
        # No debe lanzar: cumple todos los requisitos.
        validate_password_policy(temp)


def test_generate_temporary_password_respects_min_length() -> None:
    """Pedir menos que el mínimo eleva a la longitud mínima de política."""
    temp = generate_temporary_password(length=4)
    assert len(temp) >= MIN_PASSWORD_LENGTH
