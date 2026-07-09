"""Cargador YAML -> schema: lee `manifests/` y construye los 6 Registries tipados.

Layout esperado bajo el directorio `manifests/` que se recibe como parametro (la ruta por
defecto la resuelve `app/`, nunca `core/`, ver regla dura 1):

    manifests/
        agents/*.yaml      -> AgentManifest
        skills/*.yaml      -> SkillManifest
        tools/*.yaml       -> ToolManifest
        policies/*.yaml    -> PolicyManifest
        routing/*.yaml     -> RoutingManifest
        evals/*.yaml       -> EvalTemplateManifest

Cada subdirectorio ausente se trata como vacio (Registry sin manifiestos de ese tipo), no
como error: un `manifests/` parcial (p. ej. en un test) es valido. Solo carga, valida y
cataloga: cero ejecucion, cero red, cero imports de adapters (LiteLLM, MCP, LangGraph).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

import yaml
from pydantic import ValidationError

from resultarai.core.manifests import (
    AgentManifest,
    BaseManifest,
    EvalTemplateManifest,
    PolicyManifest,
    RoutingManifest,
    SkillManifest,
    ToolManifest,
)
from resultarai.core.registries.registry import ManifestRegistry

__all__ = [
    "AgentRegistry",
    "EvalTemplateRegistry",
    "ManifestLoadError",
    "PolicyRegistry",
    "Registries",
    "RoutingRegistry",
    "SkillRegistry",
    "ToolRegistry",
    "load_registries",
]

# Alias tipados: un unico generico (`ManifestRegistry[M]`) parametrizado por cada schema,
# en lugar de 6 clases duplicadas.
AgentRegistry = ManifestRegistry[AgentManifest]
SkillRegistry = ManifestRegistry[SkillManifest]
ToolRegistry = ManifestRegistry[ToolManifest]
PolicyRegistry = ManifestRegistry[PolicyManifest]
RoutingRegistry = ManifestRegistry[RoutingManifest]
EvalTemplateRegistry = ManifestRegistry[EvalTemplateManifest]

_YAML_SUFFIXES: Final = (".yaml", ".yml")


class ManifestLoadError(Exception):
    """Un archivo de `manifests/` no es YAML valido o no cumple su schema Pydantic."""


def _yaml_files(directory: Path) -> list[Path]:
    """Rutas de YAML en `directory`, orden estable. Directorio ausente -> lista vacia."""
    if not directory.is_dir():
        return []
    return sorted(
        path for path in directory.iterdir() if path.is_file() and path.suffix in _YAML_SUFFIXES
    )


def _load_manifest[M: BaseManifest](path: Path, schema: type[M]) -> M:
    """Parsea `path` como YAML y lo valida contra `schema`.

    Cualquier fallo (sintaxis YAML rota, contenido que no es un mapeo, o violacion del
    schema Pydantic) se re-lanza como `ManifestLoadError` nombrando el archivo y la causa.
    """
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ManifestLoadError(f"{path}: invalid YAML syntax: {exc}") from exc

    if not isinstance(raw, dict):
        raise ManifestLoadError(
            f"{path}: expected a YAML mapping at the top level, got {type(raw).__name__}"
        )

    try:
        return schema.model_validate(raw)
    except ValidationError as exc:
        raise ManifestLoadError(f"{path}: manifest validation failed: {exc}") from exc


def _load_registry[M: BaseManifest](directory: Path, schema: type[M]) -> ManifestRegistry[M]:
    """Carga todos los YAML de `directory` contra `schema` y construye su Registry.

    `ManifestRegistry` rechaza `id` duplicados dentro del mismo tipo al construirse.
    """
    manifests = [_load_manifest(path, schema) for path in _yaml_files(directory)]
    return ManifestRegistry(manifests)


@dataclass(frozen=True, slots=True)
class Registries:
    """Los 6 Registries tipados construidos desde un directorio `manifests/`."""

    agents: AgentRegistry
    skills: SkillRegistry
    tools: ToolRegistry
    policies: PolicyRegistry
    routing: RoutingRegistry
    evals: EvalTemplateRegistry


def load_registries(manifests_dir: Path) -> Registries:
    """Construye los 6 Registries leyendo los subdirectorios de `manifests_dir`.

    Subdirectorios esperados: `agents/`, `skills/`, `tools/`, `policies/`, `routing/`,
    `evals/`. `manifests_dir` es un parametro explicito (nunca una ruta absoluta harcodeada en
    `core/`): los tests lo apuntan a `tmp_path`; la resolucion del default de produccion es
    responsabilidad de `app/`.
    """
    return Registries(
        agents=_load_registry(manifests_dir / "agents", AgentManifest),
        skills=_load_registry(manifests_dir / "skills", SkillManifest),
        tools=_load_registry(manifests_dir / "tools", ToolManifest),
        policies=_load_registry(manifests_dir / "policies", PolicyManifest),
        routing=_load_registry(manifests_dir / "routing", RoutingManifest),
        evals=_load_registry(manifests_dir / "evals", EvalTemplateManifest),
    )
