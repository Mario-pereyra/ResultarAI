"""Tests del schema base de Manifest (BaseManifest): strict mode + semver + status.

Se usa `model_validate` con un dict porque asi llega un Manifest en produccion:
YAML -> dict -> validacion (los valores son strings, no miembros del enum).
"""

from typing import Any

import pytest
from pydantic import ValidationError

from resultarai.core.manifests import BaseManifest, ManifestStatus


class _SampleManifest(BaseManifest):
    """Subclase minima para ejercitar la base sin depender de un Manifest concreto."""


def _payload(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {"id": "example_echo", "status": "active", "version": "1.0.0"}
    data.update(overrides)
    return data


def test_valid_manifest_builds_and_exposes_typed_fields() -> None:
    manifest = _SampleManifest.model_validate(_payload())

    assert manifest.id == "example_echo"
    assert manifest.status is ManifestStatus.ACTIVE
    assert manifest.version == "1.0.0"


def test_status_accepts_every_lifecycle_string_from_yaml() -> None:
    for raw, expected in [
        ("draft", ManifestStatus.DRAFT),
        ("validated", ManifestStatus.VALIDATED),
        ("active", ManifestStatus.ACTIVE),
        ("deprecated", ManifestStatus.DEPRECATED),
    ]:
        manifest = _SampleManifest.model_validate(_payload(status=raw))
        assert manifest.status is expected


def test_unknown_field_rejected_by_strict_mode() -> None:
    with pytest.raises(ValidationError) as exc_info:
        _SampleManifest.model_validate(_payload(unexpected_key="boom"))

    assert "unexpected_key" in str(exc_info.value)


@pytest.mark.parametrize("bad_version", ["v1", "1.2", "1.0", "latest", "1.0.0-rc1", "01.0.0"])
def test_non_semver_version_rejected(bad_version: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        _SampleManifest.model_validate(_payload(version=bad_version))

    assert "version" in str(exc_info.value)


def test_status_outside_enum_rejected() -> None:
    with pytest.raises(ValidationError) as exc_info:
        _SampleManifest.model_validate(_payload(status="archived"))

    assert "status" in str(exc_info.value)


def test_empty_id_rejected() -> None:
    with pytest.raises(ValidationError) as exc_info:
        _SampleManifest.model_validate(_payload(id=""))

    assert "id" in str(exc_info.value)


def test_strict_mode_rejects_implicit_type_coercion() -> None:
    # version es str: en strict mode un int (100) no se coacciona a "100".
    with pytest.raises(ValidationError):
        _SampleManifest.model_validate(_payload(version=100))
