"""Cargador YAML -> schema y Registries en memoria de los 6 Manifests declarativos."""

from resultarai.core.registries.cross_references import (
    DanglingReferenceError,
    validate_cross_references,
)
from resultarai.core.registries.loader import (
    AgentRegistry,
    EvalTemplateRegistry,
    ManifestLoadError,
    PolicyRegistry,
    Registries,
    RoutingRegistry,
    SkillRegistry,
    ToolRegistry,
    load_registries,
)
from resultarai.core.registries.registry import DuplicateManifestIdError, ManifestRegistry

__all__ = [
    "AgentRegistry",
    "DanglingReferenceError",
    "DuplicateManifestIdError",
    "EvalTemplateRegistry",
    "ManifestLoadError",
    "ManifestRegistry",
    "PolicyRegistry",
    "Registries",
    "RoutingRegistry",
    "SkillRegistry",
    "ToolRegistry",
    "load_registries",
    "validate_cross_references",
]
