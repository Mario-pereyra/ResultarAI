## Why

Hoy el Default Chat no recuerda nada de un usuario entre conversaciones: cada sesión nueva arranca en blanco, y cualquier forma de "recordar" quedaría a discreción del modelo — exactamente lo que el producto rechaza (nada oculto, nada editable a espaldas del usuario, `design/VISTAS/06-mi-espacio.md` vista 24). `docs/07-roadmap.md` fila `e23` asigna esta capacidad a la Etapa E: memoria de perfil personal, transparente, con el agente limitado a **proponer** y el usuario en control total de ver/editar/borrar, inyectada como snapshot inmutable por sesión para no romper el prefijo cacheable ni el principio append-only.

## What Changes

- Se añade el bounded context de producto **memoria de usuario**: un texto de perfil por usuario (`memoria.texto`, límite ~1.000 tokens), versionado de forma append-only (cada guardado crea una versión nueva; ninguna versión anterior se sobrescribe ni se borra del historial).
- **El agente solo propone.** Cuando una respuesta del Default Chat incluye una propuesta de memoria, la app la detecta en el texto ya resuelto (fuera de cualquier bloque `<adjunto>`, mismo principio de exclusión anti-injection que el marcador de escalación de `b05-gateway-modelos`) y la UI la muestra inline con opciones "Guardar" / "Descartar". El agente **nunca** persiste una entrada por sí mismo.
- Se implementa la vista **Mi memoria** (`24-mi-memoria`, `/espacio/memoria`, cuarta tab del shell "Mi espacio" ya construido por `d18-mi-espacio`): editor con contador en vivo (~4 car./token), guardado con confirmación obligatoria y resumen del diff, "Borrar todo" con escribir-para-confirmar, historial de cambios de solo lectura (`versión`, `fecha`, `origen` ∈ vos · propuesta del agente aceptada, `cambio`, `tamaño`), y control de concurrencia optimista (edición en dos pestañas detectada y bloqueada sin merge silencioso).
- Se implementa el **validador de contenido prohibido**, fail-closed: credenciales/secretos y datos personales de clientes reales (PII estructurada) bloquean el guardado —tanto la edición manual como la aceptación de una propuesta— con el motivo exacto y la ubicación; si el validador no responde, no se guarda nada (sin validación no hay escritura). A diferencia del escaneo N2 de adjuntos (`d14-attachments`), aquí no existe checkbox de "son datos de prueba": PII real y credenciales bloquean sin excepción.
- Se implementa la **inyección de memoria como snapshot post-prefijo**: al crear una sesión nueva, se congela la versión vigente de `memoria.texto` en ese instante y se adjunta a la sesión, envuelta en un delimitador estructural (`<memoria_usuario id="…">…</memoria_usuario>`) declarado como dato-no-instrucción, insertado **inmediatamente después** del system prompt estático y **antes** del historial de turnos — preserva el cache del prefijo 100% estático (nada varía dentro de él) y dentro de la sesión el snapshot nunca cambia, aunque el usuario edite su memoria en otra pestaña o sesión mientras tanto (coherente con append-only / branch-never-rewrite).
- Se implementa el **indicador de memoria usada** en el chat (`d13-chat-conversacion` ya reservó el punto de extensión): indicador discreto en cada respuesta de una sesión cuyo snapshot de memoria no estaba vacío, con link a Mi memoria.
- Toda alta (propuesta aceptada), edición manual, borrado y uso (snapshot incluido al crear una sesión) queda como `AuditEvent` (contrato de `a03-core-gobernanza`) y, para el uso, también como traza consumible por `b07-observabilidad`.
- Se aplica **ownership estricto**: nadie —ni siquiera Admin— lee o edita la memoria de otro usuario desde este módulo; todo intento con un `user_id` ajeno se deniega y queda auditado como intento denegado (mismo contrato que `personal-space` de `d18-mi-espacio`).

## Capabilities

### New Capabilities

- `user-memory`: memoria de perfil por usuario (texto único versionado, ~1.000 tokens), propuesta-y-confirmación desde el chat, vista Mi memoria (ver/editar/borrar/historial), validador fail-closed de credenciales y PII real, snapshot post-prefijo inmutable por sesión, indicador de uso en chat y auditoría completa de alta/edición/borrado/uso.

### Modified Capabilities

*(ninguna — `user-memory` es nueva; consume sin modificar `audit-log` de `a03-core-gobernanza`, `conversation-persistence` de `b04-persistencia-postgres`, `agent-runtime` de `b06-runtime-grafos`, `observability-tracing` de `b07-observabilidad`, `chat-experience` de `d13-chat-conversacion` y `personal-space`/el shell de `d18-mi-espacio`)*

## No-objetivos

- **Sin memoria de proyecto/cliente compartida**: memoria administrada por Técnicos y compartida por equipo queda para Etapa P (`docs/07-roadmap.md`); este change es estrictamente memoria personal de un usuario.
- **Sin memoria automática/implícita**: el sistema jamás guarda una entrada sin una propuesta explícita del agente confirmada por el usuario, ni infiere/actualiza memoria a partir del historial de conversaciones sin ese paso. La memoria nunca contiene ni deriva del historial de conversaciones — es perfil, no transcript.
- **Sin RAG**: la memoria es un bloque de texto plano inyectado íntegro por snapshot, no un índice recuperable ni un `RetrievalPort` (ese puerto es de `a03-core-gobernanza`, puerta abierta sin implementar).
- **Sin modificar `escalation-marker` de `b05-gateway-modelos`**: la detección de la propuesta de memoria vive enteramente en `app/`, sobre el texto de respuesta ya resuelto por `LLMPort`; no se toca el gateway ni su contrato de salida.
- **Sin flag de habilitar/deshabilitar la propuesta por agente**: a diferencia del marcador de escalación, en este change la capacidad de proponer memoria está disponible de fábrica para todo agente; un campo de configuración por Agent Manifest queda fuera de alcance.
- **Sin el panel "Qué sabe la plataforma de vos" como contrato de backend**: es una lectura derivada y agrupada del mismo `memoria.texto`, resuelta client-side sin endpoint nuevo; no forma parte de las requirements de este spec.
- **Sin exportación ni API de memoria para integraciones externas.**
- **Sin cambios en `core/`**: no se introduce ningún bounded context ni Port nuevo en el hexágono; se reutilizan `AuditEvent` y los ports ya definidos por `a03-core-gobernanza`.

## Bounded context afectado

Slice vertical de producto: `resultarai/app/` (casos de uso de memoria: detección de propuesta sobre el texto de respuesta, guardado versionado, validación fail-closed, snapshot al crear sesión, consulta de historial, ownership) + `frontend/` (vista `24-mi-memoria` bajo la sección "Mi espacio" del shell ya construido por `d18-mi-espacio`, e indicador de memoria usada en el chat de `d13-chat-conversacion`). No introduce lógica de dominio nueva en `core/`.

## Impact

- `resultarai/app/user_memory/` (o equivalente): casos de uso de propuesta/aceptación/rechazo, guardado versionado con validación, snapshot por sesión, historial, ownership.
- `resultarai/app/api/`: endpoints REST `GET /me/memory`, `PUT /me/memory` (edición manual, con `base_version` para concurrencia optimista), `DELETE /me/memory` (borrar todo), `GET /me/memory/history`, `POST /me/messages/{id}/memory-proposal/accept` y `.../reject` (o equivalente del flujo de propuesta inline en el turno de chat).
- `frontend/`: vista `24-mi-memoria` conforme a `design/VISTAS/06-mi-espacio.md` (quinta— en realidad cuarta— tab de "Mi espacio"), y el indicador de memoria usada + la propuesta inline sobre la UI de chat ya construida por `d13-chat-conversacion`.
- Depende de (archivados o con interfaz ya especificada): `a01-fundacion-repo` (esqueleto), `a03-core-gobernanza` (`AuditEvent`), `b04-persistencia-postgres` (persistencia append-only, patrón de versionado/ramas), `b05-gateway-modelos` (patrón de marcador y exclusión anti-injection, como precedente, sin modificarlo), `b06-runtime-grafos` (ciclo de vida de creación de sesión, punto de enganche del snapshot), `b07-observabilidad` (traza de uso), `d10-design-system-shell` (shell, tokens, componentes), `d13-chat-conversacion` (UI de chat, punto de enganche del indicador y la propuesta inline), `d18-mi-espacio` (shell de "Mi espacio" y sus tabs).
- Referencia normativa: `design/VISTAS/06-mi-espacio.md` (vista 24 — Mi memoria), `design/FUNCIONALIDADES.md` §4 (indicador de memoria usada, propuesta de guardar) y §10 (Mi memoria), `design/mockups/24-mi-memoria.html`, `design/ANEXO-ATTACHMENTS.md` §4.3/§4.4 (patrón de delimitación estructural y niveles N2/N3, citados como precedente, no redefinidos).
