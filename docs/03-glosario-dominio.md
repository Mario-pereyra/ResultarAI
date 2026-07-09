# 03 — Glosario del Dominio (Lenguaje Ubicuo)

> Última actualización: 2026-07-09
> Regla: estos son los únicos nombres válidos para estos conceptos, en docs, specs, código y prompts. **Sin sinónimos.**

## Reglas de nombrado

- **Código e identificadores: inglés** (`SkillManifest`, `PolicyGate`, `deny_by_default`).
- **Docs, specs de OpenSpec y commits: español**, usando los términos técnicos en su forma original.
- Si un concepto nuevo aparece, se agrega aquí ANTES de usarse en código o specs.

## Términos del Agentic Scaffolding

| Término | Nombre en código | Definición |
|---|---|---|
| **Agent** | `Agent`, `AgentManifest` | Unidad orquestadora con propósito, skills habilitadas, límites y políticas. El único del MVP es el **Default Chat**. |
| **Default Chat** | `default_chat` | Agente principal de entrada. Responde directo, activa skills o delega. **Nunca ejecuta tools directamente.** |
| **Skill** | `Skill`, `SkillManifest` | Capacidad reutilizable que agrupa intención, prompts, tools permitidas, restricciones y política de salida. Única vía de acceso a tools. |
| **Tool** | `Tool`, `ToolManifest` | Herramienta técnica concreta (una operación) expuesta vía un adapter: MCP, OpenAPI/REST, Edge Connector. |
| **Manifest** | `*Manifest` | Contrato declarativo YAML, versionado en Git, validado contra schema Pydantic antes de cargarse al runtime. |
| **Registry** | `AgentRegistry`, `SkillRegistry`, `ToolRegistry` | Catálogo en memoria construido desde los manifiestos validados; resuelve qué existe y qué está activo. |
| **Policy** | `Policy`, `PolicyManifest` | Regla de ejecución declarativa: read-only, requiere aprobación, bloqueado, local-only, etc. |
| **Policy Gate** | `PolicyGate` | Función pura que autoriza o bloquea cada acción (usuario, cliente, skill, tool, riesgo) → permitir / bloquear / escalar. Deny-by-default. |
| **Skill Router** | `SkillRouter` | Decide si el Default Chat responde directo, activa una skill o delega a un agente. |
| **Route** | `RoutingManifest` | Regla declarativa de selección de skill o delegación. |
| **Graph Template** | `graph_templates/` | Plantilla LangGraph reutilizable: respuesta directa, tool call, plan-then-execute, HITL, error handling. |
| **Eval Placeholder** | `EvalTemplateManifest` | Espacio reservado para evaluación futura de un agente/skill/tool. Obligatorio desde el día uno; sin datasets reales todavía. |
| **Port** | `core/ports/` | Interfaz (`Protocol`) que el núcleo define y un adapter implementa: `LLMPort`, `ToolPort`, `TracePort`, `PolicyPort`, `StatePort`. |
| **Adapter** | `adapters/` | Implementación de un port contra una tecnología concreta. Traduce, no decide. |
| **HITL** | `requires_human_approval` | Human-in-the-loop: aprobación humana previa para acciones de riesgo. |
| **Audit Log** | `AuditEvent` | Registro append-only e inmutable de decisiones del Policy Gate y tool calls. |

## Términos de conectividad

| Término | Definición |
|---|---|
| **ERP Safe Query API** | API REST (OpenAPI 3.1) desplegada junto al Protheus de cada cliente. Traduce consultas permitidas a operaciones internas. Allowlist de tablas/campos + plantillas de consulta. **Prohíbe SQL libre.** |
| **Edge Connector** | Cliente Windows que ejecuta tools aprobadas dentro de la red del usuario aprovechando su VPN activa. Fase transitoria (blueprint patrón 10). |
| **Service Identity** | Identidad técnica (no personal) con la que un conector accede a un sistema. Estado objetivo; mientras no exista por cliente, opera el Edge Connector. |
| **Tenant** | Cliente de Resultar (Totalpec, Unión, Inbolsa, Maprial, Lafage…) o el proyecto interno `Resultar`. Aísla permisos, memoria, caché y trazas. |

## Términos Protheus (mínimos para entender las skills ERP)

| Término | Definición |
|---|---|
| **Protheus** | ERP de TOTVS; producto principal que implementa Resultar. |
| **AppServer** | Servidor de aplicaciones de Protheus; procesa la lógica y las sesiones. |
| **RPO** | Repositorio de Objetos: archivo compilado con las rutinas estándar y customizadas. |
| **DBAccess** | Middleware obligatorio entre AppServer y MS SQL Server. Nada consulta la base directo. |
| **Tablas SX** | Metadatos/diccionarios del sistema (SX1 preguntas, SX2 tablas, SX3 campos, SX6 parámetros, SX7 gatillos…). |
| **SC5 / SC6** | Encabezado / ítems de pedidos de venta. Ejemplo canónico de la relación encabezado-ítems. |
| **`R_E_C_N_O_` / `D_E_L_E_T_`** | Campos de control de Protheus: consecutivo de fila y borrado lógico (`*`). Toda consulta debe filtrar `D_E_L_E_T_ = ' '`. |
| **MsExecAuto** | Mecanismo autorizado para escritura programática masiva: simula al usuario y fuerza todas las validaciones. Única vía de escritura futura. |
| **DES → BIB → PRD** | Ruta obligatoria de ambientes (desarrollo → biblioteca/calidad → producción). ResultarAI solo tocará DES y endpoints read-only autorizados. |
