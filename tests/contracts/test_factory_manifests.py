"""Test de contrato: los manifiestos de fabrica REALES del repo cargan en los Registries.

A diferencia de `tests/core/test_registry_loading.py` y `tests/core/test_cross_references.py`
(que escriben fixtures propios con `yaml.safe_dump` sobre `tmp_path`, sin depender de
`manifests/`), este test apunta `load_registries` directamente al directorio `manifests/`
del root del repo y ejercita el conjunto de fabrica que existe hoy en el arbol: el Agent
`default_chat`, la Skill `example_skill`, la Tool `example_echo`, la Policy
`example_read_only_policy`, el Routing `default_routing` y los 3 Eval Templates
placeholder (`default_chat_eval`, `example_skill_eval`, `example_echo_eval`).

Cubre los 4 escenarios del requirement "Manifiestos de fabrica de ejemplo cargables"
(`openspec/changes/a02-core-manifiestos/specs/manifest-registries/spec.md`):

1. El conjunto completo carga y valida; las referencias cruzadas resuelven; los
   Manifests con `ManifestStatus` quedan `active` e invocables (los Eval Templates usan
   su propio `EvalStatus.PLACEHOLDER`, ajeno a ese ciclo de vida, ver `manifests/eval.py`).
2. La regla de oro de `default_chat`: `can_execute_tools_directly == False` y
   `tool_access_policy.mode == "deny_by_default"`.
3. La clasificacion de la Tool `example_echo`: `risk.operation_type == read`,
   `risk.level == low`, `security.allow_sql_freeform == False` y el binding MCP
   (`server`/`tool_name`/`spec_revision`) presente.
4. La Policy de ejemplo es deny-by-default: solo declara `allow` para lecturas, ninguna
   regla `allow` cubre `operation_type: write` (ese caso queda en `deny` implicito, que
   resolvera el Policy Gate en `a03`).

La ruta a `manifests/` se resuelve de forma robusta a partir de este archivo (subiendo
directorios hasta encontrar la raiz del repo), nunca relativa al cwd desde el que se
invoque `pytest`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from resultarai.core.manifests import ManifestStatus
from resultarai.core.manifests.eval import EvalStatus
from resultarai.core.manifests.policy import PolicyEffect
from resultarai.core.manifests.tool import OperationType
from resultarai.core.registries import Registries, load_registries


def _find_repo_root(start: Path) -> Path:
    """Sube desde `start` hasta el directorio que contiene `pyproject.toml` y `manifests/`.

    Resuelve la raiz del repo relativa a la ubicacion de este archivo, no al directorio de
    trabajo actual: `pytest` puede invocarse desde cualquier cwd (raiz del repo, un
    subdirectorio, o incluso desde fuera del repo con `--rootdir`), y ese cwd no es un
    supuesto seguro sobre donde vive `manifests/`.
    """
    for candidate in (start, *start.parents):
        if (candidate / "pyproject.toml").is_file() and (candidate / "manifests").is_dir():
            return candidate
    raise RuntimeError(
        f"no se encontro la raiz del repo (pyproject.toml + manifests/) subiendo desde {start}"
    )


REPO_ROOT = _find_repo_root(Path(__file__).resolve())
MANIFESTS_DIR = REPO_ROOT / "manifests"


@pytest.fixture(scope="module")
def registries() -> Registries:
    """Los 6 Registries construidos sobre los manifiestos de fabrica REALES de `manifests/`."""
    return load_registries(MANIFESTS_DIR)


# 1. El conjunto completo de fabrica carga y valida; referencias cruzadas resueltas;
#    los manifiestos con ManifestStatus quedan active e invocables (evals: EvalStatus propio).


def test_factory_manifest_set_loads_and_all_are_active_and_invocable(
    registries: Registries,
) -> None:
    agent = registries.agents.get("default_chat")
    skill = registries.skills.get("example_skill")
    tool = registries.tools.get("example_echo")
    policy = registries.policies.get("example_read_only_policy")
    routing = registries.routing.get("default_routing")

    assert agent is not None
    assert skill is not None
    assert tool is not None
    assert policy is not None
    assert routing is not None

    # Los 5 Manifests que comparten el ciclo de vida ManifestStatus quedan active e invocables.
    for manifest_registry, manifest_id in (
        (registries.agents, "default_chat"),
        (registries.skills, "example_skill"),
        (registries.tools, "example_echo"),
        (registries.policies, "example_read_only_policy"),
        (registries.routing, "default_routing"),
    ):
        assert manifest_registry.get(manifest_id).status == ManifestStatus.ACTIVE  # type: ignore[union-attr]
        assert manifest_registry.is_invocable(manifest_id) is True
        assert manifest_registry.get_invocable(manifest_id) is not None

    # Los 3 Eval Templates placeholder usan su propio EvalStatus (ajeno a ManifestStatus):
    # no se esperan invocables via `is_invocable` (compara contra ManifestStatus.ACTIVE),
    # sino con `status: placeholder`, tal como declara el requirement de fabrica.
    for eval_id in ("default_chat_eval", "example_skill_eval", "example_echo_eval"):
        eval_template = registries.evals.get(eval_id)
        assert eval_template is not None
        assert eval_template.status == EvalStatus.PLACEHOLDER

    # Referencias cruzadas resueltas (si no, `load_registries` ya habria fallado con
    # `DanglingReferenceError` al construir la fixture `registries`): Agent -> Skill,
    # Skill -> Tool y Skill/Agent -> Eval Template, todas presentes.
    assert "example_skill" in agent.enabled_skills
    assert "example_echo" in skill.tools
    assert agent.evals.template == "default_chat_eval"
    assert skill.evals.template == "example_skill_eval"
    assert tool.evals.template == "example_echo_eval"


# 2. default_chat de fabrica respeta la regla de oro (regla dura 3).


def test_default_chat_respects_the_golden_rule(registries: Registries) -> None:
    agent = registries.agents.get("default_chat")

    assert agent is not None
    assert agent.capabilities.can_execute_tools_directly is False
    assert agent.tool_access_policy.mode == "deny_by_default"


# 3. La Tool example_echo de fabrica: clasificacion de riesgo + binding MCP.


def test_example_echo_tool_classification_and_mcp_binding(registries: Registries) -> None:
    tool = registries.tools.get("example_echo")

    assert tool is not None
    assert tool.risk.operation_type == OperationType.READ
    assert tool.risk.level == "low"
    assert tool.security.allow_sql_freeform is False

    # Binding MCP presente: referencia obligatoria server + tool_name (+ spec_revision).
    assert tool.mcp.server
    assert tool.mcp.tool_name == "echo"
    assert tool.mcp.spec_revision


# 4. La Policy de ejemplo es deny-by-default: solo declara allow para lecturas.


def test_example_policy_is_deny_by_default_only_allows_reads(registries: Registries) -> None:
    policy = registries.policies.get("example_read_only_policy")

    assert policy is not None

    allow_rules = [rule for rule in policy.rules if rule.effect == PolicyEffect.ALLOW]
    assert len(allow_rules) > 0
    assert all(rule.when.get("operation_type") == "read" for rule in allow_rules)

    # Ninguna regla allow cubre operation_type: write -- la escritura queda en deny
    # implicito (decision real del Policy Gate en runtime, a03).
    assert not any(rule.when.get("operation_type") == "write" for rule in allow_rules)
