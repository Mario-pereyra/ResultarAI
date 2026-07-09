"""Test de integración: divulgación progresiva y resolución de skillset.

Cubre:
- Nivel 1: contexto de sistema contiene name+description, NO el body.
- Nivel 2: body se carga solo al activar la skill.
- Nivel 3: recurso se carga solo al referenciarse.
- Skillset fijo por versión de agente (inmutable en la sesión).
- Fail-fast: paquete inexistente hace fallar la carga.
- Intersección: el toolset ejecutable es el resultado correcto.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from resultarai.adapters.skills_fs.loader import FilesystemSkillPackageAdapter
from resultarai.core.manifests.agent import (
    AgentCapabilities,
    AgentEscalation,
    AgentEvals,
    AgentManifest,
    AgentRuntime,
    ToolAccessPolicy,
)
from resultarai.core.manifests.base import EvalStatus, ManifestStatus
from resultarai.core.manifests.skill import (
    EvalsConfig,
    ExecutionConfig,
    ExecutionMode,
    OutputPolicyConfig,
    SkillManifest,
)
from resultarai.core.manifests.skill import (
    SkillPackage as SkillPackageRef,
)
from resultarai.core.manifests.skill import (
    SkillPackageSpec as SkillPackageSpecEnum,
)
from resultarai.core.registries.registry import ManifestRegistry
from resultarai.core.skills.loader import (
    SkillPackageLoadError,
    build_skills_context,
    load_level2_body,
    load_level3_resource,
    load_skill_packages,
    resolve_agent_skillset,
)

_SKILL_MD = """\
---
name: test-skill
description: A test skill for integration testing.
allowed-tools:
  - example_echo
  - another_tool
---

# Test Skill Body

This body content should only appear at Level 2.
"""

_RESOURCE = "# Reference Template\n\nLevel 3 content."


def _make_skill_manifest(
    skill_id: str = "test_skill",
    ref: str = "test-skill",
    tools: list[str] | None = None,
    status: ManifestStatus = ManifestStatus.ACTIVE,
) -> SkillManifest:
    """Construye un SkillManifest de prueba."""
    return SkillManifest(
        id=skill_id,
        name="Test Skill",
        description="A test skill",
        status=status,
        version="1.0.0",
        skill_package=SkillPackageRef(
            spec=SkillPackageSpecEnum.AGENT_SKILLS,
            ref=ref,
            path=f"skills/packages/{ref}/SKILL.md",
            version="1.0.0",
        ),
        execution=ExecutionConfig(
            mode=ExecutionMode.READ_ONLY,
            graph="default_skill_graph",
        ),
        tools=tools or ["example_echo"],
        output_policy=OutputPolicyConfig(
            summarize_results=True,
            mask_sensitive_fields=False,
            max_rows=50,
        ),
        evals=EvalsConfig(
            status=EvalStatus.PLACEHOLDER,
            template="test_eval",
        ),
    )


def _make_agent_manifest(
    enabled_skills: list[str] | None = None,
) -> AgentManifest:
    """Construye un AgentManifest de prueba."""
    return AgentManifest(
        id="test_agent",
        name="Test Agent",
        type="default_orchestrator",
        status=ManifestStatus.ACTIVE,
        version="1.0.0",
        runtime=AgentRuntime(framework="langgraph", graph="test_graph"),
        capabilities=AgentCapabilities(
            can_answer_general_questions=True,
            can_use_skills=True,
            can_delegate_to_agents=False,
            can_execute_tools_directly=False,
        ),
        enabled_skills=enabled_skills or ["test_skill"],
        tool_access_policy=ToolAccessPolicy(
            mode="deny_by_default",
            allow_only_via_skills=True,
        ),
        observability={  # type: ignore[arg-type]
            "provider": "langfuse",
            "trace_all_interactions": True,
            "log_skill_selection": True,
            "log_tool_calls": True,
            "log_model_calls": True,
            "log_costs": True,
        },
        evals=AgentEvals(status="placeholder", template="test_eval"),
        escalation=AgentEscalation(enabled=True),
    )


@pytest.fixture
def packages_dir(tmp_path: Path) -> Path:
    """Crea un paquete fixture."""
    pkg = tmp_path / "test-skill"
    pkg.mkdir()
    (pkg / "SKILL.md").write_text(_SKILL_MD, encoding="utf-8")
    refs = pkg / "references"
    refs.mkdir()
    (refs / "template.md").write_text(_RESOURCE, encoding="utf-8")
    return tmp_path


@pytest.fixture
def adapter(packages_dir: Path) -> FilesystemSkillPackageAdapter:
    return FilesystemSkillPackageAdapter(packages_dir=packages_dir)


@pytest.fixture
def skill_registry() -> ManifestRegistry[SkillManifest]:
    return ManifestRegistry([_make_skill_manifest()])


class TestLoadSkillPackages:
    """Carga fail-fast de paquetes."""

    def test_loads_valid_package(
        self,
        skill_registry: ManifestRegistry[SkillManifest],
        adapter: FilesystemSkillPackageAdapter,
        packages_dir: Path,
    ) -> None:
        """Carga un paquete válido sin error."""
        packages = load_skill_packages(skill_registry, adapter, str(packages_dir))
        assert "test_skill" in packages
        pkg = packages["test_skill"]
        assert pkg.name == "test-skill"
        assert pkg.description == "A test skill for integration testing."
        assert "example_echo" in pkg.allowed_tools

    def test_missing_package_fails(
        self,
        adapter: FilesystemSkillPackageAdapter,
        tmp_path: Path,
    ) -> None:
        """Paquete inexistente hace fallar la carga."""
        missing_manifest = _make_skill_manifest(ref="nonexistent")
        registry: ManifestRegistry[SkillManifest] = ManifestRegistry([missing_manifest])
        with pytest.raises(SkillPackageLoadError, match="nonexistent"):
            load_skill_packages(registry, adapter, str(tmp_path))

    def test_skips_non_active_manifests(
        self,
        adapter: FilesystemSkillPackageAdapter,
        packages_dir: Path,
    ) -> None:
        """Manifiestos con status != active son ignorados."""
        draft_manifest = _make_skill_manifest(status=ManifestStatus.DRAFT)
        registry: ManifestRegistry[SkillManifest] = ManifestRegistry([draft_manifest])
        packages = load_skill_packages(registry, adapter, str(packages_dir))
        assert len(packages) == 0


class TestProgressiveDisclosure:
    """Divulgación progresiva en 3 niveles."""

    def test_level1_context_contains_metadata_not_body(
        self,
        skill_registry: ManifestRegistry[SkillManifest],
        adapter: FilesystemSkillPackageAdapter,
        packages_dir: Path,
    ) -> None:
        """Nivel 1: contexto contiene name+description, NO el body."""
        packages = load_skill_packages(skill_registry, adapter, str(packages_dir))
        agent = _make_agent_manifest()
        context = build_skills_context(agent, skill_registry, packages)

        # Metadata present
        assert "test-skill" in context
        assert "A test skill for integration testing." in context

        # Body NOT present
        assert "# Test Skill Body" not in context
        assert "Level 2" not in context

    def test_level2_body_loaded_on_activation(
        self,
        adapter: FilesystemSkillPackageAdapter,
    ) -> None:
        """Nivel 2: body se carga solo al activar (vía load_level2_body)."""
        body = load_level2_body(adapter, "test-skill")
        assert "# Test Skill Body" in body
        assert "Level 2" in body

    def test_level3_resource_loaded_on_demand(
        self,
        adapter: FilesystemSkillPackageAdapter,
    ) -> None:
        """Nivel 3: recurso se carga solo al referenciarse."""
        resource = load_level3_resource(adapter, "test-skill", "references/template.md")
        assert "# Reference Template" in resource
        assert "Level 3 content" in resource


class TestFixedSkillset:
    """Skillset fijo por versión de agente (inmutable en la sesión)."""

    def test_skillset_resolved_from_enabled_skills(
        self,
        skill_registry: ManifestRegistry[SkillManifest],
        adapter: FilesystemSkillPackageAdapter,
        packages_dir: Path,
    ) -> None:
        """El skillset se resuelve desde enabled_skills + active manifests."""
        packages = load_skill_packages(skill_registry, adapter, str(packages_dir))
        agent = _make_agent_manifest()
        skillset = resolve_agent_skillset(agent, skill_registry, packages)

        assert "test_skill" in skillset
        assert skillset["test_skill"] == frozenset({"example_echo"})

    def test_skill_not_in_enabled_skills_excluded(
        self,
        skill_registry: ManifestRegistry[SkillManifest],
        adapter: FilesystemSkillPackageAdapter,
        packages_dir: Path,
    ) -> None:
        """Una skill no en enabled_skills no aparece en el skillset."""
        packages = load_skill_packages(skill_registry, adapter, str(packages_dir))
        agent = _make_agent_manifest(enabled_skills=["other_skill"])
        skillset = resolve_agent_skillset(agent, skill_registry, packages)

        assert "test_skill" not in skillset

    def test_skillset_is_immutable_snapshot(
        self,
        skill_registry: ManifestRegistry[SkillManifest],
        adapter: FilesystemSkillPackageAdapter,
        packages_dir: Path,
    ) -> None:
        """El skillset resuelto no cambia aunque se modifique el registry después.

        Demuestra que el skillset es una instantánea fija por versión.
        """
        packages = load_skill_packages(skill_registry, adapter, str(packages_dir))
        agent = _make_agent_manifest()

        # Resolver skillset
        skillset = resolve_agent_skillset(agent, skill_registry, packages)

        # El skillset es un dict con frozensets → inmutable en contenido
        assert isinstance(skillset["test_skill"], frozenset)
        assert "test_skill" in skillset

        # Simular que se añade una nueva skill después de resolver
        new_manifest = _make_skill_manifest(
            skill_id="new_skill", ref="test-skill", tools=["example_echo"]
        )
        new_registry: ManifestRegistry[SkillManifest] = ManifestRegistry(
            [_make_skill_manifest(), new_manifest]
        )

        # Cargar packages para el nuevo registry también
        new_packages = load_skill_packages(new_registry, adapter, str(packages_dir))

        # El skillset ORIGINAL no incluye new_skill (snapshot inmutable)
        assert "new_skill" not in skillset

        # Solo un nuevo resolve con los nuevos packages la incluiría
        new_agent = _make_agent_manifest(enabled_skills=["test_skill", "new_skill"])
        new_skillset = resolve_agent_skillset(new_agent, new_registry, new_packages)
        assert "new_skill" in new_skillset


class TestToolsetIntersectionIntegration:
    """Intersección del toolset ejecutable en contexto real."""

    def test_toolset_is_intersection_of_package_and_manifest(
        self,
        adapter: FilesystemSkillPackageAdapter,
        packages_dir: Path,
    ) -> None:
        """El toolset ejecutable es la intersección de package.allowed_tools ∩ manifest.tools."""
        # Package has [example_echo, another_tool], manifest has [example_echo]
        manifest = _make_skill_manifest(tools=["example_echo"])
        registry: ManifestRegistry[SkillManifest] = ManifestRegistry([manifest])
        packages = load_skill_packages(registry, adapter, str(packages_dir))

        agent = _make_agent_manifest()
        skillset = resolve_agent_skillset(agent, registry, packages)

        # Only example_echo is in both
        assert skillset["test_skill"] == frozenset({"example_echo"})
