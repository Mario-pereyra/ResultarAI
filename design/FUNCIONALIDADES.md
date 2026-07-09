# FUNCIONALIDADES — Mapa funcional completo del producto

> **Estado:** documentación de diseño · 11 junio 2026
> **Alcance:** mapa exhaustivo de TODO el producto terminado (Resultar Agents Platform), organizado por módulo. No es un plan de sprint: las fases indican en qué etapa del producto entra cada funcionalidad.
> **Fuentes normativas:** UX-SPEC, ADR-0001/0006 (cache-first), ADR-0002 (topología MCP/VPN), ADR-0004 (evals), ADR-0007 (infraestructura/cuotas), ADR-0008 (UI chat), ADR-0010 (memoria/skills/workflows), ADR-0011 (registro de prompts), ADR-0012 (gateway), ADR-0013 (identidad), ADR-0014 (niveles de datos), ANEXO-ATTACHMENTS, AUDITORIA-ARQUITECTONICA-2026-06-11.

---

## Convenciones

**Modelo de despliegue:** instancia por cliente. Cada consultora despliega la suya; branding, catálogo, usuarios y límites son **configuración de instancia**, jamás forks de código. Primera instancia: Resultar Bolivia (~30 consultores).

**Roles (cerrado — codifican capacidades, no antigüedad):**

| Rol | Resumen |
|---|---|
| **Admin** | Gobierna todo: telemetría, consola admin, gobernanza, builders, registro de prompts. TOTP obligatorio. |
| **Técnico** | Consulta + toca ambientes/valida/desarrolla. Ve la **ficha técnica** de agentes (tools, costo, versión de prompt, evals). **NO ve telemetría global.** |
| **Funcional** | Experiencia limpia tipo ChatGPT: cero jerga técnica, cero costos, cero menciones de cache. |

**Una sola UI compartida** con agregados por capa de capacidades — jamás interfaces separadas por rol. La **visibilidad** (qué agentes y secciones ve cada rol) es configurable por el Admin, no hardcodeada.

**Fases:**

| Fase | Contenido |
|---|---|
| **F1 — Núcleo** | Acceso, shell, chat, DocAgent, catálogo, attachments, cuotas, administración y gobernanza base, builders solo-Admin. |
| **F2 — Validación/HITL** | ValidationAgent, contexto cliente/ambiente, bridge/VPN, aprobaciones HITL, workflows, memoria de usuario, skills. |
| **F3 — Dev** | DevAgent (solo-sugerencia con diffs), creación self-service, memoria de proyecto compartida, activación PT-BR. |

**Columna "Roles":** A = Admin, T = Técnico, F = Funcional. "Todos" = A+T+F. Cuando la visibilidad es configurable se indica el default.

---

## 1. Acceso e identidad (ADR-0013)

| Funcionalidad | Descripción | Roles | Fase | Notas de comportamiento |
|---|---|---|---|---|
| Login usuario + contraseña | Autenticación local (Better Auth embebido, schema propio en Postgres). Identidad canónica = username corto estable; displayName solo presentación. | Todos | F1 | Sin auth artesanal. Errores de login genéricos (no revelan si la cuenta existe). |
| TOTP obligatorio para Admin | Segundo factor TOTP exigido por sistema a toda cuenta Admin; sin TOTP configurado no se accede a capacidades de Admin. | A | F1 | Enrolamiento guiado en primer login Admin (QR + códigos de respaldo). |
| TOTP opcional para Técnico/Funcional | Activable desde configuración personal. | T, F | F1 | Revisión del "opcional" al crecer en usuarios (trigger ADR-0013). |
| Sin registro público | No existe pantalla de registro. Las cuentas las crea solo el Admin desde la consola; el rol viene de la cuenta y el usuario jamás lo elige. | Todos (afecta) | F1 | Plataforma interna. El alta vive en §11 (Administración). |
| Acuerdo de uso auditado | Checkbox de aceptación de la política de uso (solo datos de prueba hacia la IA, verificación antes de aplicar en cliente) en el **primer login**. | Todos | F1 | La aceptación queda en audit log (usuario, versión del texto, timestamp). Cambio del texto → re-aceptación. |
| Sesión server-side firmada | Sesiones con revocación y timeout; reemplaza cualquier cookie sin firmar. | Todos | F1 | Revocación individual o total por el Admin (§11). `userId` se deriva de la sesión, nunca del body. |
| Cambio de contraseña propio | Desde configuración personal, con contraseña actual. | Todos | F1 | — |
| Cierre de sesión | Logout explícito + expiración por inactividad. | Todos | F1 | — |
| Gateway no público | El gateway LLM (:4111) no se expone a internet; token de servicio web↔platform; validación de ownership de `sessionId`. | — (técnico) | F1 | Invisible para el usuario; condición de seguridad de todo lo demás. |

---

## 2. Shell y navegación

| Funcionalidad | Descripción | Roles | Fase | Notas de comportamiento |
|---|---|---|---|---|
| Shell única por capacidades | Navegación lateral cuyas secciones aparecen/desaparecen según la matriz de capacidades del rol y la visibilidad configurada. | Todos | F1 | Jamás dos apps: el Funcional ve un subconjunto del mismo shell. |
| Secciones principales | Chat (historial), Catálogo de agentes, **Workflows (sección propia)**, Aprobaciones, Mi espacio, Notificaciones; + Telemetría, Administración, Gobernanza, Builders para Admin. | Según rol | F1–F2 | Workflows separado del catálogo de agentes por decisión de producto. |
| Historial de conversaciones | Lista de sesiones propias con título, agente, fecha; búsqueda por texto. | Todos | F1 | Una sesión vive en un solo `model_profile` (stickiness); las ramas cuelgan de la misma sesión. |
| Banner permanente de IA | "Respuestas generadas por IA — verificá antes de aplicar en cliente", discreto y persistente en el área de chat. | Todos | F1 | No se puede ocultar; estilo no intrusivo. |
| Branding por instancia | Logo, nombre y brand de tokens (`default` sala-de-control / `totvs`) definidos en configuración de instancia. | Todos | F1 | Atributos `html[data-brand="default|totvs"]`. |
| Selector de tema dark/light | Conmutador personal; dark por defecto. | Todos | F1 | `html[data-theme="dark|light"]`; ambos temas completos en ambos brands. |
| Estados globales accionables | `GATEWAY_OFFLINE` (plataforma caída → pantalla con estado y reintento), `QUOTA` (ver §4), `VPN_OFFLINE` / `BRIDGE_OFFLINE` (ver §9). | Todos | F1 (gateway/quota), F2 (vpn/bridge) | Nunca un error críptico: cada estado dice qué pasó y qué hacer. |
| Indicador de identidad | Avatar/username + rol visible; acceso a Mi espacio y logout. | Todos | F1 | El rol se muestra, no se elige. |

---

## 3. Notificaciones

Sin push ni email en MVP (fuera de alcance explícito): todo es **in-app**, centro de notificaciones con campana e indicador de no-leídas.

| Funcionalidad | Descripción | Roles | Fase | Notas de comportamiento |
|---|---|---|---|---|
| Centro de notificaciones | Panel con notificaciones propias, marcar leído, ir-al-origen (deep link a sesión/tarjeta/solicitud). | Todos | F1 | Contenido filtrado por rol y ownership. |
| Solicitud de liberación de cuota | El Admin recibe la solicitud generada por el botón "Solicitar liberación" (usuario, cuota afectada, consumo actual). | A | F1 | Acción directa desde la notificación → §11 Cuotas. |
| Resultado de liberación | El solicitante es notificado de liberación otorgada o denegada. | Todos | F1 | La decisión queda en audit log. |
| Aprobación HITL pendiente | Notifica tarjetas HITL que esperan decisión, incluyendo segundas aprobaciones de acciones irreversibles. | T, A | F2 | Incluye cliente/ambiente y riesgo; deep link a la tarjeta. |
| Expiración de tarjeta HITL | Aviso previo a expirar y notificación de expirada (auto-rechazo). | T, A | F2 | La expiración queda auditada como rechazo por timeout. |
| Workflow terminado / fallido | Fin de ejecución de workflow (ok, con errores, cancelado) con link al resultado. | Según visibilidad | F2 | Útil en ejecuciones largas; el usuario puede salir de la pantalla. |
| Novedades de catálogo | Aviso opcional de agente/workflow nuevo o versión nueva visible para el rol. | Todos | F2 | Configurable por instancia; apagado por defecto. |

---

## 4. Chat y conversación (ADR-0006/0008, UX-SPEC §2)

| Funcionalidad | Descripción | Roles | Fase | Notas de comportamiento |
|---|---|---|---|---|
| Chat streaming | Respuestas en streaming con markdown, tablas y código con highlighting (assistant-ui). | Todos | F1 | — |
| Edición de mensaje = rama nueva | Editar cualquier mensaje propio crea una rama; selector visible "versión 1/2" en el punto de bifurcación. **La historia jamás se reescribe** (branch-never-rewrite). | Todos | F1 | Tabla `messages` con `parent_id`; la rama original nunca se pierde. Las ramas comparten adjuntos y prefijo cacheado. |
| Regenerar respuesta | Regenerar desde cualquier punto = rama nueva con el mismo selector de versiones. | Todos | F1 | — |
| Aviso de regeneración costosa | Aviso suave al editar muy atrás en sesiones largas (costo de regenerar todo lo posterior). | Todos | F1 | Solo informa; no bloquea. |
| Escalación manual a Pro | Cuando el modelo emite `<<<NEEDS_PRO>>>`, la UI ofrece **un botón de un clic** que abre **una NUEVA conversación/rama** con `deepseek-v4-pro`. Jamás escala sola. | Todos | F1 | **Configurable por agente** (el Admin puede deshabilitar la escalación por agente). Un documento adjunto no puede disparar el marcador (defensa anti-inyección, ANEXO §4.3). |
| Etiqueta "modelo alterno" | Cuando una respuesta se generó por fallback de modelo (cascada ADR-0006), el mensaje lleva una etiqueta discreta visible **para TODOS los roles**. | Todos | F1 | Transparencia sin jerga: el Funcional ve "respondido con modelo alterno", el Técnico/Admin ven además qué perfil. |
| Stickiness de modelo | Una sesión vive en un solo `model_profile`; cambiar de modelo = rama/sesión nueva explícita. | Todos | F1 | Nunca se mezclan modelos dentro de una rama. |
| Tool calls visibles | Lecturas se ejecutan directo y aparecen **colapsadas y expandibles** (qué tool, contra qué, resultado truncado). Escrituras → tarjeta HITL (§8). | Todos | F1 (lecturas), F2 (escrituras) | Para el Funcional la vista expandida usa lenguaje simple; el Técnico ve parámetros completos. |
| Citas obligatorias (DocAgent) | Respuestas documentales con citas a la fuente (TDN/CST) y **abstención explícita sin evidencia** ("no encontré respaldo para esto"). | Todos | F1 | El agente responde en el idioma del usuario y cita la fuente en su idioma original (PT-BR frecuente). |
| Feedback por respuesta | Thumbs up/down + comentario opcional en cada respuesta, desde el día 1. | Todos | F1 | Va a Langfuse ligado a la traza; thumbs-down con comentario se revisa y se convierte en eval de regresión. El feedback se conserva siempre (exento de purga de 90 días). |
| Aviso de cuota al 80% | Aviso no intrusivo en el composer al alcanzar el 80% del presupuesto diario. | Todos | F1 | Umbral configurable por instancia. |
| Bloqueo de cuota al 100% | Bloqueo claro ("alcanzaste tu límite diario, se renueva a medianoche") + botón **"Solicitar liberación"** que notifica al Admin. | Todos | F1 | La cuota se evalúa ANTES de cada llamada LLM: global→grupo→usuario→sesión. |
| Indicador de memoria usada | Indicador discreto cuando una respuesta usó la memoria del usuario. | Todos | F2 | Link a "Mi memoria" (§10). |
| Propuesta de guardar en memoria | El agente **nunca guarda solo**: propone "¿guardo esto en tu memoria?" y el usuario confirma o rechaza inline. | Todos | F2 | La entrada aparece editable en Mi memoria. |
| Compactación de contexto | Compaction al 80% de la ventana, **una sola vez**, en frontera de turno; indicador discreto de que la sesión fue compactada. | Todos | F1 | El usuario puede repedir contenido (p. ej. releer un adjunto) y entra como mensaje nuevo. |
| Tarjetas de error en chat | `VPN_OFFLINE` → tarjeta con cliente/ambiente afectado + instrucción de activar la VPN; `BRIDGE_OFFLINE` → "tu tat-mcp no está conectado" + comando para levantarlo; `QUOTA` → ver arriba. | Todos | F2 | Estados de error como ciudadanos de primera clase; siempre accionables. |
| Ejemplos clicables | Los 3 prompts de ejemplo de la ficha del agente precargan el composer. | Todos | F1 | Onboarding integrado al producto. |
| Indicador de nivel de datos | La sesión muestra su nivel N0–N3 cuando aplica (heredado por escalación y fallback); la UI advierte antes de acciones que lo violarían. | Todos | F2 | N3 jamás sale a un LLM: scrubber en gateway bloquea y registra (ADR-0014). Si no hay proveedor permitido para el nivel, error claro — nunca se degrada el nivel. |

---

## 5. Attachments (ANEXO-ATTACHMENTS)

| Funcionalidad | Descripción | Roles | Fase | Notas de comportamiento |
|---|---|---|---|---|
| Subida de archivos al chat | Drag & drop / selector; máx. 5 adjuntos por mensaje; límites de tamaño por tipo (matriz ANEXO §9). | Todos | F1 | Todos los límites son configuración de instancia/agente, no constantes. |
| Chip de estados | Estados visibles: subiendo → procesando → listo / advertencia / **bloqueado** / error, cada uno con causa específica. | Todos | F1 | Jamás fallar en silencio (anti-patrón Copilot documentado). |
| Extracción server-side a texto | XLSX/CSV (esquema+muestra), PDF (texto nativo por página), DOCX (Markdown estructurado), TXT/MD/código/logs (directo). El archivo nunca viaja al LLM; viaja su extracción, **al final del contexto**. | Todos | F1 | Determinista, almacenada una vez; envuelta en `<adjunto id=…>` declarado como dato-no-instrucción en el system prompt estático. |
| Vista previa "Ver lo que verá el agente" | Panel con la extracción exacta (incl. marcadores de truncado) + tokens estimados y % del archivo incluido. | Todos | F1 | Para Funcional el conteo se muestra como "% del espacio del mensaje"; Técnico/Admin ven tokens. Diferencial frente a ChatGPT/Claude. |
| Truncado por relevancia, una sola vez | Si excede el presupuesto (12k tokens/archivo, 24k/mensaje por defecto), se trunca al insertar con marcadores explícitos. Nunca se re-trunca (reescribiría historia). | Todos | F1 | Pedir otra parte del archivo inserta un fragmento nuevo desde `full_text`, sin re-procesar. |
| Escaneo N3 → bloqueo | Credenciales/secretos detectados (claves API, `Password=`, cadenas de conexión) bloquean el adjunto: no se puede enviar hasta quitar el secreto. | Todos | F1 | Mensaje accionable con línea/ubicación. Resultado del escaneo visible para Admin en telemetría. |
| Escaneo N2 → confirmación auditada | PII estructurada detectada → advertencia con detalle + checkbox "Confirmo que son datos de prueba", registrado en audit log. | Todos | F1 | Coherente con la política solo-datos-de-prueba. Cancelar siempre disponible. |
| Detección de instrucción embebida | Heurística anti prompt-injection: el texto sospechoso no bloquea, pero advierte al usuario y marca la traza en Langfuse. | Todos | F1 | Mitigación de fondo: toda escritura pasa por HITL igual. |
| Validación y rechazos de seguridad | Allowlist de extensiones + magic bytes; rechazo de macros (.xlsm/.docm), comprimidos, ejecutables, .doc antiguo, PDF con contraseña. | Todos | F1 | Mensajes que educan ("guardalo como .xlsx sin macros"). |
| Imágenes — rechazo claro (V1) | Sin visión: rechazo con alternativa accionable ("pegá el texto del error / exportá a PDF o Excel"). | Todos | F1 | — |
| OCR opt-in (PDF escaneado e imágenes) | Oferta explícita de OCR (tesseract `spa`), resultado etiquetado `[OCR]`, **vista previa obligatoria** antes de adjuntar. | Todos | F2 | Límite 20 páginas; advertencia de fidelidad. Visión real por API de terceros queda diferida como capacidad/perfil aparte. |
| Almacenamiento y retención | Binario 90 días (default por instancia); `inserted_text` vive lo que viva la conversación; dedup por sha256; descarga solo dueño y Admin (auditada). Sin URLs públicas, sin S3 externo. | Todos / A | F1 | Los documentos del cliente no salen de la instancia. |
| Adjuntos en workflows | El formulario del workflow declara archivos esperados (tipo y presupuesto fijados por el workflow). | Según visibilidad | F2 | La extracción entra en la posición que el workflow define, post-prefijo estático. |

---

## 6. Catálogo de agentes (UX-SPEC §3)

| Funcionalidad | Descripción | Roles | Fase | Notas de comportamiento |
|---|---|---|---|---|
| Catálogo filtrado por rol | Grilla de agentes publicados, filtrada por la **matriz de visibilidad agente×rol** que administra el Admin. | Todos | F1 | Un Funcional no ve agentes cuyo toolset excede sus permisos. "Un agente que nadie sabe que existe no se usa." |
| Ficha de agente (capa común) | Nombre, descripción, casos de uso ideales, usuario objetivo, owner y **3 ejemplos de prompts clicables** ("primeros pasos"). | Todos | F1 | La ficha ES el onboarding. |
| Ficha técnica (capa T/A) | Tools que usa, modelo/perfil LLM, costo estimado por sesión, **versión de prompt activa**, score de evals vigente. | T, A | F1 | Oculta para Funcional (cero jerga/costos). |
| Iniciar conversación | Botón que abre sesión nueva con el agente (con selector de contexto si toca Protheus, §9). | Todos | F1 | La sesión nace con el snapshot de memoria post-prefijo (ADR-0010). |
| Estado del agente | Si el kill-switch del agente está apagado (§12), el agente aparece deshabilitado con mensaje claro o se oculta (configurable). | Todos | F1 | Apagado efectivo < 1 min, sin deploy. |
| Indicador de escalación | La ficha indica si el agente permite escalación a Pro y a qué perfil. | T, A | F1 | Para Funcional solo se manifiesta como el botón post-`<<<NEEDS_PRO>>>`. |
| Agentes del producto | **DocAgent** (documental TDN/CST, citas obligatorias, abstención sin evidencia) — F1. **ValidationAgent** (checklists de parametrización, contexto cliente/ambiente, HITL) — F2. **DevAgent** (AdvPL/TLPP, solo-sugerencia con diffs, jamás aplica cambios) — F3. | Según visibilidad | F1–F3 | DevAgent nunca ejecuta ni escribe: entrega diffs propuestos para revisión humana. |

---

## 7. Workflows — sección propia (ADR-0010 §workflows, UX-SPEC §10d)

Los workflows deterministas son un **tipo de ítem propio del producto, en sección separada del catálogo de agentes**: se ejecutan con formulario, no con chat.

| Funcionalidad | Descripción | Roles | Fase | Notas de comportamiento |
|---|---|---|---|---|
| Listado de workflows | Workflows publicados visibles según matriz workflow×rol. | Según visibilidad | F2 | Misma lógica de visibilidad que agentes; default: Técnico+Admin. |
| Ficha de workflow | Nombre, qué produce, pasos que ejecuta, inputs requeridos, costo estimado por ejecución, owner. | Según visibilidad | F2 | Capa técnica (modelo/tools por paso) solo T/A. |
| Ejecución por formulario | Formulario tipado de inputs (cliente/ambiente/módulo, parámetros, archivos esperados). Validación antes de ejecutar. | Según visibilidad | F2 | El selector cliente/ambiente respeta los perfiles asignados al usuario. |
| Pasos con estado en vivo | Lista de pasos con estado (pendiente / en curso / completado / fallido / esperando aprobación), streaming de progreso. | Según visibilidad | F2 | Determinista: el orden y los pasos son fijos por versión del workflow. |
| Pausa HITL en pasos de escritura | Un paso de escritura pausa la ejecución y muestra la **tarjeta de aprobación estándar** (§8); al decidir, continúa o aborta. | T, A | F2 | Misma tarjeta, mismas reglas (expiración, segunda aprobación). |
| Resultado descargable | Informe final descargable (xlsx / md), p. ej. informe GAP de validación de módulo. | Según visibilidad | F2 | El resultado queda asociado a la ejecución. |
| Historial de ejecuciones | Ejecuciones propias consultables (inputs, estado, resultado, costo); Admin ve todas. | Todos los que ejecutan / A | F2 | Re-ejecutar precarga el formulario con los mismos inputs. |
| Cancelación | Cancelar una ejecución en curso (los pasos ya ejecutados quedan registrados; nada se revierte solo). | Dueño, A | F2 | Cancelación auditada. |

---

## 8. Aprobaciones HITL (UX-SPEC §5)

Regla dura: **jamás SQL write a Protheus**; toda escritura va por API REST oficial y se detiene en una tarjeta de aprobación. Sin aprobación no se ejecuta.

| Funcionalidad | Descripción | Roles | Fase | Notas de comportamiento |
|---|---|---|---|---|
| Tarjeta de aprobación | Toda tool call de escritura (POST/PUT/DELETE, cambios MV_*/SX6, rutinas con efectos fiscales) muestra: **qué se va a hacer, payload completo, cliente/ambiente destino, nivel de riesgo**, botones Aprobar/Rechazar. | T, A | F2 | Aparece inline en el chat o pausa el workflow. El Funcional no tiene agentes con tools de escritura (visibilidad por matriz). |
| Comentario obligatorio en críticos | Acciones clasificadas críticas exigen comentario del aprobador antes de habilitar "Aprobar". | T, A | F2 | El comentario queda en el audit log. |
| Expiración de la tarjeta | Tarjeta con tiempo de vida; al expirar = rechazo automático auditado. | T, A | F2 | Aviso previo vía notificaciones (§3). |
| Segunda aprobación (4 ojos) | Acciones **irreversibles** requieren una segunda aprobación de otra persona (otro Técnico o Admin) antes de ejecutar. | T, A | F2 | La bandeja muestra "esperando segunda aprobación"; el solicitante no puede ser su propio segundo aprobador. |
| Bandeja de aprobaciones | Sección con tarjetas pendientes (propias + segundas aprobaciones asignables), historial de decididas. | T, A | F2 | Funcional: oculta. Funciona en móvil (transversal §14). |
| Auditoría integral | Aprobado/rechazado/expirado queda en audit log con usuario, timestamp, comentario y payload. | A (consulta global), dueño (personal) | F2 | Inmutable. |
| Lecturas sin fricción | Las tools de solo-lectura se ejecutan directo y se muestran colapsadas/expandibles — el HITL es solo para escrituras. | Todos | F1 | Clasificación lectura/escritura/riesgo vive en el registro de tools (§12) y **no es modificable en runtime**. |

---

## 9. Validación Protheus — cliente/ambiente, checklists, bridge (UX-SPEC §6, ADR-0002)

| Funcionalidad | Descripción | Roles | Fase | Notas de comportamiento |
|---|---|---|---|---|
| Selector de contexto obligatorio | Al iniciar sesión con un agente que toca Protheus, el usuario elige **cliente final + ambiente** antes de poder chatear. | T, A | F2 | Solo ve sus perfiles de conexión asignados. Datos de clientes finales siempre ficticios en mockups. |
| Header de contexto permanente | La sesión muestra siempre: cliente, ambiente con color por criticidad (**prod/val/dev**), y estado del bridge/VPN **en vivo** (verde/rojo). | T, A | F2 | Imposible olvidar contra qué se está trabajando. |
| Cambio de contexto = sesión nueva | No se cambia cliente/ambiente dentro de una sesión (stickiness, coherencia de cache y auditoría). | T, A | F2 | CTA "trabajar con otro cliente" abre sesión nueva. |
| Checklists de parametrización | ValidationAgent valida la parametrización del ambiente contra checklists versionados; produce hallazgos con evidencia (parámetro, valor esperado vs encontrado). | T, A | F2 | Los checklists son contenido versionado y gobernado (owner, versión). |
| Informe GAP | Salida estructurada de validación (por chat o workflow §7) exportable. | T, A | F2 | — |
| SQL SELECT solo INBOLSA | Consultas SQL de solo-lectura habilitadas únicamente en el perfil INBOLSA (ambiente interno propio) vía `protheus_query`. | T, A | F2 | Flag `allow_sql_select` por perfil de conexión; cualquier otro perfil lo tiene apagado. |
| Escrituras solo API REST + HITL | Toda modificación va por la API REST oficial de Protheus y pasa por la tarjeta HITL (§8). | T, A | F2 | Flag `allow_writes` por perfil; sin el flag, las tools de escritura ni se ofrecen al agente. |
| Estado del bridge en vivo | El bridge tat-mcp (`--connect`, WSS) reporta su estado; la UI lo refleja en el header y en tarjetas de error. | T, A | F2 | `BRIDGE_OFFLINE` → "tu tat-mcp no está conectado" + comando exacto para levantarlo. |
| Estado de la VPN | `VPN_OFFLINE` → tarjeta con el cliente/ambiente afectado y la instrucción de activar la VPN. | T, A | F2 | Por cliente final (cada uno tiene su VPN). |
| Nivel de datos por contexto | El contexto cliente/ambiente clasifica la sesión (N0–N3, ADR-0014); ambientes de prueba habilitan N2 hacia DeepSeek; ambientes productivos restringen proveedor (ZDR) o bloquean. | T, A | F2 | El selector hace natural la clasificación; herencia hacia escalación y fallback. |

---

## 10. Mi espacio — consumo, memoria, auditoría personal, configuración

| Funcionalidad | Descripción | Roles | Fase | Notas de comportamiento |
|---|---|---|---|---|
| Mi consumo | Consumo propio del día y del mes contra la cuota: nadie llega al límite por sorpresa. | Todos | F1 | Funcional ve **% de cuota y "espacio usado"** (sin moneda ni tokens); Técnico/Admin ven tokens y costo. |
| Mis solicitudes de liberación | Estado de las liberaciones de cuota pedidas (pendiente/otorgada/denegada). | Todos | F1 | Historial personal; decisión y motivo visibles. |
| Mi memoria | Página propia con **todas** las entradas de memoria: ver, editar, borrar. El agente solo propone; el usuario confirma (§4). | Todos | F2 | Límite ~1.000 tokens (perfil, no historial). Prohibido PII de clientes reales y credenciales — la UI lo valida y advierte. Entra como snapshot post-prefijo al crear sesión (no rompe cache). |
| Memoria de proyecto/cliente | Memoria compartida por equipo, administrada por Técnicos. | T, A | F3 | Mismo contrato de transparencia: visible, editable, auditada. |
| Mi auditoría | Vista personal: mis ejecuciones de tools, mis aprobaciones/rechazos HITL, mis confirmaciones N2 ("datos de prueba"), mis aceptaciones de acuerdo. | Todos | F1 (base), F2 (HITL) | Subconjunto del audit log global filtrado por el propio usuario. |
| Mis adjuntos | Lista y descarga de archivos propios dentro de la retención (90 días default). | Todos | F1 | Descarga auditada. |
| Configuración personal | Tema dark/light, idioma (español; PT-BR cuando se active), TOTP (opcional T/F), cambio de contraseña. | Todos | F1 | El idioma de UI multi-instancia llega en F3; los textos ya nacen externalizados. |

---

## 11. Administración — usuarios, grupos, cuotas, audit, salud (solo Admin)

| Funcionalidad | Descripción | Roles | Fase | Notas de comportamiento |
|---|---|---|---|---|
| Gestión de usuarios | Alta/baja/suspensión de cuentas, asignación de rol, reset de contraseña, revocación de sesiones, exigencia de TOTP. | A | F1 | Único origen de cuentas (sin registro). Toda mutación → audit log. |
| Grupos/equipos | Crear grupos, asignar miembros; base de presupuestos por grupo y analítica por equipo. | A | F1 | — |
| Matriz de visibilidad agente×rol | Configurar qué agentes (y workflows §7) ve cada rol; también visibilidad de secciones. | A | F1 | Configuración viva en DB + UI, sin deploy; versionada y auditada. |
| Matriz de capacidades por rol | Qué capa ve cada rol en cada vista (la semántica de capacidades cambia por PR; la asignación es config). | A | F1 | Telemetría: **solo Admin** — decisión cerrada. |
| Cuotas jerárquicas | Presupuestos global → grupo → usuario → sesión, todos configurables; defaults de ADR-0007; umbral de aviso (80%) configurable. | A | F1 | Evaluación previa a CADA llamada LLM con tarifas hit/miss separadas. |
| Liberaciones de cuota | Bandeja del día: aprobar/denegar solicitudes; liberación temporal con alcance y vencimiento. | A | F1 | Cada liberación queda en audit log; notificación al solicitante. |
| Asignación de perfiles de conexión | Qué usuarios pueden trabajar contra qué cliente/ambiente (los perfiles se definen en Gobernanza §12). | A | F2 | El selector de contexto (§9) solo ofrece lo asignado. |
| Telemetría y analítica de consumo | Consumo por usuario, **grupo/equipo**, agente, modelo y cliente; por día/semana/mes; top sesiones caras; **cache_hit_rate por usuario** (detecta patrones que rompen el cache); export CSV. | A | F1 | Técnico NO accede. Profundización vía dashboards Langfuse enlazados. |
| Audit log global | Consulta con filtros: quién ejecutó qué tool, cuándo, contra qué cliente/ambiente; decisiones HITL; mutaciones de config; liberaciones; aceptaciones de acuerdo; confirmaciones N2. | A | F1 | Append-only, exportable. |
| Salud del sistema | Estado de servicios (gateway, Postgres, Langfuse, bridges) con links a Uptime Kuma y dashboards de costo/cache de Langfuse. | A | F1 | No se reimplementa lo que Langfuse/Uptime Kuma ya muestran — se enlaza. |
| Acuerdos de uso | Versión vigente del texto, registro de aceptaciones, forzar re-aceptación al cambiar. | A | F1 | — |
| Retención y políticas de instancia | Configurar retención de adjuntos, branding, límites de attachments, idioma default. | A | F1 | Todo default es configuración de instancia, no constante de código. |

---

## 12. Gobernanza — prompts, tools, conexiones, flags, evals (solo Admin)

| Funcionalidad | Descripción | Roles | Fase | Notas de comportamiento |
|---|---|---|---|---|
| Registro de Prompts | Fuente de verdad de runtime en Postgres (ADR-0011): versiones **inmutables** una vez publicadas; editar = versión nueva. | A | F1 | Técnico ve solo la versión activa en la ficha técnica; jamás edita. Nunca se edita en Langfuse a mano. |
| Workflow draft → published → retired | Un draft se edita libre y nunca llega a runtime; **publicar exige evals ≥80% + safety en verde, verificado por el sistema** (imposible saltárselo). | A | F1 | Score y notas de cambio en cada versión (reemplaza CHANGELOG). |
| Activar / rollback sin deploy | Cambiar la versión activa de un agente = update de puntero + audit; rollback idéntico. | A | F1 | Activar otra versión = línea de cache nueva (warmup esperado y visible en telemetría). |
| Diff entre versiones | Comparación de contenido entre versiones de prompt. | A | F1 | — |
| Espejo Git automático | Cada publicación exporta snapshot a `prompts/` para code review y arqueología. Git deja de ser la fuente de runtime. | A | F1 | — |
| Registro de tools | Catálogo de tools disponibles con clasificación **lectura/escritura y nivel de riesgo**, y permisos por rol/agente. Toolset completo y fijo por versión de agente (`stableToolSchemas()`). | A | F1 | La clasificación de riesgo y el enforcement HITL **no son modificables en runtime** (cambio = PR). Skills jamás se cargan a mitad de sesión. |
| Perfiles de conexión | Alta/baja de perfiles cliente final + ambiente con flags `allow_sql_select` / `allow_writes`, datos de VPN/bridge asociados. | A | F2 | La asignación a usuarios vive en Administración (§11). |
| Feature flags + kill-switch | Tabla de flags con scope; **kill-switch por agente y por tool**: apagado efectivo en < 1 min, sin deploy, auditado. | A | F1 | Primer recurso del runbook de incidentes. Lo que apaga un flag aparece deshabilitado con mensaje claro (§6). |
| Evals | Datasets YAML por agente, runner, score vigente por versión; casos `safety` = hard-fail individual; gate de CI (<80% bloquea deploy); todo bug de producción → caso de regresión. | A | F1 | El Técnico ve el score en la ficha técnica; la gestión es solo-Admin. Evals solo con datos sintéticos (ADR-0014). |
| Política de datos y proveedores | Matriz N0–N3 × proveedor (DeepSeek ≤N1/N2-prueba; alternos/SOTA vía OpenRouter ≤N2 con ZDR; **N3 jamás**); registro de bloqueos del scrubber. | A | F2 | La cascada de fallback filtra por nivel; sin proveedor permitido → error claro, nunca degradar. Telemetría enmascarada (mask de Langfuse). |
| Configuración de modelos | Perfiles de modelo y cascadas de fallback por agente (config, no hardcode); escalación Pro habilitada/deshabilitada por agente. | A | F1 | Precios y cadenas de fallback nuevas entran por PR; la activación por agente es config. |

---

## 13. Construcción — Agent Builder y Skills Builder

| Funcionalidad | Descripción | Roles | Fase | Notas de comportamiento |
|---|---|---|---|---|
| Agent Builder (solo Admin) | Crear/editar agentes: identidad de ficha, instrucciones, toolset elegido del registro (§12), perfil de modelo, escalación on/off. **El header estático cache-safe lo pone la plataforma** — el builder no puede romper el prefijo. | A | F1 | Publicar exige evals en verde (mismo gate que prompts). Cada versión de agente hornea su toolset y skills — fijos por versión. |
| Skills Builder (solo Admin) | Crear skills: paquete versionado de instrucciones + ejemplos + tools permitidas. Publicar exige **≥3 casos de eval**. | A | F2 | Las skills se hornean en versiones de agente o se montan como subagentes — nunca se cargan a mitad de sesión. |
| Registro de skills | Catálogo paralelo al de agentes: ficha con nombre, versión, owner, **qué agentes la usan**, evals. | T (consulta), A | F2 | En el builder, las skills aprobadas aparecen como bloques seleccionables. |
| Propuestas de técnicos (template guiado) | Power users proponen agentes/skills personalizando instrucciones dentro de un marco fijo; toolset acotado a la lista permitida por rol; **revisión del Admin + evals mínimos** antes de aparecer en catálogo. | T (propone), A (aprueba) | F2 | Autonomía sin romper cache ni seguridad. |
| Creación self-service | Constructor no-code para cualquier empleado, **en sandbox sin tools de escritura**. | Todos (sandbox), A (promoción) | F3 | Solo si se cumplen los criterios go/no-go (plan §12.2). Promover a catálogo = pasar por el gate completo. |
| Definición de workflows | Los workflows deterministas se definen por código + registro (pasos, inputs, archivos esperados, pasos HITL) y se publican al catálogo de workflows. | A | F2 | No hay builder visual de workflows en el alcance actual; la publicación y visibilidad sí son config. |

---

## 14. Transversales

| Funcionalidad | Descripción | Roles | Fase | Notas de comportamiento |
|---|---|---|---|---|
| i18n preparado | UI en español (voseo consistente con los textos del producto); todos los textos externalizados; layouts previendo **+25% de largo** para PT-BR. | Todos | F1 (preparación), F3 (activación PT-BR) | El agente ya responde en el idioma del usuario; esto cubre la UI. |
| Theming dual-brand por tokens | Brand `default` ("sala de control": fondo #0a0d13, ámbar #ffb000, verde #3ddc97, Chakra Petch/Saira/JetBrains Mono) y brand `totvs` (azul TOTVS clásico). **Ambos con dark y light completos.** | Todos | F1 | `html[data-theme="dark|light"][data-brand="default|totvs"]`. El brand es configuración de instancia; el theme es preferencia personal. Ver DESIGN-SYSTEM.md. |
| Accesibilidad WCAG 2.1 AA | Contraste AA en ambos temas/brands, foco visible, navegación completa por teclado, aria en componentes interactivos (tarjetas HITL, selector de ramas, chips de adjuntos). | Todos | F1 | Las tarjetas HITL son críticas: aprobar/rechazar operable por teclado y lector de pantalla. |
| Móvil funcional | Desktop-first; en móvil funcionan **chat, catálogo y aprobaciones HITL** (las tres cosas que no pueden esperar al escritorio). | Todos | F1 (chat/catálogo), F2 (HITL) | Sin app nativa ni push en MVP; web responsive. |
| Iconografía | lucide en toda la UI. | Todos | F1 | — |
| Niveles de datos N0–N3 | Clasificación transversal (sesión, adjuntos, memoria): N3 jamás al LLM (scrubber bloquea + registra), N2 con advertencia/ZDR, herencia por escalación y fallback. | Todos | F1 (adjuntos), F2 (sesiones) | La UI siempre advierte antes de bloquear; el bloqueo explica el porqué y el remedio. |
| Instancia por cliente | Branding, catálogo, usuarios, cuotas, retención, idioma y política de datos = configuración de instancia. | A | F1 | Vendible a otras consultoras; Resultar = primer cliente. |
| Observabilidad integral | Toda llamada LLM trazada en Langfuse (costo hit/miss/output, sesión, usuario enmascarado); base de telemetría, evals y feedback. | A (consulta) | F1 | Invisible para Funcional/Técnico salvo lo que la ficha técnica expone. |
| Append-only / branch-never-rewrite | Garantía transversal: nada reescribe historia — ni edición (rama), ni truncado (una vez), ni compaction (frontera de turno, una vez). | — (principio) | F1 | Es la economía del proyecto (cache-first); las violaciones se rechazan en PR. |

---

## Matriz Vista × Rol

Leyenda: **●** completo · **◐** parcial (capa reducida — ver nota) · **○** oculto. "(cfg)" = default mostrado, ajustable por la matriz de visibilidad del Admin.

| Vista | Admin | Técnico | Funcional | Nota de la capa parcial |
|---|:---:|:---:|:---:|---|
| Login + TOTP | ● | ● | ● | TOTP obligatorio solo Admin; opcional para el resto. |
| Acuerdo de uso (primer login) | ● | ● | ● | Idéntico para todos; aceptación auditada. |
| Shell / navegación | ● | ◐ | ◐ | Técnico: sin Telemetría, Administración, Gobernanza ni Builders. Funcional: solo Chat, Catálogo, Workflows (cfg), Mi espacio, Notificaciones. |
| Chat | ● | ● | ◐ | Funcional: sin tokens/costos (espacio en %), tool calls en lenguaje simple, sin detalle de perfil en "modelo alterno" (la etiqueta sí se ve — todos los roles). |
| Selector de ramas ("versión 1/2") | ● | ● | ● | Idéntico: la transparencia de ramas no es jerga. |
| Escalación a Pro (botón post-marcador) | ● | ● | ● | Visible si el agente lo permite (config por agente). |
| Attachments + vista previa de extracción | ● | ● | ◐ | Funcional: misma vista previa, conteo como "% del espacio" en vez de tokens. |
| Catálogo de agentes | ● | ● | ◐ | Filtrado por matriz agente×rol para todos; Funcional ve menos agentes y ficha limpia. |
| Ficha de agente — capa común | ● | ● | ● | Nombre, descripción, casos de uso, ejemplos clicables. |
| Ficha de agente — ficha técnica | ● | ● | ○ | Tools, modelo, costo/sesión, versión de prompt, score de evals. |
| Workflows (listado + ejecución) | ● | ● (cfg) | ◐ (cfg) | Funcional: solo workflows sin escrituras asignados por el Admin; sin capa técnica de pasos. |
| Selector de contexto cliente/ambiente | ● | ● | ○ (cfg) | Solo perfiles asignados al usuario; Funcional sin agentes Protheus por default. |
| Header de contexto (cliente/ambiente/bridge) | ● | ● | ○ | Acompaña a las sesiones Protheus. |
| Bandeja de aprobaciones HITL | ● | ● | ○ | Técnico: sus tarjetas + segundas aprobaciones; Admin: todas. |
| Tarjeta HITL en chat/workflow | ● | ● | ○ | Funcional no llega a tools de escritura (matriz de visibilidad). |
| Notificaciones | ● | ◐ | ◐ | Cada rol recibe solo lo suyo; HITL solo T/A; liberaciones de cuota: solicitante + Admin. |
| Mi espacio — consumo propio | ● | ● | ◐ | Funcional: % de cuota, sin moneda/tokens. |
| Mi espacio — memoria | ● | ● | ● | Idéntico: ver/editar/borrar; el agente solo propone. |
| Mi espacio — auditoría personal | ● | ● | ● | Cada quien lo suyo. |
| Mi espacio — configuración | ● | ● | ● | Tema, idioma, TOTP, contraseña. |
| Telemetría / analítica global | ● | ○ | ○ | **Solo Admin** — decisión cerrada (el Técnico no ve telemetría). |
| Administración (usuarios/grupos/cuotas/liberaciones) | ● | ○ | ○ | — |
| Audit log global | ● | ○ | ○ | Los demás solo ven su auditoría personal. |
| Salud del sistema (Uptime Kuma/Langfuse) | ● | ○ | ○ | — |
| Gobernanza — Registro de Prompts | ● | ○ | ○ | El Técnico ve la versión activa en la ficha técnica, no el registro. |
| Gobernanza — tools/conexiones/flags/evals | ● | ○ | ○ | El Técnico ve tools y score de evals en la ficha técnica. |
| Agent Builder / Skills Builder | ● | ◐ (F2) | ○ | F2: el Técnico propone vía template guiado con aprobación del Admin; F3: sandbox self-service sin escrituras para todos. |
| Registro de skills | ● | ● | ○ | Consulta para Técnico; gestión solo Admin. |

---

*Documento de diseño — los datos que aparezcan en mockups derivados de este mapa son siempre ficticios (clientes tipo "Comercial Andina S.A.", usuarios tipo "lucia"). Cualquier funcionalidad nueva que contradiga un ADR se discute antes de diseñarse.*
