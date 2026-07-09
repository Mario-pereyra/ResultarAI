"""Tests de la puerta abierta a RAG: campo `retrieval` opcional del Skill Manifest.

Cubre el requirement "Puerta abierta a RAG sin implementacion" (spec de a02): el campo
`retrieval` es metadato declarativo inerte. Ausente -> ningun comportamiento; presente ->
solo reserva el contrato, sin invocar ningun adapter (no existe `RetrievalPort` en a02).

Se valida con dicts porque asi llega un Manifest en produccion: YAML -> dict -> validacion.
"""

from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from resultarai.core.manifests.skill import RetrievalConfig, SkillManifest


def _example_skill(**overrides: Any) -> dict[str, Any]:
    """Dict equivalente al YAML de ejemplo de docs/04-manifiestos.md (Skill Manifest)."""
    data: dict[str, Any] = {
        "id": "example_skill",
        "name": "Utilidades de Ejemplo",
        "status": "active",
        "version": "1.0.0",
        "description": (
            "Skill de ejemplo de fabrica: envuelve un paquete Agent Skill (SKILL.md) con "
            "utilidades genericas y expone, con gobernanza, sus tools permitidas."
        ),
        "skill_package": {
            "spec": "agent_skills",
            "ref": "example_utils",
            "path": "skills/example_utils/SKILL.md",
            "version": "1.0.0",
        },
        "execution": {
            "mode": "read_only",
            "graph": "default_skill_graph",
            "requires_human_approval": False,
        },
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


def test_skill_without_retrieval_is_valid() -> None:
    # Caso de fabrica: omitir `retrieval` por completo -> None -> sin comportamiento.
    payload = _example_skill()
    assert "retrieval" not in payload

    manifest = SkillManifest.model_validate(payload)

    assert manifest.retrieval is None


def test_declared_retrieval_is_inert_metadata() -> None:
    # Bloque `retrieval` tal cual el ejemplo normativo de docs/04-manifiestos.md.
    manifest = SkillManifest.model_validate(
        _example_skill(retrieval={"enabled": False, "source": None})
    )

    assert manifest.retrieval is not None
    assert isinstance(manifest.retrieval, RetrievalConfig)
    assert manifest.retrieval.enabled is False
    assert manifest.retrieval.source is None


def test_unknown_key_in_retrieval_rejected_by_strict_mode() -> None:
    with pytest.raises(ValidationError) as exc_info:
        SkillManifest.model_validate(
            _example_skill(retrieval={"enabled": False, "source": None, "index_url": "x"})
        )

    assert "index_url" in str(exc_info.value)


def test_retrieval_config_is_pure_data_without_adapter() -> None:
    # No exige ningun adapter: es un modelo de datos Pydantic puro (solo campos declarativos,
    # sin metodo de recuperacion ni referencia a un puerto/adapter). El propio import de este
    # modulo (solo stdlib + Pydantic, garantizado por import-linter) evidencia que cargar un
    # manifest con retrieval no introduce dependencias nuevas.
    assert issubclass(RetrievalConfig, BaseModel)
    assert set(RetrievalConfig.model_fields) == {"enabled", "source"}

    config = RetrievalConfig()
    assert config.enabled is False
    assert config.source is None

    # Ningun metodo de comportamiento (retrieve/search/port/adapter): es puro dato.
    behaviour = {"retrieve", "search", "query", "port", "adapter", "connect"}
    assert behaviour.isdisjoint(set(dir(config)))
