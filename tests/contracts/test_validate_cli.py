"""Tests del CLI de validacion de manifiestos (a02-core-manifiestos, tarea 4.1).

Cubre los 4 escenarios del requirement "CLI de validacion de manifiestos"
(`openspec/changes/a02-core-manifiestos/specs/manifest-validation/spec.md`):

1. CLI en verde sobre manifiestos validos -> exit 0, reporta lo validado.
2. CLI falla ante un Manifest invalido -> exit != 0, nombrando archivo y causa.
3. CLI detecta una referencia colgante -> exit != 0, reportandola.
4. CLI no accede a red -> ya se cumple por construccion (solo lee YAML y aplica
   schemas, igual que `load_registries`; no hay ninguna llamada de red en el camino),
   asi que no hace falta un test que simule "sin conectividad": no hay nada que cortar.

**Decision -- invocar `main()` directamente, no subprocess.** `resultarai.app.cli.main`
acepta un `argv: list[str] | None` y devuelve el exit code en vez de llamar a
`sys.exit`, precisamente para que los tests lo invoquen en proceso: mas rapido (sin
levantar un interprete ni `uv run` por test) y mas robusto (no depende de que el
entry point `resultarai-validate` este instalado/editable en el entorno que corre
pytest). La invocacion real via `uv run resultarai-validate` se ejerce por separado
como parte de la verificacion manual del comando (no en la suite), que es donde
importa probar el wiring de `[project.scripts]` en si.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from resultarai.app.cli import main


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
        "description": "Skill de ejemplo para el test del CLI de validacion.",
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


# 1. CLI en verde sobre manifiestos validos: los de fabrica del repo real.


def test_cli_exits_zero_on_valid_factory_manifests(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["--manifests-dir", str(FACTORY_MANIFESTS_DIR)])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "default_chat" in out
    assert "example_skill" in out
    assert "example_echo" in out
    assert "OK" in out


# 2. CLI falla ante un Manifest invalido (campo obligatorio ausente), nombrando archivo y causa.


def test_cli_exits_nonzero_on_invalid_manifest_naming_file_and_cause(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    invalid_payload = _tool_payload()
    del invalid_payload["security"]  # campo obligatorio del Tool Manifest
    path = _write_manifest(tmp_path / "tools", "invalid_tool.yaml", invalid_payload)

    exit_code = main(["--manifests-dir", str(tmp_path)])

    assert exit_code != 0
    err = capsys.readouterr().err
    assert str(path) in err
    assert "security" in err


# 3. CLI detecta una referencia colgante (Skill -> Tool inexistente) y la reporta.


def test_cli_exits_nonzero_on_dangling_reference(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_manifest(
        tmp_path / "skills",
        "example_skill.yaml",
        _skill_payload(tools=["nonexistent_tool"]),
    )
    _write_manifest(tmp_path / "evals", "skill_eval_template.yaml", _eval_payload())

    exit_code = main(["--manifests-dir", str(tmp_path)])

    assert exit_code != 0
    err = capsys.readouterr().err
    assert "Skill:example_skill" in err
    assert "Tool:nonexistent_tool" in err


# Casos adicionales de invocacion: directorio ausente y default de --manifests-dir.


def test_cli_exits_nonzero_when_manifests_dir_does_not_exist(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing_dir = tmp_path / "does_not_exist"

    exit_code = main(["--manifests-dir", str(missing_dir)])

    assert exit_code != 0
    err = capsys.readouterr().err
    assert str(missing_dir) in err


def test_cli_defaults_manifests_dir_to_cwd_slash_manifests(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(REPO_ROOT)

    exit_code = main([])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "default_chat" in out
