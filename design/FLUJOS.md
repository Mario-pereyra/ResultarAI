# FLUJOS.md — Flujos end-to-end · Resultar Agents Platform

> Documentación de diseño — no código de producción. Cada flujo referencia las vistas por nombre de archivo de mockup en [`mockups/`](mockups/index.html). Specs detalladas en [`VISTAS/`](VISTAS/).

---

## Flujo A — Primer acceso de un usuario nuevo

Actores: Admin (alta) y usuario nuevo (rol Funcional "lucia").

1. **Admin** entra a Gestión de usuarios (`31-admin-usuarios.html`) → "Crear usuario": nombre, correo, rol (Funcional), grupo, cuota heredada del grupo. No existe registro público.
2. **Sistema** genera contraseña temporal de un solo uso y la muestra una única vez al Admin, que la entrega por canal interno. El alta queda en el audit log (`37-admin-audit.html`).
3. **Usuario** abre la plataforma → Login (`01-login.html`), ingresa correo + contraseña temporal. (Si fuera Admin, el login exigiría además TOTP.)
4. **Sistema** detecta primer ingreso → wizard de Primer acceso (`02-primer-acceso.html`): cambio obligatorio de contraseña, idioma (ES, preparado PT-BR), tema dark/light.
5. **Usuario** lee y marca el **checkbox del acuerdo de uso** (datos N0–N3, "verificá antes de aplicar en cliente"). El sistema audita fecha/hora/versión del acuerdo — sin marcarlo no se avanza.
6. **Sistema** muestra el shell (`03-shell.html`): sidebar con Catálogo, Workflows, Aprobaciones (si aplica), Mi espacio; banner permanente "respuestas generadas por IA".
7. **Usuario** abre el Catálogo (`13-catalogo.html`), elige DocAgent y entra a su ficha (`14-ficha-agente.html`) — versión Funcional: descripción, ejemplos, sin jerga técnica.
8. **Usuario** pulsa "Iniciar conversación" → chat limpio tipo ChatGPT (`05-chat-funcional.html`) y envía su primera pregunta.

## Flujo B — Consulta documental con cita y feedback

1. **Usuario** en chat con DocAgent (`05-chat-funcional.html`) pregunta: "¿Qué parámetro controla la numeración de facturas en Bolivia?".
2. **Sistema** muestra streaming con indicador de actividad ("buscando en TDN…").
3. **Sistema** responde con citas obligatorias inline [1][2]; el panel de evidencia (`11-citas.html`) lista cada fuente: título TDN/CST, fragmento citado, fecha y enlace.
4. **Usuario** expande la cita [1] para ver el fragmento exacto que sustenta la afirmación.
5. Caso alternativo — sin evidencia: el agente **se abstiene** explícitamente ("No encontré documentación que respalde una respuesta") en lugar de inventar; ofrece reformular o escalar.
6. **Usuario** califica el turno con 👍/👎; ante 👎 se pide motivo breve.
7. **Sistema** registra el feedback vinculado al turno y a la versión de prompt activa — insumo para evals (`43-admin-evals.html`). Para Técnico/Admin el mismo turno muestra además telemetría (`06-chat-admin.html`).
8. La conversación queda en el historial de sesiones (`12-historial.html`).

## Flujo C — Validación completa de módulo (bridge + HITL + informe GAP)

1. **Técnico** abre ValidationAgent desde el catálogo (`14-ficha-agente.html`); el agente exige contexto antes de operar.
2. **Sistema** muestra el selector de cliente-final y ambiente (`27-selector-cliente-ambiente.html`): "Comercial Andina S.A." / ambiente QA, con nivel de datos (N1) y estado del bridge/VPN visible.
3. Si el bridge está caído: estado accionable `BRIDGE_OFFLINE` / `VPN_OFFLINE` (`10-errores.html`) con pasos de reconexión; no se puede continuar.
4. **Técnico** elige el checklist de parametrización del módulo (p. ej. Facturación BOL) desde Gestión de checklists (`28-checklists.html`); si el checklist fue convertido desde un XLSX, pasó antes por revisión humana (`29-checklist-review.html`).
5. **Sistema** ejecuta la validación punto por punto (SX3/SX6 vía consultas de solo lectura), mostrando progreso por ítem en el chat.
6. El agente detecta un parámetro corregible y propone una escritura → **pausa HITL**: la corrida se detiene y se crea una solicitud en la cola de aprobaciones (`20-aprobaciones-cola.html`).
7. **Aprobador** abre el detalle (`21-aprobacion-detalle.html`): payload exacto, cliente/ambiente, nivel de riesgo, expiración. En riesgo crítico el comentario es obligatorio; lo irreversible exige segunda aprobación.
8. **Aprobador** aprueba (o rechaza). La decisión queda en el historial (`22-aprobaciones-historial.html`) y la corrida se reanuda.
9. **Sistema** entrega el informe GAP final: ítems OK / desviados / no verificables, con evidencia por ítem, exportable. La sesión queda trazada en `12-historial.html`.

## Flujo D — Escalación a Pro

1. **Usuario** hace una pregunta compleja; el modelo default (`deepseek-v4-flash`) detecta que excede su capacidad y emite el marcador `<<<NEEDS_PRO>>>`.
2. **Sistema** lo traduce en una tarjeta de escalación (`08-escalacion.html`): "Esta consulta puede requerir el modelo Pro" + botón único "Continuar con Pro". Nunca escala solo — la escalación es **manual** y configurable por agente.
3. **Usuario** hace clic en "Continuar con Pro".
4. **Sistema** abre una **nueva conversación/rama** (stickiness de modelo: una sesión vive en un solo perfil), re-planteando la consulta con el contexto necesario.
5. **Sistema** muestra a todos los roles la etiqueta de modelo cuando hubo fallback ("modelo alterno"); Técnico/Admin ven además el detalle de costo (`06-chat-admin.html`).
6. Si el usuario no escala, puede seguir en flash con una respuesta de mejor esfuerzo; la rama original queda intacta.

## Flujo E — Cuota agotada → solicitud → liberación

1. **Usuario** conversa normalmente; al cruzar el **80%** de su cuota el sistema muestra un aviso no bloqueante (toast + barra en `23-mi-consumo.html`).
2. **Usuario** llega al **100%** → bloqueo: el composer se deshabilita y aparece el estado `QUOTA` (`10-errores.html`) con botón "Solicitar liberación".
3. **Usuario** pulsa el botón y agrega un motivo breve ("cierre de mes con Comercial Andina S.A.").
4. **Sistema** crea la solicitud y notifica al Admin por el centro de notificaciones (`04-notificaciones.html`).
5. **Admin** la atiende en Cuotas y liberaciones (`33-admin-cuotas.html`): ve consumo del usuario/grupo, motivo, y aprueba una ampliación puntual o permanente (o rechaza con motivo).
6. **Sistema** notifica al usuario; el chat se desbloquea al instante. Toda la cadena queda auditada (`37-admin-audit.html`) y visible para el usuario en su auditoría personal (`25-mi-auditoria.html`).

## Flujo F — Publicación de nueva versión de prompt

1. **Admin** entra al Registro de Prompts (`34-admin-prompts.html`) y crea un **draft** a partir de la versión activa del system prompt de DocAgent (las versiones publicadas son inmutables — nunca se edita en caliente).
2. **Admin** edita el draft con diff lado a lado contra la versión activa.
3. **Admin** lanza los **evals** del draft (`43-admin-evals.html`): el runner ejecuta el dataset del agente; score < 80% bloquea, casos `safety` son hard-fail individual.
4. **Sistema** aplica el gate: con evals verdes habilita "Publicar"; en rojo, el botón queda deshabilitado con el detalle de los casos fallados.
5. **Admin** publica → la versión queda inmutable y numerada; **activar** la apunta como runtime sin deploy. Ambas acciones quedan en el audit (`37-admin-audit.html`).
6. **Sistema** espeja un snapshot en `prompts/` (Git) para code review; los chats nuevos toman la versión activa (las sesiones en curso no se reescriben).
7. Si algo sale mal en producción: **rollback** con un clic a la versión anterior desde la misma vista, también auditado; el bug se convierte en caso de regresión en `evals/`.

## Flujo G — Edición de mensaje → rama nueva

1. **Usuario** revisa una conversación y nota que formuló mal una pregunta tres turnos atrás.
2. **Usuario** pulsa "Editar" sobre su mensaje (`09-branching.html`).
3. **Sistema** abre el texto en edición dejando claro que se creará una **versión nueva** — la historia jamás se reescribe (append-only, `parent_id`).
4. **Usuario** envía el texto corregido.
5. **Sistema** crea una rama desde ese punto y responde sobre ella; aparece el selector "versión 1/2" en el mensaje editado.
6. **Usuario** alterna entre ramas con el selector; cada rama conserva sus respuestas posteriores intactas.
7. En el historial (`12-historial.html`) la sesión indica que tiene ramas; ambas son recuperables siempre.

## Flujo H — Subida de archivo XLSX al chat

1. **Usuario** arrastra `parametros-facturacion.xlsx` al composer (`07-composer-attachments.html`).
2. **Sistema** valida tipo y tamaño y muestra el chip del archivo en estado **Subiendo** (barra de progreso).
3. **Sistema** pasa a **Extrayendo**: pipeline transparente (hojas detectadas, filas/columnas leídas) — el usuario ve qué se extrajo, no una caja negra (ver `ANEXO-ATTACHMENTS.md`).
4. **Sistema** llega a **Listo**: resumen de extracción ("2 hojas, 148 filas") con vista previa expandible; si el archivo contiene datos N3 (personales/credenciales) la UI **advierte** que no deben enviarse al LLM.
5. Caso de error: estado **Falló** accionable (formato corrupto, hoja vacía) con opción de reintentar o quitar el adjunto.
6. **Usuario** escribe la consulta y envía; solo el contenido extraído (truncado por relevancia) viaja como contexto, marcado como dato no confiable (anti prompt-injection).
7. **Sistema** responde citando celdas/hojas concretas del archivo cuando corresponde.

## Flujo I — Kill-switch de un agente

1. **Admin** detecta un comportamiento anómalo en ValidationAgent (alerta en `30-admin-dashboard.html` o `39-admin-salud.html`).
2. **Admin** va a Flags y kill-switch (`38-admin-flags.html`) y apaga el agente; en acción crítica el sistema pide confirmación + motivo (y TOTP ya está garantizado por su sesión Admin).
3. **Sistema** aplica el corte de inmediato: rechaza turnos nuevos hacia ese agente, deja terminar (o aborta con aviso) los streams en curso y congela las aprobaciones HITL pendientes de ese agente marcándolas "agente suspendido".
4. **Lo que ven los usuarios**: en el catálogo (`13-catalogo.html`) la ficha aparece "No disponible temporalmente"; en chats abiertos, estado accionable tipo `GATEWAY_OFFLINE` (`10-errores.html`) con texto claro sin jerga: "Este agente está en mantenimiento. Tu conversación quedó guardada." Sin detalles internos para Funcional; Técnico ve el flag en la ficha técnica.
5. **Sistema** notifica a usuarios con sesiones activas vía centro de notificaciones (`04-notificaciones.html`) y registra el evento en el audit (`37-admin-audit.html`).
6. **Admin** corrige la causa (p. ej. rollback de prompt, flujo F) y reactiva el flag; el catálogo y los chats se restauran y se notifica la vuelta al servicio.
