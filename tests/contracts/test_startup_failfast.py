"""Tests del arranque fail-fast de la plataforma (a02-core-manifiestos, tarea 4.2).

Cubre los 4 escenarios del requirement "Validación fail-fast al arranque"
(`openspec/changes/a02-core-manifiestos/specs/manifest-validation/spec.md`):

1. Arranque exitoso con manifiestos válidos -> `bootstrap` devuelve los Registries
   construidos.
2. Arranque abortado por un Manifest que viola su schema -> `bootstrap` lanza
   `StartupError` (no devuelve, no queda "en servicio") citando el Manifest/archivo
   culpable.
3. Arranque abortado por una referencia colgante -> `StartupError` señala el origen y el
   destino de la referencia rota.
4. Un Manifest `draft` válido junto a los `active` -> el arranque continúa (`bootstrap`
   devuelve) y el `draft` queda catalogado pero no invocable.

Mismos fixtures YAML que `tests/contracts/test_validate_cli.py` (misma fuente de verdad,
`load_registries`, ejercitada ahora a través de `bootstrap`, no del CLI).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from resultarai.app.startup import StartupError, bootstrap
from resultarai.core.manifests import ManifestStatus
from resultarai.core.registries import Registries


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


def _skill_payload(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": "example_skill",
        "name": "Utilidades de Ejemplo",
        "status": "active",
        "version": "1.0.0",
        "description": "Skill de ejemplo para el test de arranque fail-fast.",
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


def _find_repo_root(start: Path) -> Path:
    """Sube desde `start` hasta el directorio que contiene `pyproject.toml` y `manifests/`."""
    for candidate in (start, *start.parents):
        if (candidate / "pyproject.toml").is_file() and (candidate / "manifests").is_dir():
            return candidate
    raise RuntimeError(
        f"no se encontro la raiz del repo (pyproject.toml + manifests/) subiendo desde {start}"
    )


REPO_ROOT = _find_repo_root(Path(__file__).resolve())
FACTORY_MANIFESTS_DIR = REPO_ROOT / "manifests"


# 1. Arranque exitoso con manifiestos validos -> Registries construidos.


def test_bootstrap_succeeds_with_valid_factory_manifests_and_returns_registries() -> None:
    registries = bootstrap(FACTORY_MANIFESTS_DIR)

    assert isinstance(registries, Registries)
    agent = registries.agents.get("default_chat")
    assert agent is not None
    assert registries.agents.is_invocable("default_chat") is True


# 2. Arranque abortado por Manifest que viola schema -> StartupError citando el manifest.


def test_bootstrap_aborts_on_schema_violation_naming_the_culprit_manifest(
    tmp_path: Path,
) -> None:
    invalid_payload = _tool_payload()
    del invalid_payload["security"]  # campo obligatorio del Tool Manifest
    path = _write_manifest(tmp_path / "tools", "invalid_tool.yaml", invalid_payload)

    with pytest.raises(StartupError) as exc_info:
        bootstrap(tmp_path)

    message = str(exc_info.value)
    assert str(path) in message
    assert "security" in message
    # No queda "en servicio": la excepcion se propaga, no hay Registries que consumir.
    assert exc_info.value.__cause__ is not None


# 3. Arranque abortado por referencia colgante -> StartupError señalandola.


def test_bootstrap_aborts_on_dangling_reference_naming_origin_and_target(
    tmp_path: Path,
) -> None:
    _write_manifest(
        tmp_path / "skills",
        "example_skill.yaml",
        _skill_payload(tools=["nonexistent_tool"]),
    )
    _write_manifest(tmp_path / "evals", "skill_eval_template.yaml", _eval_payload())

    with pytest.raises(StartupError) as exc_info:
        bootstrap(tmp_path)

    message = str(exc_info.value)
    assert "Skill:example_skill" in message
    assert "Tool:nonexistent_tool" in message
    assert exc_info.value.__cause__ is not None


# 4. Manifest draft valido junto a los active -> el arranque continua y el draft no es
#    invocable.


def test_bootstrap_continues_with_a_valid_draft_manifest_not_invocable(
    tmp_path: Path,
) -> None:
    # El tool draft no lo referencia ninguna Skill (no hay skills/ en este fixture), asi
    # que no dispara la validacion de referencias cruzadas de Agent/Skill->Tool: el unico
    # punto bajo prueba aqui es que un draft valido no aborta el arranque. Su propio
    # `evals.template` si se valida siempre (independiente del status del Tool, ver
    # `cross_references.py`), asi que el Eval Template referenciado debe existir.
    _write_manifest(tmp_path / "tools", "example_echo.yaml", _tool_payload(status="draft"))
    _write_manifest(
        tmp_path / "evals",
        "tool_eval_template.yaml",
        _eval_payload(id="tool_eval_template", target_kind="tool"),
    )

    registries = bootstrap(tmp_path)

    draft_tool = registries.tools.get("example_echo")
    assert draft_tool is not None
    assert draft_tool.status is ManifestStatus.DRAFT
    assert "example_echo" in registries.tools

    assert registries.tools.is_invocable("example_echo") is False
    assert registries.tools.get_invocable("example_echo") is None
    assert registries.tools.invocable() == ()
