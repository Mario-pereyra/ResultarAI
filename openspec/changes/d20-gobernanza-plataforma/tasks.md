# Tasks — d20-gobernanza-plataforma

## 1. Persistencia y bounded context governance

- [ ] 1.1 Crear el módulo `resultarai/app/governance/` (paquete + `__init__.py`) y el repositorio Postgres base (adapter) para las tablas de gobernanza. Verificación: `lint-imports` en verde (governance vive en app/, no toca core/); `uv run pytest` importa el paquete sin efectos. `[modelo: sonnet]`
- [ ] 1.2 Migración Alembic del schema de prompts: tabla de versiones (`agent_id`, `version`, `estado draft|published|retired`, `contenido`, `hash sha256`, `autor`, `fecha`, `changelog`, `score_gate`) + puntero de versión activa por Agent. Verificación: migración up/down aplica limpio contra Postgres de test. `[modelo: haiku]`
- [ ] 1.3 Migración Alembic de flags/kill-switch, permisos y matrices, config de instancia y auditoría append-only de gobernanza (sin UPDATE/DELETE sobre auditoría). Verificación: intento de UPDATE en la tabla de auditoría falla por constraint/trigger (test). `[modelo: sonnet]`

## 2. Registro de Prompts — backend

- [ ] 2.1 Servicio de ciclo de vida: crear `draft` (único por Agent), editar `draft`, transición `draft→published→retired`; **inmutabilidad**: rechazar edición de `published` y ofrecer clonar a `draft`; rechazar activar `retired`. Verificación: tests de los escenarios "Intento de editar una versión publicada es rechazado", "Un solo borrador por agente" y "Una versión retirada no puede activarse" de `specs/prompt-registry`. `[modelo: opus]`
- [ ] 2.2 Activar/rollback como update de puntero **sin deploy** con stickiness (sesiones en curso conservan su versión) y motivo obligatorio; runtime resuelve el prompt desde Postgres, no desde Git. Verificación: tests de "Los chats nuevos toman la versión activada, los en curso no", "Activar exige motivo" y "El runtime resuelve el prompt desde el registro". `[modelo: opus]`
- [ ] 2.3 Gate de publicación **pluggable** (`PublicationGate` con `PlaceholderGate`/`EnforcingGate`): placeholder = advertencia y publica; enforcing = bloqueo si score < 80% o `safety` en rojo; editar `draft` invalida la corrida (gate por hash). Verificación: tests de "Publicar sin evals en modo placeholder muestra advertencia y publica", "Modo enforcing bloquea por score bajo o safety en rojo" y "Editar el borrador invalida la corrida de evals". `[modelo: opus]`
- [ ] 2.4 Espejo Git automático: en cada `publish`, exportar snapshot inmutable de la versión a `prompts/`; el runtime nunca lee de ahí. Verificación: test de "Publicar deja un snapshot en prompts/" y "Edición manual fuera del registro no tiene efecto en runtime". `[modelo: haiku]`
- [ ] 2.5 Auditoría append-only de `draft-create`/`draft-edit`/`publish`/`activate`/`rollback` (con de→a y motivo). Verificación: test de "La auditoría registra publicación y activación"; eventos inmutables. `[modelo: sonnet]`

## 3. Registro de Prompts — UI (vista 34, solo Admin)

- [ ] 3.1 Vista maestro-detalle `34-admin-prompts` (lista de Agents/versiones + tabs Borrador/Activa/Auditoría) con estados de versión y candado en `published`. Verificación: renderiza versiones y bloquea edición de `published` (mock del backend); solo visible para Admin (404 de producto para otros roles). `[modelo: sonnet]`
- [ ] 3.2 Diff lado a lado entre versiones + editor de `draft` con changelog. Verificación: escenario "Comparar borrador contra versión activa"; el input del editor no se pierde ante fallo de guardado. `[modelo: sonnet]`
- [ ] 3.3 Controles de gate (Correr evals/Publicar con motivo junto al botón), activar y rollback con modal + motivo y aviso de stickiness. Verificación: en placeholder el botón publica con advertencia; en enforcing queda deshabilitado con el motivo visible (no solo tooltip). `[modelo: sonnet]`

## 4. Feature flags y kill-switch — backend

- [ ] 4.1 CRUD de flags con scope (global/agente/rol), auditoría inline y optimistic lock; garantizar que ninguna regla dura (HITL off, SQL libre) sea flageable. Verificación: tests de "Cambiar un flag sin deploy queda auditado", "Cambio concurrente rechazado por optimistic lock" y "No existe flag para desactivar HITL". `[modelo: sonnet]`
- [ ] 4.2 Kill-switch por Agent con efectos coordinados (<1 min, sin deploy): rechazar turnos nuevos, terminar/abortar streams, **emitir el contrato de congelar tarjetas HITL** (`d17`), marcar catálogo "No disponible temporalmente" (`d15`) y **emitir notificación** a sesiones activas (`d12`); reactivación restaura y notifica; coherente con status `deprecated` (no muta el Manifest). Verificación: test de "Kill-switch congela tarjetas HITL y deshabilita el agente en el catálogo", "Reactivar un agente restaura catálogo y notifica" y "Kill-switch no altera el manifiesto". `[modelo: opus]`
- [ ] 4.3 Kill-switch por Tool: desactivar hace fallar la Tool con `TOOL_DISABLED` en sesiones en curso; el toolset fijo por versión la sigue declarando; motivo obligatorio. Verificación: test de "Desactivar una tool la hace fallar en sesiones en curso". `[modelo: opus]`

## 5. Feature flags y kill-switch — UI (vista 38, solo Admin)

- [ ] 5.1 Tabla de flags con scope + audit inline + historial; kill-switch por Agent con modal crítico (motivo obligatorio) y preview del banner al usuario. Verificación: apagar exige motivo; el switch revierte y avisa ante fallo (nunca estado mentiroso). `[modelo: sonnet]`
- [ ] 5.2 Estado de kill-switch por Tool en la UI (apagar/reactivar con confirmación y consecuencia `TOOL_DISABLED`). Verificación: la acción refleja el estado real del backend y queda auditada. `[modelo: sonnet]`

## 6. Tools y permisos (vista 35, solo Admin)

- [ ] 6.1 Vista del Tool Registry (agrupada por server MCP) que muestra clasificación de riesgo (con palabra), HITL, límites y estado; **enforcement**: rechazar edición de la clasificación de riesgo en runtime (cambio = PR) y HITL marcado+bloqueado en escritura/destructiva. Verificación: tests de "Intento de editar la clasificación de riesgo en runtime es rechazado" y "HITL no desmarcable en una tool de escritura". `[modelo: opus]`
- [ ] 6.2 Permisos rol×tool y matrices de visibilidad agente×rol y de capacidades por vista como config viva versionada + auditada, sin deploy; Funcional nunca recibe tools destructivas; cambios aplican a sesiones nuevas (stickiness). Verificación: tests de "Quitar una tool a un rol aplica a sesiones nuevas", "Funcional no puede recibir tools destructivas" y "Cambiar la visibilidad de un agente sin deploy". `[modelo: sonnet]`

## 7. Configuración de instancia (vista 40, solo Admin)

- [ ] 7.1 Backend de config de instancia: branding (brand/logo/nombre), retención de adjuntos, límites de attachments, idioma default, umbral de cuota, TTL de tarjetas HITL, regional y licenciatario; lectura de defaults desde DB (no constantes) y auditoría de cambios. Verificación: tests de "Un default se lee de la configuración de instancia, no del código", "El idioma default solo afecta a usuarios sin preferencia" y "El umbral de cuota configurado gobierna el aviso". `[modelo: sonnet]`
- [ ] 7.2 UI de config de instancia (`40-admin-instancia`): formulario seccionado con preview de shell dark/light, barra "cambios sin guardar", brand conserva temas personales, logo claro+oscuro. Verificación: escenarios "Cambiar el brand conserva los temas personales" y "El logo exige versión clara y oscura". `[modelo: sonnet]`

## 8. Cierre

- [ ] 8.1 Seed de fábrica: `default_chat@1` published+activa, matriz de visibilidad por defecto y config de instancia por defecto (branding `default`, retención 90 días, umbral 80%, TTL HITL). Verificación: instancia limpia arranca con estos valores; `openspec validate` en verde. `[modelo: haiku]`
- [ ] 8.2 Review final del change: gate pluggable en ambos modos, inmutabilidad y kill-switch verificados, auditoría append-only intacta, cero lógica en core/, términos del glosario consistentes. Verificación: checklist del reviewer en el PR. `[modelo: opus]`
