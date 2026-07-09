# 01 — Visión y Alcance

> Última actualización: 2026-07-09

## Qué es ResultarAI

ResultarAI es la **plataforma interna de IA de Resultar Soluciones**, partner oficial de TOTVS en Bolivia. Es un chat gobernado (Default Chat) que puede responder consultas, activar capacidades aprobadas (skills) y —en el futuro— delegar a agentes especializados, para consultar sistemas internos y de clientes (empezando por el ERP Protheus) de forma **segura, trazable y sin acceso directo a bases de datos**.

El problema que resuelve: hoy el conocimiento operativo (consultas al ERP, parámetros SX6, estados de pedidos, documentación TOTVS) requiere acceso manual, conocimiento técnico de Protheus o escalamiento a consultores. ResultarAI lo expone a través de un chat con permisos, políticas y auditoría.

## Usuarios objetivo

1. **Fábrica de software (juniors)** — consultas técnicas de Protheus, diagnóstico asistido, consulta de diccionarios y parámetros.
2. **Consultores (seniors y semi-seniors)** — consultas rápidas al ERP de clientes sin abrir SQL ni SmartClient.
3. **Consultoras funcionales** — verificación de datos de negocio y estados de procesos durante análisis.

## Alcance del MVP

El MVP se limita a tres piezas, en este orden:

1. **Default Chat** funcional: responde preguntas generales y entiende intención.
2. **Policy Gate** operativo: deny-by-default; toda acción pasa por él desde el día uno.
3. **Una (1) skill ERP de ejemplo**: consulta read-only contra la ERP Safe Query API (p. ej. consultar cliente o parámetro SX6), demostrando el flujo completo Chat → Skill → Tool → Policy Gate → API → respuesta trazada.

Todo lo demás del blueprint (multiagente, evals reales, FinOps completo, Edge Connector) llega por fases — ver [07-roadmap.md](07-roadmap.md).

## No-objetivos (explícitos)

- **No reemplaza a Protheus** ni a sus interfaces nativas (SIGAMDI, SIGACFG, APSDU). Es una capa de consulta y asistencia.
- **No ejecuta SQL libre, nunca.** Toda consulta al ERP pasa por la ERP Safe Query API con allowlist de tablas/campos y plantillas de consulta. Regla alineada con la matriz de soluciones autorizadas de la empresa (interfaces nativas / APSDU / MsExecAuto).
- **No escribe en el ERP en el MVP.** Las operaciones de escritura (vía MsExecAuto) son fase futura y requerirán aprobación humana (HITL).
- **No es multiagente el día uno.** Un Default Chat + skills; los agentes especializados se agregan por manifiesto cuando existan casos reales.
- **No construye infraestructura especulativa**: nada de control plane distribuido, colas de eventos ni celdas hasta que un problema concreto lo justifique.

## Relación con el blueprint v2.4

El documento [referencias/arquitectura_plataformas_ia_internas_v2_4_agentic_scaffolding.md](referencias/arquitectura_plataformas_ia_internas_v2_4_agentic_scaffolding.md) es la **referencia aspiracional**: describe el estado objetivo completo (13 capas, componentes, métricas, patrones).

**Regla de jerarquía documental:**

- `docs/` (este directorio) = **lo adoptado y vigente**. Si hay conflicto, manda `docs/`.
- El blueprint = referencia. Se **cita por sección** (p. ej. "blueprint §2.4.6"), nunca se copia su contenido a los docs.
- El contexto de la empresa vive en [referencias/contexto-resultar-soluciones.md](referencias/contexto-resultar-soluciones.md).

## Criterio de éxito del MVP

Un desarrollador de la fábrica pregunta en el chat por un cliente o un parámetro del ERP de un cliente autorizado y recibe la respuesta correcta, enmascarada según política, con la traza completa (usuario, skill, tool, modelo, costo, decisión del Policy Gate) visible en Langfuse.
