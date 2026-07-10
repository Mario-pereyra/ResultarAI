## 1. API — sesiones y turnos

- [x] 1.1 Endpoint `POST /sessions` (crear sesión): recibe el agente del catálogo, fija `model_profile` inicial según la cascada de `b05-gateway-modelos` (stickiness). Verificación: test de integración que crea una sesión y confirma que turnos posteriores no cambian el `model_profile`. `[modelo: sonnet]`
- [x] 1.2 Endpoint `POST /sessions/{id}/messages` (enviar turno / editar): crea el mensaje de usuario con `parent_id` al último de la rama activa; si el payload declara `edits_message_id`, crea rama hermana bajo el `parent_id` del mensaje editado sin tocar el original. Verificación: test que edita un mensaje y confirma que el original permanece intacto y navegable. `[modelo: sonnet]`
- [x] 1.3 Endpoint `POST /messages/{id}/regenerate`: crea una respuesta de agente hermana bajo el mismo mensaje de usuario, sin borrar la anterior. Verificación: test que regenera dos veces y confirma 3 versiones navegables (`versión 1/3`, `2/3`, `3/3`). `[modelo: sonnet]`
- [x] 1.4 Traducción del evento de escalación del gateway (`escalation-marker` de `b05`) a evento de dominio de escalación en el contrato de salida del turno, garantizando que el marcador literal `<<<NEEDS_PRO>>>` nunca viaja en el texto entregado al cliente. Verificación: test que fuerza una respuesta con el marcador y confirma que el fragmento de texto entregado no lo contiene, apareciendo solo como evento de escalación separado. `[modelo: sonnet]`
- [x] 1.5 Endpoint de streaming SSE del turno: fragmentos incrementales con `id` por evento, heartbeat periódico como comentario SSE, evento de cierre con metadatos del turno (perfil usado, modelo alterno, compaction, escalación). Verificación: test de integración que consume el stream y valida el orden de eventos y el cierre. `[modelo: sonnet]`
- [x] 1.6 Reconexión por `Last-Event-ID`: al reconectar con el identificador del turno en curso, el servidor retoma desde el último fragmento no confirmado sin duplicar contenido ni reinvocar al runtime. Verificación: test que corta la conexión a mitad de un turno simulado y reconecta, confirmando que no hay fragmentos duplicados ni una segunda invocación al `LLMPort`. `[modelo: sonnet]`
- [x] 1.7 Endpoint `POST /messages/{id}/cancel`: detiene la generación en curso, persiste el texto parcial marcado "detenida por el usuario", cierra el stream sin error. Verificación: test que cancela un turno en streaming y confirma el estado "detenida" persistido y disponible para regenerar. `[modelo: sonnet]`
- [x] 1.8 Endpoint `POST /sessions/{id}/escalate`: valida que el Agent Manifest de la sesión tiene la escalación habilitada, crea sesión/rama nueva con el `model_profile` de escalación configurado, enlaza origen↔destino para la nota-enlace bidireccional; rechaza la operación si la escalación está deshabilitada por agente. Verificación: dos tests — escalación habilitada crea sesión enlazada con sesión original intacta; escalación deshabilitada retorna error sin crear nada. `[modelo: sonnet]`

## 2. API — historial y búsqueda

- [x] 2.1 Endpoint `GET /sessions` (listado propio): filtra por propietario derivado de la sesión de identidad (nunca de un parámetro), incluye agente, título automático, última actividad, `message_count`, `branch_count`. Verificación: test que confirma que el listado de un usuario nunca incluye sesiones de otro. `[modelo: sonnet]`
- [x] 2.2 Generación de título automático a partir del primer intercambio de la sesión, editable por el usuario y sin regenerarse tras edición manual. Verificación: test que edita el título y confirma que un turno nuevo no lo sobrescribe. `[modelo: haiku]`
- [x] 2.3 Endpoint `GET /sessions/{id}` (detalle): retorna el árbol completo de mensajes con `parent_id`, incluyendo ramas no activas (descartadas por edición o "Seguir con Flash"). Verificación: test que crea dos ramas y confirma que ambas aparecen en el árbol retornado. `[modelo: sonnet]`
- [x] 2.4 Endpoint `GET /sessions/search?q=` (búsqueda server-side por texto en título y contenido de mensajes de las sesiones propias). Verificación: test con término presente en un mensaje retorna la sesión con el término marcado; término ausente retorna lista vacía sin error. `[modelo: sonnet]`
- [x] 2.5 Lógica de "reanudar": abrir una sesión posiciona en su última rama activa; reconciliación si un turno seguía en streaming en otra pestaña (sin duplicar el turno). Verificación: test que abre la misma sesión desde dos "clientes" simulados durante un streaming y confirma que el turno aparece una sola vez. `[modelo: sonnet]`

## 3. UI — chat base (vista 05, assistant-ui)

- [x] 3.1 Componente de columna de mensajes con streaming: markdown, tablas y bloques de código con highlighting, cursor de bloque parpadeante mientras el turno está en curso. Verificación: prueba de componente con una tabla y un bloque de código en streaming, renderizados correctamente antes del cierre del turno. `[modelo: sonnet]`
- [x] 3.2 Sanitización anti-XSS del markdown renderizado (lista blanca de nodos/atributos sobre el AST, sin `dangerouslySetInnerHTML`/`innerHTML` con markdown crudo), aplicada tanto al texto del agente como al eco del mensaje del usuario. Verificación: test adversarial con un payload tipo `<script>`/`onerror=` que confirma que no se ejecuta ni aparece como HTML activo. `[modelo: sonnet]`
- [x] 3.3 Indicador de actividad plegado durante tool calls previas a la respuesta ("consultando…") + auto-scroll condicionado a que el usuario esté al final + botón flotante "Nuevos mensajes". Verificación: prueba de componente que simula scroll hacia arriba durante el streaming y confirma que aparece el botón en vez de forzar el scroll. `[modelo: sonnet]`
- [x] 3.4 Composer: Enter envía / Shift+Enter salto de línea, botón enviar↔detener según estado de streaming, deshabilitado con composer vacío, hint visible. Verificación: prueba de componente que cubre los tres estados (vacío, enviando, streaming). `[modelo: sonnet]`
- [x] 3.5 Sugerencias de inicio (`agent.starter_prompts`) clicables que precargan el composer con foco, sin enviar. Verificación: prueba de componente: click en sugerencia deja el texto en el composer sin turno enviado. `[modelo: sonnet]`
- [x] 3.6 Feedback 👍/👎 con popover de comentario opcional, reemplazo de voto al cambiar de ícono. Verificación: prueba de componente: votar sin comentario registra el voto; cambiar de 👍 a 👎 reemplaza el score anterior. `[modelo: sonnet]`

## 4. UI — capa de telemetría Técnico/Admin (vista 06)

- [x] 4.1 Backend: el contrato de salida del turno incluye costo, perfil, latencia y chips de cache hit/miss/write solo cuando el rol de la sesión de identidad es Técnico o Admin; el campo está ausente (no vacío) para Funcional. Verificación: test de contrato que confirma la ausencia total del campo para una sesión Funcional. `[modelo: sonnet]`
- [x] 4.2 UI: taxímetro de sesión en el header (Técnico/Admin) + fila de telemetría por turno con chips de cache y costo. Verificación: prueba de componente con datos de dos turnos que confirma la suma acumulada del taxímetro. `[modelo: sonnet]`
- [x] 4.3 UI: enlace "ver traza" visible solo para Admin, ausente para Técnico. Verificación: prueba de componente por rol que confirma la ausencia del enlace en Técnico. `[modelo: sonnet]`
- [x] 4.4 Estado degradado: si la traza no está disponible, taxímetro con `~` y tooltip "costo estimado" (solo Admin). Verificación: prueba de componente con traza no disponible simulada. `[modelo: haiku]`

## 5. UI — modelo alterno, escalación y ramas (vistas 06/08/09)

- [x] 5.1 Etiqueta "modelo alterno": visible para todos los roles con explicación simple para Funcional, nombre del perfil visible además para Técnico/Admin. Verificación: prueba de componente por rol sobre un turno marcado como modelo alterno. `[modelo: sonnet]`
- [x] 5.2 Tool calls colapsadas/expandibles consumiendo el contrato `tool-call-visibility` de `c09-mcp-tools`: lenguaje simple + resultado truncado para Funcional, parámetros completos + latencia para Técnico/Admin. Verificación: prueba de componente con el mismo tool call renderizado para ambas capas de rol. `[modelo: sonnet]`
- [x] 5.3 Tarjeta de escalación a Pro: razón, perfil de destino, botones "Continuar con Pro"/"Seguir con Flash", estados reposo/loading/escalada/descartada, idempotencia ante doble clic o doble pestaña, ausencia total de renderizado si el agente tiene la escalación deshabilitada. Verificación: prueba de componente que cubre los 4 estados más el caso de doble activación navegando a la misma sesión ya creada. `[modelo: opus]`
- [x] 5.4 Selector de versiones "versión N/M" para mensajes editados y respuestas regeneradas: alternar versión re-renderiza solo los mensajes posteriores de la rama seleccionada, con scroll anclado al mensaje ramificado, conservando la rama no seleccionada intacta. Verificación: prueba de componente que alterna entre dos ramas dos veces y confirma que ambas conservan su contenido exacto. `[modelo: opus]`
- [x] 5.5 Edición de mensaje: textarea inline con el texto original precargado, atenuación del resto del hilo, aviso "reprocesa N mensajes" cuando N≥3, sin aviso si se edita el último mensaje. Verificación: prueba de componente con N=6 y N=1 posteriores confirmando la presencia/ausencia del aviso. `[modelo: sonnet]`
- [x] 5.6 Indicador discreto de compaction en el punto de la conversación donde ocurrió. Verificación: prueba de componente con el indicador emitido por `context-compaction` de `b06`. `[modelo: haiku]`

## 6. UI — tarjetas de error accionables (vista 10)

- [x] 6.1 Tarjeta `GATEWAY_OFFLINE`: countdown de reintento con backoff (5→15→60 s), botón "Reintentar ahora", el mensaje original del usuario nunca se pierde y no se duplica al reintentar. Verificación: prueba de componente con countdown llegando a cero y disparando un reintento único. `[modelo: sonnet]`
- [x] 6.2 Tarjeta `QUOTA` (estado UI únicamente): composer deshabilitado con motivo inline, botón "Solicitar liberación" presente sin flujo de backend propio de este change. Verificación: prueba de componente que confirma el composer deshabilitado y el botón visible. `[modelo: sonnet]`
- [x] 6.3 Redacción por rol de ambas tarjetas: código mono visible arriba para Técnico/Admin, "código para soporte: X" en segundo plano y texto sin jerga para Funcional (textos ya definidos en `design/VISTAS/02-chat.md` vista 10). Verificación: prueba de componente por rol confirmando ambas redacciones. `[modelo: haiku]`

## 7. UI — historial de sesiones (vista 12)

- [x] 7.1 Lista de sesiones con buscador (debounce 300 ms), filtro por agente, tabs Activas/Archivadas con contador, fila con agente/título/última actividad/mensajes/indicador de ramas (`⑂ N`). Verificación: prueba de componente con una sesión de dos ramas mostrando el contador correcto. `[modelo: sonnet]`
- [x] 7.2 Estados vacío (primera vez / sin resultados de búsqueda / sin archivadas), carga (skeleton) y error con reintento (textos ya definidos en la vista 12). Verificación: prueba de componente por cada uno de los 4 estados. `[modelo: haiku]`
- [x] 7.3 Retomar sesión abre en la última rama activa con scroll al final; sesión con agente deshabilitado se puede leer pero el composer queda deshabilitado con motivo. Verificación: prueba de componente que abre una sesión con agente deshabilitado y confirma el composer inactivo. `[modelo: sonnet]`
- [x] 7.4 Columna de costo por sesión y total del período, visible solo para Admin. Verificación: prueba de componente por rol confirmando la ausencia de la columna para Técnico/Funcional. `[modelo: sonnet]`

## 8. Responsive

- [x] 8.1 Adaptación móvil de columna de mensajes, composer con área segura fija, acciones de turno y flechas del selector de ramas con objetivo táctil ≥44 px, tarjetas de error a ancho completo con botones apilados. Verificación: prueba de componente/visual en viewport móvil sobre las vistas 05, 08, 09 y 10. `[modelo: sonnet]`
- [x] 8.2 Adaptación móvil del historial (vista 12): búsqueda colapsada a ícono, acciones en menú por long-press. Verificación: prueba de componente/visual en viewport móvil sobre la vista 12. `[modelo: sonnet]`

## 9. Tests end-to-end de los flujos de diseño

- [x] 9.1 Test E2E Flujo B (sin citas, `design/FLUJOS.md`): turno con streaming, indicador de actividad, feedback 👍/👎 con comentario, turno visible en telemetría T/A. Verificación: el test recorre el flujo completo y pasa en CI. `[modelo: sonnet]`
- [x] 9.2 Test E2E Flujo G (edición → rama): editar un mensaje intermedio crea una rama, el selector "versión 1/2" aparece, alternar conserva ambas ramas con sus respuestas posteriores intactas. Verificación: el test recorre el flujo completo, incluida la aserción de invariante append-only (ningún mensaje original se modifica). `[modelo: opus]`
- [x] 9.3 Test E2E Flujo D (escalación): tarjeta de escalación aparece tras el evento de escalación, "Continuar con Pro" abre sesión nueva con perfil Pro y nota-enlace bidireccional, la sesión original permanece intacta, el marcador crudo nunca llega al cliente en ningún punto del flujo. Verificación: el test recorre el flujo completo y falla si el texto del marcador aparece en cualquier payload entregado al cliente. `[modelo: opus]`
- [x] 9.4 Test de contrato SSE: reconexión con `Last-Event-ID` tras un corte simulado no duplica fragmentos ni reinvoca al `LLMPort`. Verificación: el test corta y reconecta a mitad de un stream simulado y cuenta las invocaciones al doble de `LLMPort`. `[modelo: sonnet]`

## 10. Cierre

- [ ] 10.1 Review final del change: los tres capabilities (`chat-streaming`, `chat-experience`, `session-history`) tienen escenarios cubiertos por al menos un test; ningún endpoint expone el marcador de escalación crudo; las capas por rol se deciden server-side y no solo por CSS/ocultamiento en el cliente; consistencia entre `design.md`, specs y lo implementado. Verificación: checklist del reviewer en el PR. `[modelo: opus]`
