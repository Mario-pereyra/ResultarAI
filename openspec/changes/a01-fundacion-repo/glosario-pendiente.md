# Términos pendientes de incorporar al glosario (insumo de la tarea 1.3)

> Consolidado de los términos que los 25 changes usan y que `docs/03-glosario-dominio.md` (estado pre-pivote) aún no define. Al ejecutar la tarea 1.3 de este change, incorporarlos con su identificador en inglés, agrupados como sigue.

## Núcleo y gobernanza (a02, a03, b06)

Agent Skill / Paquete de skill (`SkillPackage`, carpeta con `SKILL.md`) · progressive disclosure (divulgación progresiva) · `allowed-tools` · MCP Server · estados del ciclo de vida `draft/validated/active/deprecated` · Kill switch · efecto `escalate_hitl` · semver de manifiestos · `ActionRequest` · `PolicyDecision` · `RoutingDecision` · `RiskLevel` (low/medium/high/critical) · `RetrievalPort` (placeholder RAG) · `SkillPackagePort` (adapter `skills_fs`)

## Conversación y runtime (b04, b05, b06, b07, d13)

Sesión · Turno / Frontera de turno · Mensaje · Rama (`parent_id`, branch-never-rewrite) · Selector de versiones · Stickiness · Perfil de modelo (`ModelProfile`) · Cascada de fallback · Modelo alterno · Marcador de escalación (`<<<NEEDS_PRO>>>`) · Cache hit/miss · `cache_hit_rate` · Compaction / Compactación · Ventana de contexto · Traza (`trace_id`) · Feedback · Candidato a caso de regresión · Streaming SSE / heartbeat · Tool call · Taxímetro

## Producto (d10–d18, e23)

Shell · Banner IA · Tema (dark/light) · Brand (default/totvs) · Tokens de diseño · Matriz de capacidades · Matriz de visibilidad agente×rol · Rol Admin/Técnico/Funcional · Cuenta · Grupo/equipo · TOTP · Códigos de respaldo · Acuerdo de uso · Contraseña temporal de un solo uso · Sesión activa (self-service) · Notificación · Centro de notificaciones · Ownership · Adjunto (Attachment) · Extracción (`full_text`/`inserted_text`) · Chip (de adjunto) · Niveles de datos N0–N3 · Cuota · Liberación de cuota / Solicitud de liberación · Tarjeta HITL (`ApprovalCard`) · Solicitud de aprobación (`ApprovalRequest`) · Aprobador · Segunda aprobación (4 ojos) · Bandeja de aprobaciones · Historial de decisiones · Mi auditoría · Mis adjuntos · Configuración personal · Ficha de agente (capa común / ficha técnica) · Toolset · Estado comercial de agente (activo/beta/próximamente/deprecado) · Memoria de usuario · Snapshot de memoria · Propuesta de memoria

## Gobernanza de plataforma y builders (d20, d21)

Registro de Prompts · Versión de prompt (draft/published/retired) · Activar / Rollback · Diff de versiones · Espejo Git · Gate de publicación (modos placeholder/enforcing, `PublicationGate`) · Feature flag (scope) · Tool Registry (vista admin) · Configuración de instancia · Instancia · Borrador/versión de agente · Horneado (de toolset/skills por versión) · Propuesta guiada · Sandbox self-service · Registro de skills · Caso de eval declarado · Owner

## Calidad y operación (e22, e24, e25)

Workflow (`WorkflowDefinition`) · Corrida (`WorkflowRun`) · Paso (`WorkflowStep`) · Workflow Registry · Dataset de evals · Runner de evals · Score por versión · Golden set · Safety hard-fail · Gate de CI · Hash de versión de prompt · Seed inicial · Runbook · Smoke test · Reverse proxy · Backup / Restauración · Healthcheck
