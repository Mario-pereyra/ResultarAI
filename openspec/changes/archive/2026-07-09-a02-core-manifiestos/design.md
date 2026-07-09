# Design — a02-core-manifiestos

## Context

`a01` dejó `core/` importable y las fronteras verificadas por import-linter, pero sin lógica de dominio. Este change escribe el corazón del dominio (`scaffolding`, blueprint §2.4.6): los schemas Pydantic de los 6 Manifests y sus Registries en memoria. Es un contrato transversal: `a03` (Policy Gate, ports), `b06` (runtime de grafos), `c08` (Agent Skills) y `c09` (MCP tools) consumen estos schemas. El pivote 2026-07-09 redefine dos Manifests: Skill como envoltorio de gobernanza de un paquete Agent Skill (`SKILL.md`) y Tool como referencia a un MCP server, con clasificación fija por versión. La restricción dura es que todo esto vive en `core/` sin importar frameworks (solo stdlib + Pydantic).

## Goals / Non-Goals

**Goals:**

- Los 6 Manifests como schemas Pydantic v2 en strict mode, con sus invariantes de dominio (regla de oro, deny-by-default, plan-then-execute) codificadas en el schema, no en el runtime.
- Registries en memoria que cargan YAML, validan referencias cruzadas, aplican el ciclo de vida y consultan por status — puros, sin ejecutar Tools ni modelos.
- Validación por CLI, fail-fast al arranque y en CI, con un único camino de validación reutilizado.
- Manifiestos de fábrica de ejemplo que validan verdes en CI y sirven de referencia normativa.

**Non-Goals:**

- Policy Gate, `AuditEvent`, ports y RAG real (todo en `a03` o posterior).
- Ejecución: cargar LangGraph/LiteLLM/Langfuse/MCP, o parsear paquetes `SKILL.md` reales.
- Persistencia en Postgres de los Registries (llega en `b04`; aquí es memoria + Git).

## Decisions

1. **Pydantic v2 strict mode como frontera de validación.** Cada Manifest es un `BaseModel` con `model_config = ConfigDict(strict=True, extra="forbid")`: rechaza campos desconocidos y coerciones implícitas, de modo que un YAML mal escrito falla en carga, no en runtime. Alternativa descartada: dataclasses + validación manual — reinventaría lo que Pydantic ya da y violaría la mejor práctica del stack (docs/05). Pydantic es la única dependencia no-stdlib permitida en `core/`.

2. **Las invariantes de dominio viven en el schema, no en el runtime.** La regla de oro (`can_execute_tools_directly: false`, `tool_access_policy.mode: deny_by_default`), el rechazo de SQL libre y la exigencia de plan-then-execute para Skills que tocan el ERP se codifican como validadores Pydantic (`model_validator`). Alternativa descartada: validarlas en el Policy Gate (`a03`) — llegaría tarde; un Manifest inválido no debe siquiera cargarse.

3. **Versionado semver por Manifest, con clasificación de Tool fija por versión.** Cada Manifest declara `version` semver; para el Tool Manifest, `operation_type` (lectura/escritura) y `risk.level` quedan atados a esa versión: cambiarlos exige nueva versión (un PR), nunca mutación en runtime. Esto materializa la regla dura de `c09` ("cambiar la clasificación = PR") desde el schema. Alternativa descartada: clasificación mutable por configuración — abriría un vector de escalada de privilegios silenciosa.

4. **Skill Manifest = envoltorio de gobernanza; Tool Manifest = referencia a MCP server.** El Skill Manifest referencia un paquete Agent Skill (agentskills.io: `SKILL.md` + frontmatter, progressive disclosure) por id/versión y aporta solo la capa de gobernanza (status, Tools permitidas, policies); no duplica el cuerpo de la Skill. El Tool Manifest referencia un MCP server + `tool_name`. El descubrimiento/parseo real de esos artefactos es de `c08`/`c09`; aquí solo se referencian por identificador. Alternativa descartada: schema propio que embeba el contenido de la Skill — rompe la spec oficial y duplica la fuente de verdad.

5. **Registries en memoria y puros.** Se construyen desde `manifests/` en el arranque y en el CLI; validan referencias cruzadas (Agent→Skill, Skill→Tool, *→Eval/Policy/Routing) y rechazan referencias colgantes o a Manifests no `active`. No importan adapters (verificado por import-linter). Postgres como fuente en producción (blueprint §2.4.6, "Git + Postgres") se difiere a `b04`; Git es la fuente ahora.

6. **Ciclo de vida por `status`; kill switch = cambiar `status`.** `draft → validated → active → deprecated`. Solo `active` es invocable; `draft` no se carga; `deprecated` permanece por trazabilidad. Apagar algo es moverlo a `deprecated`, nunca borrar el YAML — preserva la historia (coherente con append-only del producto). Alternativa descartada: flag booleano `enabled` — pierde la distinción draft/validated y la trazabilidad del deprecated.

7. **Un solo camino de validación, tres disparadores.** La misma función de validación se invoca desde el CLI (uv), el arranque fail-fast y el job de CI. Evita divergencia entre "lo que valida CI" y "lo que valida el arranque". Alternativa descartada: validadores separados por contexto — garantiza drift.

8. **Puerta abierta a RAG sin implementación.** Campo `retrieval` opcional en los schemas que aplican; ausente = sin comportamiento; presente = metadato declarativo sin adapter. Reserva el contrato para `RetrievalPort` (`a03`) sin implementar RAG (principio de la Etapa P).

## Risks / Trade-offs

- [Invariantes duras en el schema podrían bloquear casos legítimos futuros] → Mitigación: las invariantes codificadas son las reglas duras no negociables (regla de oro, deny-by-default, no-SQL-libre); cualquier flexibilización requiere ADR, no un parche.
- [Schemas de `a02` y ejemplos YAML de `docs/04` podrían divergir] → Mitigación: los manifiestos de fábrica de ejemplo son los mismos que ilustran `docs/04`; su validación en CI detecta la divergencia (tarea 1.4 de `a01` los alinea).
- [Referencia a specs oficiales (Agent Skills/MCP) que aún evolucionan] → Mitigación: este change solo referencia por identificador/versión; el binding real y la revisión fijada son de `c08`/`c09`, que absorben cambios de spec sin tocar estos schemas.
- [Registries en memoria no escalan a multi-instancia] → Mitigación: aceptable ahora (Git es la fuente); `b04` introduce Postgres cuando haya estado compartido.

## Migration Plan

Change greenfield sobre `core/` vacío: no hay datos ni contratos previos que migrar. Despliegue = merge del PR con CI en verde (schemas + Registries + manifiestos de fábrica validando). Rollback = revertir el PR; al no existir consumidores aún (Policy Gate y runtime llegan en `a03`+), no hay estado que restaurar.

## Open Questions

*(ninguna — las specs oficiales Agent Skills/MCP se fijan en `c08`/`c09`; la persistencia Postgres en `b04`; los ports y RAG en `a03`)*
