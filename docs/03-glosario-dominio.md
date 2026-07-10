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
| **Identity Audit Log** / **Auditoría de identidad** | `IdentityAuditEvent` | Registro append-only e inmutable de eventos de identidad (alta, suspensión, cambio de rol, reset de contraseña, revocación de sesiones, exigencia de TOTP, y aceptación de acuerdo). |
| **Agent Skill** / **Paquete de skill** | `SkillPackage` | Carpeta con `SKILL.md` que implementa la spec oficial **Agent Skills** (agentskills.io): instrucciones con progressive disclosure y `allowed-tools`. El Skill Manifest la referencia y le añade la capa de gobernanza (política, riesgo). |
| **Progressive disclosure** | — | Divulgación progresiva de instrucciones dentro de un Agent Skill: el contenido detallado se carga solo cuando la skill se activa, no de entrada. |
| **`allowed-tools`** | `allowed-tools` | Declaración, dentro de un Agent Skill, de qué tools puede usar; el Skill Router y el Policy Gate la respetan como techo, nunca la amplían. |
| **MCP Server** | — | Servidor que expone tools conforme a la spec **MCP** vigente (revisión 2025-11-25); el Tool Manifest referencia sus tools a través del cliente MCP. |
| **Ciclo de vida de skill** (`draft`/`validated`/`active`/`deprecated`) | — | Estados por los que pasa un Agent Skill antes de estar disponible para el Skill Router y después de dejar de estarlo. |
| **Kill switch** | — | Interruptor de plataforma que desactiva un agente o tool en menos de un minuto, sin deploy; auditado; visible en catálogo y ficha de agente. |
| **`escalate_hitl`** | `PolicyDecision.escalate_hitl` | Efecto del Policy Gate que detiene la ejecución y crea una Tarjeta HITL en vez de permitir o bloquear directamente. |
| **Semver de manifiestos** | — | Versionado semántico obligatorio de cada manifiesto; un cambio incompatible exige una nueva versión mayor. |
| **`ActionRequest`** | `ActionRequest` | Solicitud de acción evaluada por el Policy Gate: quién, qué skill/tool, con qué nivel de riesgo. |
| **`PolicyDecision`** | `PolicyDecision` | Resultado del Policy Gate ante un `ActionRequest`: `allow` / `deny` / `escalate_hitl`, con motivo auditable. |
| **`RoutingDecision`** | `RoutingDecision` | Resultado del Skill Router: responder directo, activar una skill o delegar a otro agente. |
| **`RiskLevel`** | `RiskLevel` (`low`/`medium`/`high`/`critical`) | Nivel de riesgo de una acción; determina si el Policy Gate exige aprobación (HITL) y con qué severidad. |
| **`RetrievalPort`** | `RetrievalPort` | Port placeholder para RAG futuro; declarado desde el día uno, sin implementación real (adapter nulo) hasta Etapa P. |
| **`SkillPackagePort`** | `SkillPackagePort` (adapter `skills_fs`) | Port que resuelve paquetes de Agent Skill desde el filesystem. |

## Términos de conversación y runtime

| Término | Nombre en código | Definición |
|---|---|---|
| **Sesión** | `Session` | Conversación persistente entre un usuario y un agente; contenedor append-only de turnos y mensajes. |
| **Turno** / **Frontera de turno** | `Turn` | Ciclo pregunta-respuesta dentro de una sesión; unidad en la que se evalúa la compaction y el Policy Gate. |
| **Fases del turno** | `TurnPhase` | Las fases ordenadas de la ejecución de un turno: `receive`, `route`, `execute_graph`, y `respond`. |
| **Mensaje** | `Message` | Unidad mínima persistida (usuario, agente o sistema) dentro de un turno; nunca se reescribe. |
| **Rama** | `parent_id`, branch-never-rewrite | Historial alternativo creado al editar o regenerar un mensaje; el original nunca se borra ni se sobrescribe. |
| **Selector de versiones** | — | Control de UI para navegar entre ramas que parten de un mismo punto de la conversación. |
| **Stickiness** | — | El perfil de modelo elegido para una sesión se mantiene salvo escalación manual o fallback automático. |
| **Perfil de modelo** | `ModelProfile` | Configuración declarativa de qué modelo(s) usa un agente/skill, con su cascada de fallback, resuelta vía LiteLLM. |
| **Cascada de fallback** | `fallback_cascade` | Orden de modelos alternos que LiteLLM intenta si el modelo principal de un perfil falla o no responde. |
| **Modelo alterno** | `is_alternate_model` | Etiqueta visible cuando una respuesta se generó con un modelo de fallback, no con el principal del perfil. |
| **Marcador de escalación** | `<<<NEEDS_PRO>>>`, `escalation.enabled` | Señal genérica que un agente emite para pedir escalar a un modelo más capaz; un adjunto nunca puede dispararla. |
| **Cache hit/miss** | `cache_hit_tokens`, `cache_miss_tokens` | Resultado de reutilizar (hit) o no (miss) contexto cacheado del proveedor LLM; afecta costo y tarificación. |
| **`cache_hit_rate`** | `cache_hit_rate` | Métrica de proporción de cache hits sobre el total de llamadas; insumo del taxímetro y de cuotas. |
| **Compaction** / **Compactación** | — | Resumen automático del historial al 80% de la ventana de contexto; ocurre una sola vez, en frontera de turno. |
| **Ventana de contexto** | — | Límite de tokens que un modelo puede recibir en una llamada; al acercarse al límite dispara compaction. |
| **Traza** | `trace_id` | Registro en Langfuse de un turno completo: prompts, tool calls, costo, usuario enmascarado. |
| **Feedback** | 👍/👎 | Señal del usuario sobre una respuesta, ligada a su traza y a la versión de prompt usada. |
| **Candidato a caso de regresión** | — | Feedback negativo que se convierte en insumo para un futuro caso de eval (`e25-evals-gates`). |
| **Streaming SSE** / **Heartbeat** | — | Entrega de la respuesta por Server-Sent Events con señales periódicas (heartbeat) para detectar cortes de conexión. |
| **Tool call** | — | Invocación de una tool MCP durante un turno; se muestra colapsada/expandible y queda auditada. |
| **Taxímetro** | — | Indicador de costo/consumo en vivo durante la conversación (tokens, costo estimado). |

## Términos de producto

### Shell y experiencia

| Término | Definición |
|---|---|
| **Shell** | Interfaz única que se adapta por rol (Admin/Técnico/Funcional); no hay apps separadas por rol. |
| **Banner IA** | Aviso permanente y visible de que las respuestas provienen de un modelo de IA. |
| **Tema** (dark/light) | Modo de color de la UI, configurable por el usuario en Configuración personal. |
| **Brand** (default/totvs) | Set de marca aplicado sobre los tokens de diseño; dual-brand por instancia. |
| **Tokens de diseño** | Valores de diseño (color, tipografía, espaciado) versionados; nunca hardcodeados en componentes. |
| **Matriz de capacidades** | Tabla que define qué puede hacer cada rol en cada sección de la shell. |
| **Matriz de visibilidad agente×rol** | Tabla que define qué agentes ve cada rol en el catálogo. |

### Identidad y acceso

| Término | Definición |
|---|---|
| **Rol Admin/Técnico/Funcional** | Los tres roles de la plataforma; determinan capacidades visibles y flujos de aprobación. |
| **Cuenta** | Identidad de un usuario dentro de una instancia; unidad de autenticación y ownership. |
| **Grupo/equipo** | Agrupación de cuentas usada por cuotas jerárquicas y notificaciones. |
| **TOTP** | Segundo factor de autenticación por código de un solo uso; obligatorio para Admin, opcional para el resto. |
| **Códigos de respaldo** | Códigos de un solo uso para recuperar acceso si se pierde el dispositivo TOTP. |
| **Acuerdo de uso** | Texto legal/operativo que el usuario acepta; su re-aceptación queda auditada si cambia de versión. |
| **Contraseña temporal de un solo uso** | Contraseña de primer acceso que fuerza un cambio inmediato. |
| **Sesión activa** (self-service) | Sesión de login que el propio usuario puede ver y cerrar remotamente. |

### Notificaciones y ownership

| Término | Definición |
|---|---|
| **Notificación** | Evento dirigido a un usuario o rol (p. ej. solicitud de liberación, aprobación resuelta). |
| **Centro de notificaciones** | Campana con no-leídas, deep links a la sección relevante y filtrado por rol/ownership. |
| **Ownership** | Relación entre un recurso (adjunto, solicitud, conversación) y el usuario que lo creó; determina qué ve cada quien en "Mi espacio". |

### Adjuntos

| Término | Nombre en código | Definición |
|---|---|---|
| **Adjunto** (**Attachment**) | `Attachment` | Archivo subido a una conversación; pasa por validación, extracción y escaneo antes de llegar al agente. |
| **Extracción** | `full_text` / `inserted_text` | Texto obtenido de un adjunto por tipo de archivo: `full_text` es el contenido completo, `inserted_text` el que efectivamente se inserta en el prompt (puede truncarse). |
| **Chip** (de adjunto) | — | Elemento de UI que representa un adjunto en el chat con su estado (extraído, bloqueado, pendiente). |
| **Niveles de datos N0–N3** | — | Clasificación de sensibilidad de un adjunto/campo: N0 público … N3 bloqueante; N2 exige confirmación auditada, N3 bloquea el envío. |

### Cuotas

| Término | Definición |
|---|---|
| **Cuota** | Límite de consumo (tokens/costo) evaluado ANTES de cada llamada, jerárquico: global→grupo→usuario→sesión. |
| **Liberación de cuota** / **Solicitud de liberación** | Excepción temporal a una cuota agotada, solicitada por el usuario y aprobada por un Admin; auditada. |

### HITL y aprobaciones

| Término | Nombre en código | Definición |
|---|---|---|
| **Tarjeta HITL** | `ApprovalCard` | Componente de UI que muestra payload, riesgo y expiración (=rechazo auditado) de una acción detenida para aprobación humana. |
| **Solicitud de aprobación** | `ApprovalRequest` | Registro de la acción pendiente de aprobación, generado por `escalate_hitl`. |
| **Aprobador** | — | Usuario habilitado para resolver una Solicitud de aprobación. |
| **Segunda aprobación** (4 ojos) | — | Aprobación adicional obligatoria en acciones irreversibles, de un aprobador distinto al primero. |
| **Bandeja de aprobaciones** | — | Vista donde el Aprobador ve y resuelve las Tarjetas HITL pendientes; con experiencia móvil de primera clase. |
| **Historial de decisiones** | — | Registro de aprobaciones/rechazos ya resueltos, consultable por el Aprobador. |

### Mi espacio

| Término | Definición |
|---|---|
| **Mi auditoría** | Vista personal del propio rastro de acciones (equivalente acotado al audit log global). |
| **Mis adjuntos** | Vista personal de adjuntos propios, con descarga auditada. |
| **Configuración personal** | Preferencias propias: tema, idioma, TOTP, contraseña. |

### Catálogo de agentes

| Término | Definición |
|---|---|
| **Ficha de agente** (capa común / ficha técnica) | Página de detalle de un agente: capa común (todos los roles) y ficha técnica (Técnico/Admin). |
| **Toolset** | Conjunto de tools habilitadas para un agente/skill, visible en el Tool Registry. |
| **Estado comercial de agente** (activo/beta/próximamente/deprecado) | Etiqueta de disponibilidad de un agente en el catálogo, independiente del kill switch técnico. |

### Memoria de usuario

| Término | Definición |
|---|---|
| **Memoria de usuario** | Datos que el agente recuerda entre sesiones; el agente solo PROPONE, el usuario confirma; límite ~1k tokens. |
| **Snapshot de memoria** | Copia de la memoria de usuario tomada post-prefijo, usada para reconstrucción/auditoría. |
| **Propuesta de memoria** | Cambio de memoria sugerido por el agente, pendiente de confirmación del usuario. |

## Términos de gobernanza de plataforma y builders

| Término | Nombre en código | Definición |
|---|---|---|
| **Registro de Prompts** | — | Catálogo de versiones inmutables de prompts, con ciclo de vida draft→published→retired. |
| **Versión de prompt** (draft/published/retired) | — | Estados del ciclo de vida de una versión de prompt dentro del Registro de Prompts. |
| **Activar** / **Rollback** | — | Operaciones sobre el Registro de Prompts para poner en producción o revertir una versión, sin deploy. |
| **Diff de versiones** | — | Comparación visual entre dos versiones de un prompt (o de un agente). |
| **Espejo Git** | — | Copia versionada en Git de cada cambio del Registro de Prompts, para trazabilidad fuera de la plataforma. |
| **Gate de publicación** | `PublicationGate` (modos `placeholder`/`enforcing`) | Verificación previa a publicar un agente/skill: en modo `placeholder` (mientras `e25-evals-gates` no esté archivado) solo advierte; en `enforcing` bloquea si el score de evals no alcanza el umbral. |
| **Feature flag** (scope) | — | Interruptor de funcionalidad con alcance configurable (global/instancia/rol); complementa al kill switch. |
| **Tool Registry** (vista admin) | — | Vista de administración que lista todas las tools conocidas, su clasificación de riesgo y su estado. |
| **Configuración de instancia** | — | Ajustes propios de una instancia: branding, retención, límites, matrices de capacidades/visibilidad. |
| **Instancia** | — | Despliegue de la plataforma para un cliente o para el proyecto interno `Resultar`; unidad de configuración y aislamiento (ver Tenant). |
| **Borrador/versión de agente** | — | Estado editable de un agente en el Agent Builder antes de publicarse. |
| **Horneado** (de toolset/skills por versión) | — | Fijar qué toolset y qué Agent Skills quedan congeladas para una versión publicada de un agente. |
| **Propuesta guiada** | — | Flujo asistido con el que un Técnico propone un agente/skill nuevo sin acceso directo al Builder de Admin. |
| **Sandbox self-service** | — | Entorno de prueba sin escrituras donde un Técnico valida su propuesta antes de someterla. |
| **Registro de skills** | — | Catálogo de Agent Skills descubiertas/validadas, análogo al Tool Registry. |
| **Caso de eval declarado** | — | Entrada de un dataset de evals (aún sin ejecutar) que documenta la intención de prueba de un agente/skill. |
| **Owner** | — | Responsable declarado de un agente, skill, tool o workflow; visible en su ficha. |

## Términos de calidad y operación

| Término | Nombre en código | Definición |
|---|---|---|
| **Workflow** | `WorkflowDefinition` | Proceso determinista de pasos fijos por versión, con formulario tipado y archivos esperados. |
| **Corrida** | `WorkflowRun` | Ejecución concreta de un Workflow: estado en vivo por paso, pausas HITL, resultado descargable. |
| **Paso** | `WorkflowStep` | Unidad de un Workflow; puede pausarse para HITL antes de continuar. |
| **Workflow Registry** | — | Catálogo de Workflows disponibles, análogo al Tool Registry y al Registro de skills. |
| **Dataset de evals** | — | Conjunto de casos de prueba (solo datos sintéticos) por agente/skill, en YAML. |
| **Runner de evals** | — | Componente que ejecuta un Dataset de evals y produce un Score por versión. |
| **Score por versión** | — | Resultado del Runner de evals asociado a una versión concreta de prompt/agente/skill. |
| **Golden set** | — | Subconjunto de casos de eval considerado referencia estable para detectar regresiones. |
| **Safety hard-fail** | — | Caso de eval de seguridad cuyo fallo bloquea la publicación individualmente, sin promediarse con el score general. |
| **Gate de CI** | — | Verificación automática en CI (ruff, mypy, import-linter, pytest, evals) que debe pasar antes de mergear. |
| **Hash de versión de prompt** | — | Huella única de una versión de prompt, usada para detectar cambios no versionados. |
| **Seed inicial** | — | Datos mínimos (usuarios, agente de ejemplo, políticas) cargados al levantar una instancia limpia. |
| **Runbook** | — | Documento operativo con pasos para responder a incidentes conocidos. |
| **Smoke test** | — | Prueba mínima end-to-end que confirma que una instancia recién levantada funciona. |
| **Reverse proxy** | — | Componente que expone la plataforma sin exponer el gateway directamente (regla: gateway no público). |
| **Backup** / **Restauración** | — | Copia periódica de Postgres y su procedimiento de restauración verificado. |
| **Healthcheck** | — | Endpoint/mecanismo que reporta si un servicio está operativo, usado por Uptime Kuma. |

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
