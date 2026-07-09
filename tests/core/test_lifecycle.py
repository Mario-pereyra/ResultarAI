"""Tests del ciclo de vida y el kill switch por `status` (a02-core-manifiestos, 2.3).

Cubre los 4 escenarios exactos del requirement "Ciclo de vida draft->validated->
active->deprecated y kill switch por status"
(`openspec/changes/a02-core-manifiestos/specs/manifest-registries/spec.md`):

1. Un Manifest `active` con referencias validas -> el Registry lo expone como invocable.
2. Un Manifest `draft` -> no se carga al runtime (no invocable), aunque exista en
   `manifests/` (queda catalogado).
3. Kill switch: un `active` que cambia a `deprecated` (nueva carga del YAML) -> deja de
   ser invocable pero permanece catalogado y consultable por trazabilidad.
4. Transicion no permitida: marcar `active` un Manifest que no paso por `validated` -> la
   operacion falla.

Los escenarios 1-3 ejercitan `load_registries` + `ManifestRegistry.is_invocable`/
`get_invocable`/`invocable` (los Manifests vienen de YAML, inmutables en memoria: el "kill
switch" del escenario 3 se simula con una segunda carga del mismo archivo ya editado,
igual que hace `test_cross_references.py` al sobrescribir un manifiesto entre cargas). El
escenario 4 ejercita `validate_status_transition` directamente: es la funcion pura del
grafo de transiciones (ver decision documentada en `core/manifests/lifecycle.py`), no hay
historial persistido de `status` que consultar en este change.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from resultarai.core.manifests import (
    InvalidStatusTransitionError,
    ManifestStatus,
    validate_status_transition,
)
from resultarai.core.registries import load_registries


def _skill_payload(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": "example_skill",
        "name": "Utilidades de Ejemplo",
        "status": "active",
        "version": "1.0.0",
        "description": "Skill de ejemplo para los tests de ciclo de vida.",
        "skill_package": {
            "spec": "agent_skills",
            "ref": "example_utils",
            "path": "skills/example_utils/SKILL.md",
            "version": "1.0.0",
        },
        "execution": {"mode": "read_only", "graph": "default_skill_graph"},
        "tools": ["example_echo"],
        "output_policy": {
            "summarize_results": True,
            "mask_sensitive_fields": True,
            "max_rows": 20,
        },
        "evals": {"status": "placeholder", "template": "skill_eval_template"},
    }
    data.update(overrides)
    return data


def _tool_payload(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": "example_echo",
        "name": "Echo de Ejemplo",
        "status": "active",
        "version": "1.0.0",
        "type": "mcp_tool",
        "adapter": "mcp",
        "mcp": {
            "server": "example_utils_server",
            "tool_name": "echo",
            "spec_revision": "2025-11-25",
            "endpoint_ref": "example_mcp_endpoint",
        },
        "risk": {"level": "low", "operation_type": "read"},
        "permissions": {"mode": "read_only", "requires_human_approval": False},
        "security": {
            "allow_sql_freeform": False,
            "allow_dynamic_table_access": False,
            "mask_sensitive_fields": True,
        },
        "audit": {
            "log_request": True,
            "log_response_summary": True,
            "log_user": True,
            "log_tenant": True,
        },
        "evals": {"status": "placeholder", "template": "tool_eval_template"},
    }
    data.update(overrides)
    return data


def _eval_payload(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": "skill_eval_template",
        "status": "placeholder",
        "version": "1.0.0",
        "target_kind": "skill",
        "metrics_planned": ["task_completion_rate"],
        "dataset": None,
    }
    data.update(overrides)
    return data


def _write_manifest(directory: Path, filename: str, payload: dict[str, Any]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


# 1. Manifest active con referencias validas -> el Registry lo expone como invocable.


def test_active_manifest_with_valid_references_is_invocable(tmp_path: Path) -> None:
    _write_manifest(tmp_path / "skills", "example_skill.yaml", _skill_payload())
    _write_manifest(tmp_path / "tools", "example_echo.yaml", _tool_payload())
    _write_manifest(
        tmp_path / "evals",
        "skill_eval_template.yaml",
        _eval_payload(),
    )
    _write_manifest(
        tmp_path / "evals",
        "tool_eval_template.yaml",
        _eval_payload(id="tool_eval_template", target_kind="tool"),
    )

    registries = load_registries(tmp_path)

    assert registries.skills.is_invocable("example_skill") is True
    invocable_skill = registries.skills.get_invocable("example_skill")
    assert invocable_skill is not None
    assert invocable_skill.id == "example_skill"
    assert [manifest.id for manifest in registries.skills.invocable()] == ["example_skill"]


# 2. Manifest draft -> no se carga al runtime (no invocable), aunque exista en manifests/.


def test_draft_manifest_is_catalogued_but_not_invocable(tmp_path: Path) -> None:
    # La skill draft no la referencia ningun Agent (no hay agents/ en este fixture), asi
    # que no dispara la validacion de referencias cruzadas de la tarea 2.2: el unico punto
    # bajo prueba aqui es la invocabilidad por status, no las referencias cruzadas.
    _write_manifest(tmp_path / "skills", "example_skill.yaml", _skill_payload(status="draft"))
    _write_manifest(tmp_path / "tools", "example_echo.yaml", _tool_payload())
    _write_manifest(tmp_path / "evals", "skill_eval_template.yaml", _eval_payload())
    _write_manifest(
        tmp_path / "evals",
        "tool_eval_template.yaml",
        _eval_payload(id="tool_eval_template", target_kind="tool"),
    )

    registries = load_registries(tmp_path)

    # Catalogado: existe en manifests/, el loader lo carga y `get`/`in` lo confirman.
    draft_skill = registries.skills.get("example_skill")
    assert draft_skill is not None
    assert draft_skill.status is ManifestStatus.DRAFT
    assert "example_skill" in registries.skills

    # No invocable: un draft nunca se expone como invocable al runtime.
    assert registries.skills.is_invocable("example_skill") is False
    assert registries.skills.get_invocable("example_skill") is None
    assert registries.skills.invocable() == ()


# 3. Kill switch: un active que cambia a deprecated (nueva carga del YAML) -> deja de ser
#    invocable pero permanece catalogado y consultable por trazabilidad.


def test_kill_switch_deprecating_an_active_manifest(tmp_path: Path) -> None:
    _write_manifest(tmp_path / "skills", "example_skill.yaml", _skill_payload())
    _write_manifest(tmp_path / "tools", "example_echo.yaml", _tool_payload())
    _write_manifest(tmp_path / "evals", "skill_eval_template.yaml", _eval_payload())
    _write_manifest(
        tmp_path / "evals",
        "tool_eval_template.yaml",
        _eval_payload(id="tool_eval_template", target_kind="tool"),
    )

    before = load_registries(tmp_path)
    assert before.skills.is_invocable("example_skill") is True

    # El kill switch es cambiar `status`, nunca borrar el Manifest: se reescribe el mismo
    # YAML con `status: deprecated` y se recarga (los Manifests son inmutables en memoria;
    # una nueva carga es la unica forma de observar el cambio de status).
    _write_manifest(
        tmp_path / "skills",
        "example_skill.yaml",
        _skill_payload(status="deprecated"),
    )

    after = load_registries(tmp_path)

    # Deja de ser invocable...
    assert after.skills.is_invocable("example_skill") is False
    assert after.skills.get_invocable("example_skill") is None
    assert after.skills.invocable() == ()

    # ...pero permanece catalogado y consultable por trazabilidad: no fue borrado.
    deprecated_skill = after.skills.get("example_skill")
    assert deprecated_skill is not None
    assert deprecated_skill.status is ManifestStatus.DEPRECATED
    assert "example_skill" in after.skills


# 4. Transicion no permitida: marcar active un Manifest que no paso por validated -> falla.


def test_marking_active_without_prior_validated_fails() -> None:
    with pytest.raises(InvalidStatusTransitionError) as exc_info:
        validate_status_transition(ManifestStatus.DRAFT, ManifestStatus.ACTIVE)

    assert exc_info.value.current is ManifestStatus.DRAFT
    assert exc_info.value.new is ManifestStatus.ACTIVE
    assert "draft" in str(exc_info.value)
    assert "active" in str(exc_info.value)


@pytest.mark.parametrize(
    ("current", "new"),
    [
        (ManifestStatus.DRAFT, ManifestStatus.VALIDATED),
        (ManifestStatus.VALIDATED, ManifestStatus.ACTIVE),
        (ManifestStatus.ACTIVE, ManifestStatus.DEPRECATED),
    ],
)
def test_each_step_of_the_lifecycle_graph_is_allowed(
    current: ManifestStatus, new: ManifestStatus
) -> None:
    validate_status_transition(current, new)  # no debe lanzar


@pytest.mark.parametrize(
    ("current", "new"),
    [
        (ManifestStatus.DRAFT, ManifestStatus.ACTIVE),
        (ManifestStatus.DRAFT, ManifestStatus.DEPRECATED),
        (ManifestStatus.VALIDATED, ManifestStatus.DEPRECATED),
        (ManifestStatus.ACTIVE, ManifestStatus.VALIDATED),
        (ManifestStatus.DEPRECATED, ManifestStatus.ACTIVE),
    ],
)
def test_transitions_outside_the_graph_are_rejected(
    current: ManifestStatus, new: ManifestStatus
) -> None:
    with pytest.raises(InvalidStatusTransitionError):
        validate_status_transition(current, new)
