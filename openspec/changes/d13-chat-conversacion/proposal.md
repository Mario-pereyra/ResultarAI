## Why

El chat es la superficie principal del producto (`design/VISTAS/02-chat.md` §0) y el único punto donde un usuario interactúa con un agente del catálogo, pero hasta ahora ningún change entrega la experiencia completa: `b04`-`b07` construyen el motor (persistencia, gateway, runtime, trazas) y `c09` el contrato de tool calls, pero ninguno expone un endpoint HTTP ni una UI. Sin `d13` nadie puede enviar un turno, ver una respuesta en streaming, editar un mensaje, escalar a Pro ni retomar una sesión anterior — el resto del roadmap de Etapa D (attachments, catálogo, cuotas, HITL) se apoya en esta superficie ya funcionando.

## What Changes

- Se implementa la **API de chat** en `resultarai/app/api/`: crear sesión (nace con el agente elegido del catálogo y fija su `model_profile` por stickiness), enviar turno, streaming de la respuesta por SSE con reconexión y heartbeat, cancelar un stream en curso, listar sesiones propias e historial de una sesión, y búsqueda por texto en título y contenido de mensajes.
- Se implementan las **ramas** (Flujo G, `design/VISTAS/02-chat.md` vista 09): editar un mensaje propio o regenerar una respuesta crea una rama nueva (`parent_id` de `b04-persistencia-postgres`) con selector "versión 1/2"; la historia jamás se reescribe; aviso suave de regeneración costosa al editar tres o más mensajes atrás; alternar de rama conserva intactas las respuestas posteriores de cada rama.
- Se implementa la **escalación manual a Pro** (Flujo D, vista 08): la UI intercepta el evento de escalación que emite `b05-gateway-modelos` (nunca el marcador crudo), muestra una tarjeta con un único botón "Continuar con Pro" que abre una **nueva conversación/rama** con el `model_profile` Pro; el usuario también puede "Seguir con Flash"; la escalación nunca ocurre sola y es configurable por agente (Agent Manifest de `a02-core-manifiestos`); la etiqueta "modelo alterno" es visible para todos los roles cuando la respuesta vino de un perfil de fallback.
- Se implementa la **UI del chat** (assistant-ui sobre `d10-design-system-shell`) para las vistas 05, 06, 08, 09, 10 y 12 de `design/VISTAS/02-chat.md`: streaming con markdown/tablas/código con highlighting y sanitización anti-XSS, indicador de actividad y de compaction, tool calls colapsadas/expandibles según el contrato `tool-call-visibility` de `c09-mcp-tools` (lenguaje simple para Funcional, parámetros completos para Técnico/Admin), capa de telemetría por turno para Técnico/Admin (costo, perfil, chips de cache hit/miss/write — vista 06), tarjetas de error accionables para `GATEWAY_OFFLINE` y `QUOTA` (el estado UI únicamente; el enforcement de cuotas llega en `d16-cuotas-liberaciones`), feedback 👍/👎 por respuesta ligado a la traza (`b07-observabilidad`), ejemplos clicables que precargan el composer, e historial de sesiones (vista 12) con búsqueda e indicador de ramas.
- La UI del chat es funcional en móvil (transversal `design/FUNCIONALIDADES.md` §14).

## Capabilities

### New Capabilities

- `chat-streaming`: API de sesiones, turnos, streaming SSE de la respuesta y cancelación; listar/leer sesiones e historial con búsqueda por texto.
- `chat-experience`: UI completa del chat por capas de rol (Funcional/Técnico/Admin), tarjetas de error accionables, UX de escalación manual a Pro, UX de ramas (edición/regeneración/selector de versiones) y UX de feedback.
- `session-history`: listado de sesiones propias, búsqueda por texto, indicador de ramas por sesión y reanudación de sesión en su última rama activa.

### Modified Capabilities

*(ninguna — este change no cambia requirements de `conversation-persistence`, `model-gateway`, `model-profiles`, `escalation-marker`, `agent-runtime`, `skill-router`, `context-compaction` ni `tool-call-visibility`; los consume tal como están especificados en `b04`, `b05`, `b06` y `c09`)*

## No-objetivos

- **Sin attachments**: subida, extracción, vista previa "lo que verá el agente", escaneo N2/N3 (vista 07, `design/ANEXO-ATTACHMENTS.md`) — eso es `d14-attachments`. Este change no agrega chips de adjuntos al composer.
- **Sin citas ni evidencia documental**: la vista 11 (citas TDN/CST, abstención de DocAgent) queda fuera; es personalización Protheus/documental de Etapa P sobre la plataforma genérica.
- **Sin enforcement de cuotas**: este change muestra el estado UI de la tarjeta `QUOTA` (composer deshabilitado + botón "Solicitar liberación") pero no implementa la evaluación de presupuestos global→grupo→usuario→sesión ni el flujo de liberación — eso es `d16-cuotas-liberaciones`.
- **Sin tarjetas HITL**: las tools de escritura y su tarjeta de aprobación (payload, riesgo, expiración, segunda aprobación) son `d17-hitl-aprobaciones`; aquí solo las tools de lectura, colapsadas/expandibles.
- **Sin memoria de usuario**: el indicador de memoria usada y la propuesta "¿guardo esto en tu memoria?" son `e23-memoria-usuario`.
- **Sin catálogo de agentes ni selector de contexto cliente/ambiente**: iniciar una sesión asume que ya se eligió el agente (`d15-catalogo-agentes`); el selector cliente/ambiente de Protheus es Etapa P.
- **Sin centro de notificaciones**: las notificaciones que podrían originarse en el chat (p. ej. liberación de cuota) son `d12-notificaciones`.

## Bounded context afectado

`orchestration` como consumidor (invoca el graph template de `b06-runtime-grafos` por turno) materializado en `resultarai/app/api/` y `resultarai/app/use_cases/chat/` (casos de uso de sesión/turno/streaming, sin lógica de dominio nueva en `core/`) + `frontend/` (vistas de chat sobre el shell de `d10-design-system-shell`). No define ports ni contratos de `core/`; compone `StatePort` (`b04`), `LLMPort`/eventos de escalación (`b05`), el runtime (`b06`) y `TracePort` (`b07`) ya definidos, y consume el contrato `tool-call-visibility` de `c09-mcp-tools` sin redefinirlo.

## Impact

- Backend: `resultarai/app/api/` (endpoints REST + SSE de chat: sesiones, turnos, streaming, cancelación, historial, búsqueda), `resultarai/app/use_cases/chat/` (orquestación de turno, ramas, escalación).
- Frontend: `frontend/` — vistas `05-chat-funcional`, `06-chat-admin`, `08-escalacion`, `09-branching`, `10-errores` (subconjunto `GATEWAY_OFFLINE`/`QUOTA`), `12-historial`, componentes assistant-ui de streaming/markdown/tool-calls/feedback.
- Dependencias: requiere `a01-fundacion-repo`, `a02-core-manifiestos`, `a03-core-gobernanza`, `b04-persistencia-postgres`, `b05-gateway-modelos`, `b06-runtime-grafos`, `b07-observabilidad`, `c09-mcp-tools` y `d10-design-system-shell` archivados o con su interfaz ya especificada.
- Habilita: `d14-attachments` (composer ya existe, solo agrega chips), `d16-cuotas-liberaciones` (reemplaza el placeholder UI de `QUOTA` por enforcement real), `d17-hitl-aprobaciones` (agrega la tarjeta de escritura al mismo flujo de tool calls), `e23-memoria-usuario` (agrega el indicador sobre esta misma UI).
- Referencia de diseño: `design/FLUJOS.md` Flujo B (sin la parte de citas), Flujo D y Flujo G; `design/VISTAS/02-chat.md` vistas 05, 06, 08, 09, 10, 12; `design/FUNCIONALIDADES.md` §4 y §14.
