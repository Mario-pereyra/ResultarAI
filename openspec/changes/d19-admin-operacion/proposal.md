## Why

El Admin gobierna toda la instancia (usuarios, cuotas, gobernanza) pero hoy no tiene un lugar único para responder "¿cuánto está costando la plataforma, el cache la está protegiendo, quién hizo qué, y los servicios están vivos?" sin saltar entre Postgres, Langfuse y los logs de cada servicio. `d11-identidad-acceso` ya audita mutaciones de identidad y `d16-cuotas-liberaciones` ya emite eventos de cuota/liberación, pero ningún change expone esa información consolidada de operación diaria al Admin. Sin este change, el roadmap no puede declarar cumplido "el Admin responde quién hizo qué, cuándo y cuánto costó sin salir de la consola" (`docs/07-roadmap.md`, fila d19).

## What Changes

- Se agrega el **Tablero de operación** (vista 30): resumen del día (costo hoy/semana, cache hit-rate, escalaciones a Pro, agentes activos, tasa de error) y alertas visibles (cuotas al límite, tarjetas HITL por expirar, kill-switches activos), con accesos directos al resto de la consola.
- Se agrega la **Telemetría y analítica de consumo**, exclusiva de Admin (decisión cerrada: el Técnico no la ve): consumo por usuario, grupo/equipo, agente y perfil de modelo; agrupación por día/semana/mes; top sesiones caras; `cache_hit_rate` por usuario (detecta patrones que rompen el cache); export CSV; enlaces directos a los dashboards de Langfuse para profundizar (sin reimplementar lo que Langfuse ya muestra, usando las naming conventions de `b07-observabilidad`).
- Se agrega el **Audit log global** (vista 37): consulta con filtros (actor, tipo de acción, entidad, rango de fechas, cliente/ambiente), lectura append-only e inmutable de los `AuditEvent` ya emitidos por `a03-core-gobernanza` y sus consumidores (`d11`, `d16`, HITL, mutaciones de config, aceptaciones de acuerdo, confirmaciones N2), export CSV, y soporte para deep links con filtro pre-aplicado desde otras vistas.
- Se agrega la **Salud del sistema** (vista 39, alcance acotado): estado de los servicios de la plataforma (gateway/LLM, PostgreSQL, Langfuse, MCP servers registrados) con enlaces externos a Uptime Kuma y a los dashboards de costo/cache de Langfuse — se enlaza, no se reimplementa.
- Se agrega el **guard de rol Admin** sobre las cuatro superficies anteriores: un intento de acceso de Técnico o Funcional se deniega y queda auditado, sin confirmar la existencia de la ruta.

## Capabilities

### New Capabilities

- `admin-operations`: tablero de operación, telemetría/analítica de consumo (solo Admin), audit log global con filtros y export, y salud del sistema (enlaces a Uptime Kuma/Langfuse), todo restringido por guard de rol Admin y auditado.

### Modified Capabilities

*(ninguna — las cuatro superficies son de solo lectura sobre datos que ya emiten `a03-core-gobernanza`, `b05-gateway-modelos`, `b07-observabilidad`, `d11-identidad-acceso` y `d16-cuotas-liberaciones`; ningún requirement existente cambia)*

## No-objetivos

- **Sin gestión de usuarios, grupos ni cuotas**: alta/baja/rol/TOTP de cuentas y grupos (`d11-identidad-acceso`) y la edición de defaults/overrides de cuota — incluida la pestaña "Cuotas" de la vista 33 — y la bandeja de liberaciones (`d16-cuotas-liberaciones`) no se redefinen aquí; el tablero solo **lee** y muestra alertas derivadas de esos datos.
- **Sin gobernanza de prompts, tools, flags ni evals** (`d20-gobernanza-plataforma`): Registro de Prompts, kill-switch por agente/tool (gestión), registro de permisos de tools y gate de evals no se especifican en este change. El tablero solo **muestra** el estado (activo/inactivo) de un kill-switch ya gestionado en `d20`, sin ofrecer la acción de encenderlo/apagarlo.
- **Sin el kill-switch global de plataforma** ("apagar el chat de la plataforma") ni backups/prueba de restore/jobs de retención descritos en `design/VISTAS/07-admin-operacion.md` §6: el alcance de "Salud del sistema" en este change se limita a estado de servicios + enlaces externos, conforme al roadmap; esas piezas adicionales quedan para un change de operación posterior (`e24-despliegue-operacion` o una revisión de `d20`).
- **Sin dashboards propios que dupliquen Langfuse o Uptime Kuma**: ninguna vista de este change reimplementa gráficos de costo/latencia que esas herramientas ya ofrecen; se enlaza con deep links siguiendo las naming conventions de `b07-observabilidad`.
- **Sin Agent Builder ni Skills Builder** (`d21-builders`) y sin catálogo de agentes (`d15-catalogo-agentes`).

## Bounded context afectado

`app/` (casos de uso de agregación de solo lectura sobre lo ya persistido por `b04-persistencia-postgres`/`b07-observabilidad`, guard de autorización de rol Admin, endpoints de consulta y export CSV del audit log y de la telemetría) y `frontend/` (vistas 30, 37 y 39 más el panel de analítica de consumo). No se agrega lógica de dominio nueva en `core/`: la única regla de negocio es la restricción de rol, que reutiliza el `PolicyGate`/`ActionRequest` de `a03-core-gobernanza` (rol Admin como condición de una Policy) en vez de introducir un mecanismo de autorización paralelo.

## Impact

- `resultarai/app/` (casos de uso de agregación de telemetría, consulta filtrada de audit log, consulta de estado de salud, export CSV) con tests de contrato.
- `frontend/` (vistas 30-admin-dashboard, 37-admin-audit, 39-admin-salud y el panel de analítica de consumo).
- Depende de: `a03-core-gobernanza` (`PolicyGate`, `AuditEvent`), `b04-persistencia-postgres` (audit log y consumo persistidos), `b05-gateway-modelos` (tarifas cache hit/miss, perfil de modelo, modelo alterno), `b07-observabilidad` (trazas Langfuse y naming conventions para deep links), `d11-identidad-acceso` (roles, eventos de identidad) y `d16-cuotas-liberaciones` (eventos de cuota/liberación que alimentan las alertas del tablero).
- Referencia del blueprint: §2.4 (economía cache-first y observabilidad) — se cita como motivación, sin copiar.
