# ADR-0004 — Manifiestos declarativos como núcleo del dominio

- **Estado:** aceptado (2026-07-09)

## Contexto

En una plataforma agentic, la pregunta "¿dónde vive el dominio?" tiene una respuesta inusual: la lógica de negocio pesada está en el ERP, y lo que la plataforma gobierna es **qué agentes, skills, tools y políticas existen y qué tienen permitido hacer**. El blueprint v2.4 (§2.4.6, principio 14) exige que eso se declare en manifiestos versionados, no se hardcodee en el runtime.

## Decisión

Los **6 manifiestos** (Agent, Skill, Tool, Policy, Routing, Eval Template — ver [04-manifiestos.md](../04-manifiestos.md)) son el modelo de dominio del proyecto:

1. Viven como YAML en `manifests/` bajo Git (historia = auditoría de configuración).
2. Sus schemas Pydantic en `core/manifests/` son la definición canónica de los conceptos del dominio.
3. Se validan en CI (cada PR) y al arranque (fail-fast): schema + reglas cruzadas (referencias entre manifiestos existen y están activas).
4. Agregar/cambiar un agente, skill o tool = editar YAML. El runtime no se toca.
5. Ciclo de vida: `draft → validado → active → deprecated`; el kill switch es cambiar el status.

## Alternativas consideradas

1. **Configuración en código Python** (registros programáticos, decoradores) — rechazada: mezcla dominio con runtime, exige tocar código para cada skill nueva y dificulta auditar qué está habilitado.
2. **Configuración en base de datos con UI de administración** — pospuesta: útil a futuro (el blueprint contempla Git + Postgres); empezar por BD sin UI ni historia de cambios pierde el versionado gratuito de Git.
3. **Un solo manifiesto monolítico** — rechazada: acopla ciclos de vida distintos (una tool cambia más seguido que un agente) y rompe el mínimo privilegio por contrato.

## Consecuencias

- (+) El "qué existe y qué está permitido" es auditable con `git log`.
- (+) Los registries y el Policy Gate se testean con YAML de fixtures, sin infraestructura.
- (+) OpenSpec puede especificar cambios de capacidad como cambios de manifiesto, no de código.
- (−) Indirección: entender una skill requiere leer su YAML + su graph template → mitigado con el glosario y ejemplos completos en [04-manifiestos.md](../04-manifiestos.md).

## Fuentes

- Blueprint v2.4, §2.4.6 (Agentic Scaffolding Framework), principios 14-16, Patrón 12 — [referencia local](../referencias/arquitectura_plataformas_ia_internas_v2_4_agentic_scaffolding.md)
- Microsoft Multi-Agent Reference Architecture (registries + router + state store como componentes estándar) — https://microsoft.github.io/multi-agent-reference-architecture/docs/reference-architecture/Patterns.html
- Model Context Protocol (contrato estándar de tools) — https://modelcontextprotocol.io/
