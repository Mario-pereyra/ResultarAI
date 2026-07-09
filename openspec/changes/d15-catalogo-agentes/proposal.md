# Proposal — d15-catalogo-agentes

## Why

`d13-chat-conversacion` entrega el chat completo pero asume que la sesión ya nace con un agente elegido; `d12-notificaciones` entrega el mecanismo de aviso genérico pero necesita un evento real de "novedad de catálogo" que lo dispare. Sin un catálogo, ningún usuario puede descubrir qué agentes existen ni cómo empezar a usarlos — "un agente que nadie sabe que existe no se usa" (`design/VISTAS/03-catalogo.md`). Este change entrega la superficie de descubrimiento (vista 13) y la ficha de detalle que funciona como onboarding (vista 14), consumiendo los agentes de `a02-core-manifiestos` filtrados por la matriz de visibilidad agente×rol que administrará `d20-gobernanza-plataforma`.

## What Changes

- Se implementa el **catálogo de agentes** (`app/api` + `frontend/`, vista 13): grilla de agentes con `status` `active` (Agent Registry de `a02-core-manifiestos`), búsqueda por texto, filtro por estado, orden fijo (activos → beta → próximamente → deprecado, alfabético dentro de cada grupo), contador `aria-live`, capa técnica en la card (versión activa, costo estimado, evals) visible solo para Técnico/Admin.
- Se implementa la **ficha de agente** (vista 14) con capa común para todos los roles (nombre, descripción, límites — qué NO hace, casos de uso, roles objetivo, owner, 3 ejemplos de prompts clicables que prellenan el composer sin enviar) y **ficha técnica** solo Técnico/Admin en tabs (Resumen: perfil de modelo, escalación a Pro, política HITL/datos, costo desglosado; Tools: tabla lectura/escritura/scope; Prompt: versión activa; Evals: score — **hasta que `e25-evals-gates` exista, muestra "sin evals aún" en modo placeholder**, conforme al desacople del roadmap).
- Se implementa el **contrato de lectura de visibilidad agente×rol**: el catálogo consulta, por cada agente y el rol del usuario autenticado, si es visible; cuando no hay una entrada explícita en la matriz (porque `d20` todavía no existe o el Admin no la configuró), aplica los defaults por `status` documentados en `design/VISTAS/03-catalogo.md` (activo/beta visibles para todos; próximamente visible por default para Técnico/Admin y oculto para Funcional salvo habilitación explícita; deprecado visible solo para Admin). Un piso de seguridad no configurable oculta a Funcional cualquier agente cuyo toolset incluya una tool de clasificación `escritura` (`a02`/`c09`), sin importar lo que diga la matriz.
- Se implementa **iniciar conversación**: el botón "Abrir chat" invoca el endpoint de creación de sesión de `d13-chat-conversacion` con el agente elegido; la ficha muestra si el agente permite escalación manual a Pro (Técnico/Admin).
- Se implementa el **estado de kill-switch por agente**: el catálogo consume una bandera de habilitación runtime por agente (contrato de lectura; la administración del feature flag/kill-switch —apagado <1 min sin deploy— es `d20-gobernanza-plataforma`); según configuración de instancia, un agente apagado aparece deshabilitado con mensaje o se oculta.
- Se seedean los **datos de fábrica**: `default_chat` + el agente de ejemplo de `a02` con su ficha completa (descripción, límites, casos de uso, ejemplos, owner) visibles a todos los roles.
- La UI es funcional en móvil (transversal `design/FUNCIONALIDADES.md` §14): grilla a 1 columna, ficha de lectura completa con scroll-x en tablas.

## Capabilities

### New Capabilities

- `agent-catalog`: grilla de agentes filtrada, búsqueda/filtro/orden, ficha por capas (común + técnica), ejemplos clicables, iniciar conversación, indicador de escalación a Pro, estado de kill-switch, estados de carga/vacío/error/degradado, datos de fábrica.
- `agent-visibility`: contrato de lectura de la matriz de visibilidad agente×rol (consumo; la administración vive en `d20-gobernanza-plataforma`), defaults por `status` cuando no hay override explícito, piso de seguridad de toolset para Funcional, y comportamiento ante cambios de visibilidad en caliente.

### Modified Capabilities

*(ninguna — `openspec/specs/` está vacío; no existen specs previas)*

## No-objetivos

- **Sin administración de la matriz de visibilidad**: crear, editar o versionar entradas agente×rol es `d20-gobernanza-plataforma`; este change solo define y consume el contrato de lectura, con sus defaults.
- **Sin Agent Builder ni Skills Builder**: crear o editar agentes (identidad de ficha, instrucciones, toolset, perfil de modelo) es `d21-builders`; este change solo lee agentes ya publicados en el registro de `a02`.
- **Sin sección de workflows**: los workflows deterministas son un tipo de ítem propio con su propia sección (`e22-workflows-deterministas`, ADR-0010); no entran a este catálogo ni a esta ficha.
- **Sin selector de contexto cliente/ambiente Protheus**: pertenece a la Etapa P; "iniciar conversación" en este change abre sesión directo, sin selector.
- **Sin registro de prompts operativo**: la ficha técnica muestra la versión activa del Agent Manifest (`a02`) como equivalente disponible hoy; el Registro de Prompts inmutable con diff/rollback es `d20-gobernanza-plataforma` y reemplazará ese campo cuando exista.
- **Sin runner de evals**: el score que muestra la ficha técnica es el que exponga `e25-evals-gates` cuando esté archivado; hasta entonces, modo placeholder ("sin evals aún"), sin bloquear nada.
- **Sin kill-switch operativo**: este change consume una bandera de habilitación por agente; crear, apagar o auditar esa bandera (<1 min, sin deploy) es `d20-gobernanza-plataforma`.
- **Sin notificación de "novedad de catálogo"**: el tipo ya está registrado en `d12-notificaciones`; este change no lo emite todavía (no hay evento de publicación de agente hasta que exista `d21-builders`).

## Bounded context afectado

`app/` (casos de uso de catálogo y `app/api` de solo-lectura sobre el Agent Registry) y `frontend/` (grilla + ficha sobre el shell de `d10-design-system-shell`). No se toca `core/`: el catálogo lee el `AgentManifest`/Agent Registry de `a02-core-manifiestos` tal como están especificados, sin redefinirlos ni agregarles campos nuevos al schema. Los campos de contenido propios de la ficha (descripción larga, límites, casos de uso, ejemplos, owner) son un read-model de aplicación propio de este change, persistido junto al resto del estado de aplicación (`b04-persistencia-postgres`), no un campo del Agent Manifest.

## Impact

- `resultarai/app/use_cases/catalog/`: casos de uso de listado filtrado por visibilidad, búsqueda/filtro/orden, resolución de ficha (capa común + técnica), resolución de visibilidad por rol con sus defaults, resolución de estado de kill-switch.
- `resultarai/app/api/`: endpoints REST de catálogo (listar agentes visibles para el rol autenticado, obtener ficha por `slug`, iniciar conversación delegando en el endpoint de sesión de `d13`).
- `resultarai/adapters/persistence_postgres/`: tabla de contenido de ficha (`agent_catalog_entry` — descripción, límites, casos de uso, roles objetivo, owner, ejemplos) y fixtures de fábrica para `default_chat` + agente de ejemplo.
- `frontend/`: vistas 13 (grilla) y 14 (ficha) de `design/VISTAS/03-catalogo.md`, componentes `agent-card__cases`/`agent-card__tech`/`agent-card__foot`, `example-btn`, tabs de ficha técnica.
- Dependencias: requiere `a01-fundacion-repo`, `a02-core-manifiestos` archivados o con su interfaz ya especificada; consume (sin bloquear si aún no están archivados) `b07-observabilidad` (costo estimado), `c09-mcp-tools` (clasificación lectura/escritura de tools), `d10-design-system-shell` (shell), `d13-chat-conversacion` (creación de sesión); deja contratos de consumo abiertos para `d20-gobernanza-plataforma` (matriz de visibilidad, kill-switch, registro de prompts) y `e25-evals-gates` (score de evals).
- Habilita: `d16-cuotas-liberaciones` y `d17-hitl-aprobaciones` (ambos asumen que una sesión nace desde este catálogo), `d20-gobernanza-plataforma` (implementa la administración de lo que aquí solo se consume), `e22-workflows-deterministas` (sección hermana, misma lógica de visibilidad).
- Referencia de diseño: `design/VISTAS/03-catalogo.md` (vistas 13 y 14, modelo de datos `agent` compartido), `design/FUNCIONALIDADES.md` §6 (Catálogo de agentes) y §14 (transversales: móvil, i18n, accesibilidad).
