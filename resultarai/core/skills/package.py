"""Modelo SkillPackage: representación en dominio del paquete Agent Skill.

Campos del frontmatter YAML de `SKILL.md` (spec agentskills.io/specification):
- `name` (obligatorio): identificador en minúsculas/dígitos/guiones, 1-64 chars.
- `description` (obligatorio): descripción breve de la skill.
- `license` (opcional): licencia del paquete.
- `compatibility` (opcional, máx 500 chars): nota de compatibilidad.
- `metadata` (opcional): mapa clave-valor libre.
- `allowed_tools` (experimental): lista de ids de tools que la skill puede usar.

Campos adicionales del modelo (no del frontmatter):
- `body`: contenido Markdown del SKILL.md después del frontmatter.
- `resources`: rutas relativas de archivos de apoyo descubiertos.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["SkillPackage"]


class SkillPackage(BaseModel):
    """Representación en dominio de un paquete Agent Skill (SKILL.md + archivos de apoyo).

    Los campos del frontmatter se mapean 1:1 a la spec (agentskills.io). `body` y
    `resources` son campos de modelo que el adapter llena al cargar el paquete.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    # --- Frontmatter fields ---
    name: Annotated[str, Field(min_length=1, max_length=64)]
    description: Annotated[str, Field(min_length=1)]
    license: str | None = None
    compatibility: Annotated[str, Field(max_length=500)] | None = None
    metadata: dict[str, str] | None = None
    allowed_tools: list[str] = Field(default_factory=list)

    # --- Non-frontmatter fields ---
    body: str = ""
    resources: list[str] = Field(default_factory=list)
