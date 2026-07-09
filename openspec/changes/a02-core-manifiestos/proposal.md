# Proposal — a02-core-manifiestos

## Why

Los manifiestos son el núcleo del dominio ([ADR-0004](../../../docs/adr/0004-manifiestos-declarativos-como-dominio.md)): sin sus schemas Pydantic y sus Registries en `core/`, ningún change posterior (Policy Gate en `a03`, runtime de grafos en `b06`, Agent Skills en `c08`, MCP tools en `c09`) tiene un contrato validado sobre el que apoyarse. El esqueleto de `a01` dejó `core/` importable pero sin lógica; este change materializa el andamiaje declarativo del blueprint §2.4.6 (principio 14): agregar o cambiar un Agent, Skill o Tool debe ser editar YAML versionado y validado, nunca tocar el runtime.

## What Changes

- Se definen los schemas Pydantic v2 (strict mode) de los 6 Manifests en `core/manifests/`: Agent, Skill, Tool, Policy, Routing y Eval Template, con sus invariantes de dominio y versionado semver.
- El Skill Manifest pasa a ser el **envoltorio de gobernanza** de un paquete conforme a la spec oficial Agent Skills (carpeta con `SKILL.md` + frontmatter `name`/`description`, progressive disclosure): referencia el paquete por `id`, versión, `status`, tools permitidas y policies, sin duplicar el contenido de la skill.
- El Tool Manifest referencia un MCP server (spec oficial MCP) + nombre de tool + clasificación lectura/escritura + nivel de riesgo, **fijos por versión** (cambiarlos exige un PR).
- Se añade un campo opcional de retrieval en los schemas que aplican (puerta abierta a RAG) **sin implementar nada** — coherente con `RetrievalPort` diferido a `a03`.
- Se implementan los Registries en memoria (`AgentRegistry`, `SkillRegistry`, `ToolRegistry` y los de Policy/Routing/Eval) que cargan los YAML desde `manifests/`, validan referencias cruzadas y exponen consulta por `status`.
- Se codifica el ciclo de vida `draft → validated → active → deprecated`; el kill switch es cambiar `status` (no borrar el manifiesto).
- Se añade validación por CLI y validación fail-fast al arranque, integrada en CI sobre cada PR.
- Se crean los manifiestos de fábrica de ejemplo: Agent `default_chat` (sin nombre comercial, general, `can_execute_tools_directly: false`), 1 Skill de ejemplo, 1 Tool de ejemplo, policies genéricas (deny-by-default + allow de lecturas de ejemplo), 1 Routing default y 1 Eval Template placeholder.

## Capabilities

### New Capabilities

- `manifest-schemas`: los 6 contratos declarativos como schemas Pydantic v2 strict, sus campos obligatorios, invariantes y versionado semver.
- `manifest-registries`: carga de YAML desde `manifests/`, validación de referencias cruzadas, ciclo de vida y consulta por `status`, más los manifiestos de fábrica de ejemplo.
- `manifest-validation`: CLI de validación, fail-fast al arranque y verificación en CI de todos los manifiestos.

### Modified Capabilities

*(ninguna — `openspec/specs/` está vacío; no existen specs previas)*

## No-objetivos

- Ningún Policy Gate ni `AuditEvent`: la evaluación de policies llega en `a03-core-gobernanza`.
- Ningún port (`LLMPort`, `ToolPort`, `TracePort`, `StatePort`, `PolicyPort`, `RetrievalPort`): se definen en `a03`.
- Ninguna ejecución real: no se carga LangGraph, LiteLLM, Langfuse ni un cliente MCP (llegan en `b05`–`c09`); los Registries solo cargan y validan, no ejecutan.
- No se implementa RAG: el campo de retrieval queda declarado y opcional, sin adapter.
- No se descubren ni parsean paquetes `SKILL.md` reales (eso es `c08`); el Tool Manifest solo referencia el MCP server por identificador, sin conectar (eso es `c09`).
- Ninguna persistencia en Postgres: los Registries son en memoria (Postgres llega en `b04`).

## Bounded context afectado

`scaffolding` (blueprint capas 3 y 4), dentro de `core/`: manifiestos, registries y validación de schemas — el núcleo del dominio. Los schemas y registries no importan ningún framework (solo stdlib + Pydantic), conforme a la regla de dependencia de [docs/02-arquitectura.md](../../../docs/02-arquitectura.md).

## Impact

- `resultarai/core/manifests/`: nuevos schemas Pydantic de los 6 Manifests y sus Registries.
- `manifests/{agents,skills,tools,policies,routing,evals}/`: manifiestos de fábrica de ejemplo (YAML).
- `resultarai/app/`: entrypoint de validación fail-fast al arranque y comando CLI de validación.
- `tests/core/` y `tests/contracts/`: tests de schemas, invariantes, referencias cruzadas, ciclo de vida y validación de los manifiestos de ejemplo.
- `.github/workflows/ci.yml`: nuevo job que valida los manifiestos en cada PR.
- Referencia del blueprint: §2.4.6 (Agentic Scaffolding Framework), principios 14 (andamiaje declarativo) y 16 (evals preparadas, no definidas).
