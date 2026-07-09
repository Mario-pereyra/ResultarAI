# Proposal — c08-agent-skills

## Why

En la plataforma genérica "de fábrica" el Default Chat se especializa por la Skill activa, y su *contenido* debe seguir la spec oficial Agent Skills (paquete con `SKILL.md`, progressive disclosure) mientras la gobernanza permanece en el Skill Manifest ([docs/04](../../../docs/04-manifiestos.md), [ADR-0009](../../../docs/adr/)). Sin un cargador que descubra paquetes de skill, aplique la divulgación progresiva y calcule la intersección `allowed-tools`, el Skill Router (`b06`) no tiene qué activar y la regla dura 3 (tools solo vía skill) carece de sustrato en runtime.

## What Changes

- **Descubrimiento y carga** de paquetes de skill (carpetas con `SKILL.md`) referenciados por el Skill Manifest (`a02`): el manifiesto es el envoltorio de gobernanza (`status`, políticas, tools permitidas); el paquete es el contenido conforme a la spec Agent Skills.
- **Validación de paquetes**: frontmatter obligatorio (`name`, `description`), formato de `name` conforme a la spec (1–64 chars, minúsculas/dígitos/guiones, sin guion inicial/final ni dobles), `name` igual al directorio padre y al `id`/referencia del Skill Manifest, y tamaño de metadata (`name`+`description`) acotado para no inflar el contexto.
- **Progressive disclosure en 3 niveles**: los metadatos (`name`+`description`) de las skills ACTIVAS del agente entran al contexto de sistema; el cuerpo de `SKILL.md` se carga cuando el Skill Router activa la skill; los archivos de apoyo (`scripts/`, `references/`, `assets/`) se leen bajo demanda.
- **`allowed-tools`**: función pura que calcula la **intersección** entre las tools declaradas por el paquete (`allowed-tools`) y las permitidas por el Skill Manifest (`tools`) → el toolset ejecutable de la skill. Regla dura 3 INTACTA: las tools llegan SOLO vía la skill activa y cada ejecución pasa por el Policy Gate.
- **Skill de ejemplo de fábrica** (genérica, sin dominio ERP): una skill de redacción/formato de informes que demuestra frontmatter, cuerpo, un archivo de apoyo en `references/` y `allowed-tools` referenciando la tool de ejemplo de `c09`, con su Skill Manifest envolvente apuntando al paquete.

## Capabilities

### New Capabilities

- `agent-skills`: descubrimiento y carga de paquetes de skill, progressive disclosure, intersección `allowed-tools`, validación de paquetes y la skill de ejemplo de fábrica.

### Modified Capabilities

*(ninguna — `a02` define el schema del Skill Manifest con su referencia al paquete; `c08` lo consume sin cambiar sus requisitos. No hay specs previas en `openspec/specs/`.)*

## No-objetivos

- **Sin builder UI de skills** (`d21`): no hay editor visual ni publicación guiada; `c08` solo carga y valida paquetes ya versionados en Git.
- **Sin skills con escritura al ERP** (Etapa P): la skill de ejemplo es genérica y read-only; ninguna toca Protheus ni la ERP Safe Query API.
- **Sin carga de skills a mitad de sesión**: el skillset/toolset es fijo por versión de agente; habilitar una skill nueva exige una nueva versión de manifiesto (`draft → validado → active`), nunca hot-reload dentro de una sesión.
- **Sin cliente MCP ni ejecución real de tools** (`c09`): `c08` calcula y entrega el toolset ejecutable; la invocación MCP, su binding y la clasificación de riesgo las aporta `c09`.
- **No define el Skill Manifest schema (`a02`) ni el Skill Router (`b06`)**: los consume como dependencias ya especificadas.

## Bounded context afectado

- **`scaffolding`** (core): modelo `SkillPackage`, reglas de validación de paquetes, función pura de intersección `allowed-tools` y un nuevo port de carga de paquetes. Solo stdlib + Pydantic; sin frameworks.
- **`orchestration`** (core + adapters): la divulgación progresiva se integra con el Skill Router (`b06`) para inyectar metadatos de skills activas y cargar el cuerpo al activarse.
- **adapters**: `adapters/skills_fs/` (lector de paquetes de skill desde el filesystem) implementa el nuevo port; la lógica de I/O vive fuera de core.

## Impact

- **core**: `resultarai/core/skills/` (modelo `SkillPackage`, validación e intersección `allowed-tools`) y `resultarai/core/ports/` (nuevo port de carga de paquetes).
- **adapters**: `resultarai/adapters/skills_fs/` (loader de filesystem).
- **manifests**: `manifests/skills/packages/<name>/SKILL.md` (skill de ejemplo + archivo de apoyo) y un Skill Manifest de ejemplo (`manifests/skills/*.yaml`) que referencia el paquete.
- **Dependencias**: `a02` (Skill Manifest + `SkillRegistry`), `b06` (Skill Router y runtime de grafos), interfaz de la tool de ejemplo de `c09` (referenciada por `allowed-tools`, ejecutada en `c09`).
- **Referencia spec**: Agent Skills specification (agentskills.io/specification, revisión vigente al 2026-07-09) y ADR-0009 (adopción de specs oficiales, `a01`).
- **Referencia blueprint**: §2.4.6 "Agentic Scaffolding Framework" (skills como capacidad declarativa), citada, no copiada.
