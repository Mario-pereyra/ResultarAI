# Proposal — d20-gobernanza-plataforma

## Why

La plataforma "de fábrica" necesita que un Admin gobierne el runtime **sin deploy y con todo auditado**: publicar y activar versiones de prompt, apagar un agente o una tool en menos de un minuto ante un incidente, ver el registro de tools con su riesgo, y ajustar los defaults de la instancia (branding, retención, límites, matrices). Sin esta consola, cada cambio operativo exigiría un despliegue y la regla dura de auditabilidad quedaría sin superficie de control. Como el runner de evals (`e25`) lo ejecuta el product owner al final, el gate de publicación debe **nacer pluggable** (`docs/07-roadmap.md`, Nota de desacople): el contrato existe desde ya y opera en modo placeholder hasta que `e25` esté archivado.

## What Changes

- **Registro de Prompts** (vista `34-admin-prompts`, Flujo F): la fuente de verdad de runtime pasa a Postgres; las versiones publicadas son **inmutables** (editar = versión nueva); ciclo `draft → published → retired`; diff lado a lado entre versiones; **activar** una versión es un update de puntero **sin deploy** (los chats nuevos la toman, las sesiones en curso no se reescriben — stickiness); **rollback** con un clic, auditado; **espejo Git automático**: cada publicación exporta un snapshot a `prompts/` para code review (Git deja de ser fuente de runtime).
- **Gate de publicación pluggable** (Nota de desacople): el contrato del gate se define ahora. Mientras `e25-evals-gates` no esté archivado opera en **modo placeholder** (score de evals ausente = **advertencia visible**, no bloqueo); cuando `e25` llegue, el **modo enforcing** bloquea con score < 80% o con algún caso `safety` en rojo. Se especifican ambos modos.
- **Feature flags + kill-switch** (vista `38-admin-flags`, Flujo I): tabla de flags con scope (global/agente/rol); **kill-switch por agente y por tool** con apagado efectivo en **< 1 min sin deploy**; en acción crítica pide confirmación + motivo; efectos coordinados: rechaza turnos nuevos, deja terminar o aborta streams con aviso, congela las tarjetas HITL del agente ("agente suspendido"), el catálogo muestra "No disponible temporalmente" y se notifica a usuarios con sesiones activas; reactivación restaura y notifica; todo auditado. Es el complemento runtime del status `deprecated` del ciclo de vida de manifiestos (`a02`).
- **Tools y permisos** (vista `35-admin-tools`): vista administrativa del **Tool Registry** (`c09`): la clasificación lectura/escritura/riesgo es **visible pero no editable en runtime** (cambiarla = PR); permisos por rol/agente; **matriz de visibilidad agente×rol** (consumida por `d15`) y matriz de capacidades por vista, ambas configuración viva en DB, versionadas y auditadas, sin deploy.
- **Configuración de instancia** (vista `40-admin-instancia`): branding (brand `default`/`totvs`, logo, nombre), retención de adjuntos, límites de attachments, idioma default, umbrales de cuota y tiempo de vida de tarjetas HITL — **todo default es configuración de instancia, no constante de código**.

## Capabilities

### New Capabilities

- `prompt-registry`: versiones inmutables en Postgres, ciclo draft/published/retired, diff, activar/rollback sin deploy, espejo Git automático y gate de publicación pluggable (placeholder/enforcing).
- `feature-flags`: flags con scope y kill-switch por agente y por tool, con sus efectos coordinados, notificación y restauración, todo auditado.
- `tool-permissions`: vista del Tool Registry con riesgo no editable en runtime, permisos por rol/agente y matrices de visibilidad y de capacidades.
- `instance-config`: configuración completa de instancia (branding, retención, límites, idioma, umbrales de cuota, TTL de tarjetas HITL).

### Modified Capabilities

*(ninguna — estas cuatro capacidades no existían en `openspec/specs/`)*

## No-objetivos

- **Sin runner de evals** (`e25-evals-gates`): aquí solo vive el **contrato** del gate en sus dos modos; el dataset, el score real y la vista `43-admin-evals` son de `e25`.
- **Sin perfiles de conexión** ni la vista `36-admin-conexiones`: son Etapa P (bridges/clientes/ambientes Protheus).
- **Sin builders** (`d21-builders`): Agent Builder y Skills Builder quedan fuera; el gate pluggable que ellos reusan se especifica aquí, no su UI de construcción.
- No se define el motor de cuotas (`d16`), el centro de notificaciones (`d12`), el catálogo (`d15`) ni las tarjetas HITL (`d17`): d20 **consume sus contratos** (config de cuota/TTL, notificar, matriz de visibilidad, congelar tarjetas) sin reimplementarlos.
- No se toca `core/`: la gobernanza de runtime es lógica de aplicación (config viva en DB), no un contrato del núcleo.

## Bounded context afectado

Bounded context **`governance`** en `resultarai/app/` (registro de prompts, flags/kill-switch, permisos de tools, config de instancia) más su **frontend** (vistas `34`, `35`, `38`, `40` bajo la sección "Consola admin", solo Admin). Usa `adapters/` para persistencia Postgres y espejo Git; no introduce lógica en `core/`.

## Impact

- `resultarai/app/governance/` (nuevo): servicios de registro de prompts, flags/kill-switch, permisos de tools y config de instancia; endpoints Admin.
- `resultarai/adapters/`: repositorios Postgres (append-only para auditoría de gobernanza) y adapter de espejo Git a `prompts/`.
- Frontend: cuatro vistas Admin nuevas y sus efectos observables por otras vistas (catálogo `d15`, HITL `d17`, notificaciones `d12`) vía contratos.
- Contratos consumidos: config de cuota (`d16`), TTL de tarjetas HITL (`d17`), matriz de visibilidad (`d15`), status `deprecated` de manifiestos (`a02`).
- Referencia del blueprint: §2.4.4 "Agentic Scaffolding Framework" (gobernanza declarativa versionada) — se cita, no se copia.
