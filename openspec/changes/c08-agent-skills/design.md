# Design — c08-agent-skills

## Context

`a02` define el Skill Manifest (envoltorio de gobernanza) y el `SkillRegistry`; `b06` aporta el Skill Router y el runtime de grafos. La spec oficial Agent Skills (agentskills.io/specification) fija el *contenido* de una skill: una carpeta con `SKILL.md` (frontmatter YAML `name`/`description` + cuerpo Markdown) más carpetas opcionales `scripts/`, `references/`, `assets/`, con divulgación progresiva en tres niveles y un campo experimental `allowed-tools`. `c08` conecta ambas cosas: carga y valida esos paquetes, aplica la divulgación progresiva y calcula el toolset ejecutable, respetando la regla dura 3 (tools solo vía skill, todo por el Policy Gate). No hay UI ni cliente MCP aquí.

## Goals / Non-Goals

**Goals:**

- Cargar y validar paquetes de skill conformes a la spec, referenciados por Skill Manifest `active`, con `core/` puro y el I/O en un adapter.
- Implementar la divulgación progresiva de 3 niveles integrada con el Skill Router.
- Definir la intersección `allowed-tools` × `tools` del manifiesto como único toolset ejecutable, sin romper la regla dura 3.
- Entregar una skill de ejemplo de fábrica genérica que ejercite el formato completo.

**Non-Goals:**

- Ejecución real de tools / cliente MCP (`c09`), builder UI (`d21`), skills de escritura ERP (Etapa P), hot-reload de skills en sesión.

## Decisions

1. **Ubicación de los paquetes: `manifests/skills/packages/<name>/`.** Los paquetes viven junto a los Skill Manifest, bajo `manifests/`, y el Skill Manifest los referencia por un campo `package` (path relativo, definido por el schema de `a02`). Alternativa: un `skills/` de primer nivel — descartada para mantener TODO artefacto declarativo bajo `manifests/` y una sola raíz que CI valida.

2. **Split hexagonal.** `core/skills/` posee el modelo `SkillPackage` (Pydantic), las reglas de validación y la función pura de intersección; `core/ports/` define un `SkillPackagePort` (`typing.Protocol`) con operaciones de descubrimiento y lectura por nivel (`discover`, `read_metadata`, `read_body`, `read_resource`). El adapter `adapters/skills_fs/` hace todo el I/O (recorrer carpetas, leer `SKILL.md` y archivos de apoyo, separar frontmatter YAML del cuerpo) y entrega datos crudos que `core/` valida. Alternativa: leer archivos desde `core/` — descartada, viola la regla 1 (core sin I/O ni frameworks).

3. **`allowed-tools` se resuelve contra el Tool Registry, no como patrones estilo Claude Code.** La spec marca `allowed-tools` como *experimental* y su ejemplo usa patrones (`Bash(git:*) Read`). En ResultarAI las tools son operaciones gobernadas con Tool Manifest e id; por tanto cada entrada de `allowed-tools` se interpreta como referencia a un id de tool del Tool Registry. El toolset ejecutable = `frozenset(package.allowed_tools) ∩ frozenset(manifest.tools)`. Esta es una **función pura** en `core/`; su resultado es lo ÚNICO que el runtime puede intentar ejecutar, y cada intento pasa igual por el Policy Gate. Divergencia de la spec anotada como "a verificar/afinar al implementar `c09`".

4. **Divulgación progresiva mapeada a los niveles del runtime.** Nivel 1 (metadatos `name`+`description` de skills `active`): la orquestación los inyecta en el contexto de sistema al construir el agente. Nivel 2 (cuerpo `SKILL.md`): el Skill Router (`b06`) invoca `read_body` al activar. Nivel 3 (archivos de apoyo): se leen vía `read_resource` solo cuando el cuerpo los referencia. Los niveles 2–3 nunca se precargan. La spec recomienda ~100 tokens de metadata y <5000 tokens / <500 líneas de cuerpo; adoptamos esos números como guía y convertimos el tope de metadata de descubrimiento en validación dura configurable.

5. **Skillset fijo por versión de agente.** El toolset/skillset se resuelve al cargar el agente desde `enabled_skills` + Skill Manifest `active` y queda inmutable en la sesión. Cambiar skills = nueva versión de manifiesto (`draft → validado → active`). Sin hot-reload: elimina una clase entera de fallos de seguridad (skill inyectada a mitad de sesión).

6. **Skill de ejemplo `report-formatting`.** Genérica, sin ERP: redacta/formatea informes. Incluye `SKILL.md` (frontmatter + cuerpo), un `references/` de apoyo (p. ej. plantilla de estructura de informe) y `allowed-tools` con el id de la tool de ejemplo de `c09`. Su Skill Manifest envolvente la referencia. Como `c09` aún no ejecuta tools, el escenario de intersección se verifica **estructuralmente** (el id entra al toolset resuelto) y la ejecución real se valida cuando `c09` esté archivado; los tests de `c08` usan un id de tool de referencia (stub) para el cálculo de intersección.

7. **Fijación de la spec.** Formato tomado de agentskills.io/specification (fetch 2026-07-09). Campos de frontmatter confirmados: `name` (req.), `description` (req.), `license`, `compatibility` (máx. 500 chars), `metadata` (mapa clave-valor), `allowed-tools` (experimental). La página no expone un número de versión explícito; se cita URL + fecha de fetch y ADR-0009. Opcionalmente, `skills-ref validate` (github.com/agentskills/agentskills) puede usarse como verificación externa complementaria — "a verificar al implementar".

## Risks / Trade-offs

- [Semántica de `allowed-tools` divergente entre la spec (patrones tipo Claude Code) y ResultarAI (ids de Tool Registry)] → Mitigación: se documenta el mapeo en el schema del Skill Manifest (`a02`) y se re-verifica la spec al implementar `c09`; el campo se trata como experimental.
- [Dependencia hacia adelante de la tool de ejemplo de `c09`] → Mitigación: la intersección es estructural y testeable con un id stub; el escenario de ejecución end-to-end de la skill de ejemplo queda verde recién con `c09` archivado.
- [La spec Agent Skills marca `allowed-tools` como experimental y puede cambiar] → Mitigación: campo fijado a la fecha de fetch, ADR-0009 registra la adopción y se re-consulta al implementar; comportamiento aislado tras el `SkillPackagePort`.
- [Inflación del presupuesto de contexto a medida que crecen las skills] → Mitigación: tope de metadata de descubrimiento validado en carga y en CI (fail-fast), no como recomendación blanda.

## Open Questions

- El valor concreto del tope de metadata de descubrimiento (tokens/caracteres) se fija al implementar, tomando ~100 tokens de la guía de la spec como punto de partida; no bloquea el diseño.
- La resolución final de `allowed-tools` (validación cruzada de que cada id existe y está `active` en el Tool Registry) se cierra en `c09`; `c08` valida solo la intersección estructural.
