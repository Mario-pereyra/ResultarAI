# ADR-0009 — Adopción de specs oficiales: Agent Skills (skills) y MCP (tools)

- **Estado:** aceptado (2026-07-09)

## Contexto

El intento anterior de `design/` (2026-06) diseñó un formato de paquete de skill propio (instrucciones + ejemplos + tools embebidos) y un bridge de tools a medida, `tat-mcp`, para conectar con Protheus. El pivote 2026-07-09 especifica el producto completo por adelantado y separa "plataforma genérica de fábrica" (Etapas A–E) de "personalización Protheus" (Etapa P, [docs/07-roadmap.md](../07-roadmap.md)). Mantener formatos propios para skills y tools significaría diseñar, documentar y versionar dos contratos que el ecosistema ya estandarizó en 2025: **Agent Skills** (skills como conjuntos de instrucciones + recursos con progressive disclosure) y **Model Context Protocol** (tools como servidores con contrato de descubrimiento e invocación). El manifiesto de dominio de este proyecto ([docs/04-manifiestos.md](../04-manifiestos.md), [ADR-0004](0004-manifiestos-declarativos-como-dominio.md)) ya definía Skill Manifest y Tool Manifest como los contratos de gobernanza — quedaba decidir si el **contenido técnico** que esos manifiestos describen es un formato propio o una spec pública ya adoptada por la industria.

## Decisión

Adoptar las specs oficiales como el artefacto técnico, y mantener los manifiestos de este proyecto como **envoltorio de gobernanza** sobre ellas:

1. **Skills → spec Agent Skills** (agentskills.io, formato `SKILL.md` con progressive disclosure y frontmatter `allowed-tools`). El change `c08-agent-skills` implementa el descubrimiento de paquetes `SKILL.md`; el `default_chat` se especializa por skill activa. La regla dura 3 (tools solo vía skill) se mantiene intacta: `allowed-tools` en el `SKILL.md` es una restricción adicional, no un reemplazo del Policy Gate.
2. **Tools → spec MCP, revisión 2025-11-25** (modelcontextprotocol.io). El change `c09-mcp-tools` fija esta revisión operativamente (cliente MCP + Tool Registry + clasificación lectura/escritura/riesgo fija por versión). Fijar la revisión es deliberado: MCP es una spec viva y este proyecto no sigue "latest" automáticamente — subir de revisión es un cambio explícito (PR + change de OpenSpec), igual que cambiar la clasificación de riesgo de una tool.
3. **El Skill Manifest y el Tool Manifest de `docs/04-manifiestos.md` pasan a ser envoltorio de gobernanza**, no el formato técnico en sí: el Skill Manifest referencia un paquete `SKILL.md` (ubicación, versión, estado del ciclo de vida) y agrega lo que la spec no cubre —`risk`, `output_policy`, `evals`, pertenencia a un tenant—; el Tool Manifest referencia un servidor MCP (o binding OpenAPI/ERP Safe Query API) de la misma forma. Esto no cambia ADR-0004: los 6 manifiestos siguen siendo el modelo de dominio versionado en YAML; cambia qué describen sus campos técnicos.
4. El bridge propio `tat-mcp` del intento anterior no se lleva al pivote: la conectividad Protheus se rediseña en Etapa P como un servidor MCP (o binding OpenAPI vía ERP Safe Query API) que cumple la misma spec MCP adoptada aquí, no un protocolo aparte.

## Alternativas consideradas

1. **Mantener el paquete de skill propio y el bridge `tat-mcp`** (lo que traía `design/`) — rechazada: mantener dos specs propias (formato de skill + protocolo de tool) es carga de diseño y documentación permanente para resolver un problema que la industria ya estandarizó en 2025; además fragmenta el ecosistema de tooling (editores, validadores, examples) que ya existe alrededor de Agent Skills y MCP.
2. **Formato propio de skill, pero tools ya en MCP** (adopción parcial) — rechazada: la asimetría no se justifica; Agent Skills y MCP están diseñados para complementarse (`allowed-tools` de una skill referencia tools expuestas vía MCP), adoptar solo una mitad pierde esa integración nativa.
3. **Esperar a que las specs maduren más antes de adoptarlas** — rechazada: Agent Skills y MCP (revisión 2025-11-25) ya tienen implementaciones de referencia y adopción multi-vendor; el proyecto es greenfield y no carga con una decisión anterior que migrar — el costo de adoptar ahora es menor que el de re-litigar el formato después con contenido ya construido.
4. **Seguir "latest" de MCP sin fijar revisión** — rechazada: una spec viva sin ancla de versión rompe la regla dura de clasificación de riesgo fija por versión (regla operativa de `c09-mcp-tools`); fijar la revisión 2025-11-25 y subirla solo vía PR explícito da control de cambio sobre algo con implicancia de seguridad.

## Consecuencias

- (+) Se elimina diseño y mantenimiento de dos formatos propios; el proyecto hereda tooling, ejemplos y validadores del ecosistema Agent Skills / MCP.
- (+) El envoltorio de gobernanza (manifiestos) queda más delgado: solo agrega lo que la spec pública no resuelve (riesgo, políticas de salida, ciclo de vida, pertenencia a tenant), coherente con ADR-0004.
- (+) La personalización Protheus de Etapa P se construye como un servidor MCP estándar, reutilizable con cualquier cliente MCP futuro, no como protocolo cerrado.
- (−) Este proyecto queda acoplado a la evolución de dos specs externas fuera de su control → mitigado: se fija revisión explícita de MCP y el Skill/Tool Manifest actúa de capa de indirección — migrar de revisión o de spec es cambiar el envoltorio, no reescribir el dominio.
- (−) Progressive disclosure de Agent Skills y el modelo de permisos de MCP deben mapearse al Policy Gate propio (deny-by-default) sin asumir que la spec ya impone ese nivel de gobernanza → asumido como trabajo explícito de `c08-agent-skills`/`c09-mcp-tools`, no un gap oculto.

## Fuentes

- Agent Skills — especificación y formato `SKILL.md` — https://agentskills.io/
- Model Context Protocol — especificación, revisión 2025-11-25 — https://modelcontextprotocol.io/specification/2025-11-25
- Model Context Protocol — sitio y documentación general — https://modelcontextprotocol.io/
- `docs/04-manifiestos.md` — Skill Manifest y Tool Manifest (envoltorio de gobernanza)
- [ADR-0004](0004-manifiestos-declarativos-como-dominio.md) — manifiestos declarativos como núcleo del dominio (no se revierte, se reinterpreta)
- `docs/07-roadmap.md` — pivote 2026-07-09, tabla "Cambios adoptados" (filas "Skills" y "Tools") y changes `c08-agent-skills`, `c09-mcp-tools`
