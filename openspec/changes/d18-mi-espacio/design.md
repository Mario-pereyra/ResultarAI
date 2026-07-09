# Design — d18-mi-espacio

## Context

`d18` es el tercer y último slice de "Mi espacio" (`design/VISTAS/06-mi-espacio.md`), después de Mi consumo (`d16`) y antes de Mi memoria (`e23`). A diferencia de esos dos, `d18` no introduce dominio nuevo: es una capa de **lectura filtrada por ownership** sobre capacidades que ya existen o ya están especificadas — el Audit Log (`a03-core-gobernanza`), el schema de attachments (`b04-persistencia-postgres`) y su pipeline con descarga auditada (`d14-attachments`), y la autenticación/TOTP/sesiones (`d11-identidad-acceso`) — más una vista de listado de adjuntos que el paquete de diseño no mockeó explícitamente. El riesgo central del change no es "qué construir" sino "no reconstruir dos veces lo mismo": cada una de las tres áreas linda con un change que ya posee el dominio.

## Goals / Non-Goals

**Goals:**

- Exponer Mi auditoría, Mis adjuntos y Configuración personal como autoservicio, con ownership estricto verificado en cada endpoint.
- Reutilizar sin reabrir: `AuditEvent` (a03), schema de attachments + invariante `inserted_text` (b04), descarga auditada (d14), Argon2id/TOTP/sesiones (d11).
- Dejar auditado cada acceso propio relevante (lectura de auditoría no genera evento nuevo — sería ruido infinito; descarga de adjunto y mutaciones de configuración sí).

**Non-Goals:**

- Ningún schema nuevo de persistencia de dominio: solo consultas filtradas sobre tablas ya definidas por `a03`/`b04`/`d11`, y como mucho una tabla ligera de preferencias de usuario (tema/idioma) si `d11` no la tiene ya (a decidir en `a02`/`b04` si el campo ya existe en la tabla de cuentas del wizard de primer acceso).
- Ninguna acción de escritura sobre el Audit Log: Mi auditoría es 100% lectura.
- Ninguna eliminación manual de adjuntos por el usuario (ver No-objetivos del proposal).

## Decisions

1. **Mi auditoría es una vista, no una capability de escritura de auditoría.** El `AuditEvent` ya lo define `a03-core-gobernanza`; `d18` solo agrega la consulta filtrada por `user_id` con paginación server-side. Alternativa descartada: duplicar el modelo de evento con un "vista personal" propio — rompería la garantía de una sola fuente de verdad para el audit log.
2. **Mis adjuntos no reimplementa descarga ni escaneo.** Reutiliza el endpoint auditado de `d14-attachments` (dueño y Admin) y el `scan_result` persistido por `b04`. `d18` agrega el endpoint de listado (`GET /me/attachments`, filtro `uploaded_by = session.user_id`) y envuelve la llamada de descarga solo para emitir el `AuditEvent` de acceso desde Mi espacio (distinto del evento de subida, que ya audita `d14`). Alternativa descartada: que Mis adjuntos llame directo al storage sin pasar por el endpoint de `d14` — violaría "un solo camino auditado de descarga".
3. **Sin vista de mockup dedicada para Mis adjuntos**, se sigue el patrón visual ya validado de Mi auditoría (`.panel`, `.table` en `.panel--flush`, paginación clásica, `.tag` de estado) y los estados de escaneo ya definidos por el ANEXO §4.4 (`listo` / `bloqueado` N3 / advertencia N2 confirmada). Se documenta esta decisión aquí para que `d20` (design system) no la trate como deuda de design/.
4. **Configuración personal delega TOTP/contraseña/sesiones a los casos de uso de `identity` (`d11`), sin duplicar lógica.** La vista es una nueva superficie (fuera del wizard de primer acceso) sobre los mismos casos de uso: activar/desactivar TOTP, regenerar códigos, cambiar contraseña, revocar sesión. Lo único nuevo en `app/` es (a) el endpoint de listado de sesiones propias (no existía: `d11` solo expone revocar, no listar) y (b) las preferencias de tema/idioma persistentes fuera del wizard.
5. **La purga por retención no es un evento de "eliminación" auditado por el usuario.** Es un proceso de sistema ya cubierto por el invariante de `b04` (`inserted_text` sobrevive al binario). Mi auditoría no necesita un tipo de evento nuevo para esto: el ítem simplemente deja de listarse en Mis adjuntos como vigente.
6. **El intento de acceso ownership-denegado se audita con un `AuditEvent` genérico**, no ligado al Policy Gate (que en `docs/06-seguridad-gobernanza.md` cubre específicamente `ActionRequest` de agente/skill/tool). Se usa el mismo contrato `AuditEvent` de `a03` porque ya es de uso general (`d11` audita alta/baja/reset sin pasar por Policy Gate); no se crea un segundo esquema de evento de seguridad.

## Risks / Trade-offs

- [Acoplamiento fuerte a que `d11`/`d14`/`b04`/`a03` estén ya especificados o archivados antes de implementar] → Mitigación: el proposal declara la dependencia explícitamente; si algún change previo cambia su contrato, `d18` se re-valida antes de aplicar tareas, no antes de especificar (OpenSpec permite especificar contra la interfaz ya publicada).
- [Falta de mockup para Mis adjuntos puede generar una UI inconsistente con el resto de "Mi espacio"] → Mitigación: decisión 3 fija el patrón visual a reutilizar; una tarea de tasks.md pide revisión de consistencia visual antes de cerrar el change.
- [El endpoint de listado de sesiones propias es nuevo y no estaba en `d11`] → Mitigación: se especifica aquí como extensión menor de lectura sobre datos que `d11` ya persiste (sesiones activas por usuario); no requiere cambiar el contrato de revocación existente.

## Open Questions

*(ninguna — las decisiones quedan tomadas arriba; cualquier ajuste de contrato con `d11`/`d14` se resuelve como corrección de esos changes, no aquí)*
