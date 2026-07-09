"""Port de carga de paquetes Agent Skill (SkillPackagePort).

Define el protocolo para descubrir, leer metadata, cuerpo y recursos de paquetes
Agent Skill. El adapter concreto (filesystem, red, etc.) implementa este protocolo;
`core/` nunca hace I/O directo.
"""

from __future__ import annotations

from typing import Any, Protocol

__all__ = ["SkillPackagePort"]


class SkillPackagePort(Protocol):
    """Protocolo para cargar paquetes Agent Skill (SKILL.md + archivos de apoyo).

    Cada método corresponde a un nivel de la divulgación progresiva:
    - `discover`: lista los paquetes disponibles (Nivel 0 / arranque).
    - `read_metadata`: frontmatter YAML de SKILL.md (Nivel 1).
    - `read_body`: cuerpo Markdown de SKILL.md (Nivel 2).
    - `read_resource`: archivo de apoyo (Nivel 3).
    """

    def discover(self, packages_dir: str) -> list[str]:
        """Descubre los paquetes disponibles en `packages_dir`.

        Retorna los nombres (directorio) de paquetes que contienen un `SKILL.md`.
        """
        ...

    def read_metadata(self, package_name: str) -> dict[str, Any]:
        """Lee el frontmatter YAML de `SKILL.md` del paquete `package_name`.

        Retorna un diccionario con los campos del frontmatter (name, description,
        allowed-tools, etc.) sin el cuerpo Markdown.
        """
        ...

    def read_body(self, package_name: str) -> str:
        """Lee el cuerpo Markdown de `SKILL.md` del paquete `package_name`.

        Retorna el contenido después del frontmatter YAML (delimitado por `---`).
        """
        ...

    def read_resource(self, package_name: str, resource_path: str) -> str:
        """Lee un archivo de apoyo del paquete `package_name`.

        `resource_path` es relativo al directorio del paquete (p. ej.
        `references/report-template.md`). Solo se permite leer desde
        `references/`, `scripts/` y `assets/`.
        """
        ...
