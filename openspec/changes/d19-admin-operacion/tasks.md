## 1. Guard de rol Admin

- [ ] 1.1 Definir el `ActionRequest`/Policy Manifest de administración (agent/skill de administración, `operation_type: read`) que autoriza rol Admin y deniega Técnico/Funcional para las 4 superficies de esta capability. Verificación: el escenario "Técnico intenta acceder al tablero de operación" pasa en un test de contrato. `[modelo: sonnet]`
- [ ] 1.2 Implementar en `app/` la dependencia que evalúa el `ActionRequest` contra el `PolicyGate` en cada endpoint de `admin-operations` y responde sin revelar la ruta ante `deny`. Verificación: test de integración cubre Técnico denegado, Funcional denegado y Admin permitido. `[modelo: sonnet]`
- [ ] 1.3 Verificar que cada denegación produce su `AuditEvent` reutilizando el flujo ya definido en `a03-core-gobernanza`. Verificación: test de contrato en `tests/contracts/` confirma el `AuditEvent` del intento denegado. `[modelo: sonnet]`

## 2. Tablero de operación (vista 30)

- [ ] 2.1 Caso de uso de resumen del día: costo hoy/semana con delta, `cache_hit_rate` del período con tendencia, escalaciones a Pro, agentes activos y tasa de error, agregados sobre `b04-persistencia-postgres`/`b07-observabilidad`. Verificación: test de contrato con datos fixture cubre instancia con datos y sin sesiones. `[modelo: sonnet]`
- [ ] 2.2 Caso de uso de alertas operativas: lectura agregada de Cuotas cerca del umbral (`d16-cuotas-liberaciones`), tarjetas HITL por expirar y kill-switches activos (`d20-gobernanza-plataforma`), sin exponer ninguna acción de mutación. Verificación: test de contrato confirma que el endpoint no expone verbos de escritura. `[modelo: sonnet]`
- [ ] 2.3 Manejo de degradación: cuando el adapter de Langfuse no responde, marcar los montos como estimados en el payload y devolver el aviso degradado sin fallar el resto del tablero. Verificación: test simula timeout del adapter de Langfuse. `[modelo: sonnet]`
- [ ] 2.4 Componente UI del tablero conforme a `design/VISTAS/07-admin-operacion.md` §1: KPIs, panel de alertas, salud resumida, accesos directos, selector Hoy/7 días. Verificación: test de componente cubre los estados carga/vacío/error/degradado. `[modelo: sonnet]`
- [ ] 2.5 Textos y labels del tablero (es-BO, catálogo i18n) conforme a §1 del mockup. Verificación: cero strings hardcodeadas fuera del catálogo de i18n. `[modelo: haiku]`

## 3. Telemetría y analítica de consumo

- [ ] 3.1 Caso de uso de consumo agregado por usuario, grupo/equipo, agente y perfil de modelo, con selector día/semana/mes, sobre datos de `b04` y tarifas hit/miss de `b05-gateway-modelos`. Verificación: test de contrato con fixtures cubre las 4 dimensiones y los 3 periodos. `[modelo: sonnet]`
- [ ] 3.2 Caso de uso de top sesiones caras del periodo, con enlace a traza. Verificación: test de contrato confirma orden por costo descendente. `[modelo: sonnet]`
- [ ] 3.3 Cálculo de `cache_hit_rate` por usuario a partir de los contadores hit/miss ya expuestos por `b05`, agregados por periodo. Verificación: test de contrato incluye un usuario con `cache_hit_rate` anómalamente bajo frente al global. `[modelo: sonnet]`
- [ ] 3.4 Endpoint y caso de uso de export CSV de la telemetría filtrada, con `AuditEvent` del export. Verificación: test de contrato valida columnas del CSV y el `AuditEvent` emitido. `[modelo: sonnet]`
- [ ] 3.5 Test de contrato dedicado que confirma que el endpoint de telemetría deniega explícitamente al rol Técnico (decisión cerrada, distinta del guard genérico de la sección 1). Verificación: test falla si Técnico recibe datos agregados de otros usuarios. `[modelo: sonnet]`
- [ ] 3.6 Construcción de deep links a Langfuse por `trace_id`/`session_id` usando la convención de nombres documentada por `b07-observabilidad`, sin llamar a ninguna API adicional del adapter. Verificación: test valida el formato de URL contra la convención documentada. `[modelo: sonnet]`
- [ ] 3.7 UI de la analítica de consumo: selectores de agrupación/periodo, tabla de top sesiones, columna `cache_hit_rate` por usuario, botón exportar CSV, enlaces "Abrir en Langfuse". Verificación: test de componente cubre cada agrupación y el estado degradado. `[modelo: sonnet]`
- [ ] 3.8 Textos y labels de la analítica de consumo. Verificación: catálogo i18n completo, sin strings hardcodeadas. `[modelo: haiku]`

## 4. Audit log global (vista 37)

- [ ] 4.1 Caso de uso de consulta filtrada de `AuditEvent` (actor, tipo de evento, entidad, rango de fechas, `tenant`/`environment`) con paginación clásica y orden fijo por fecha-hora descendente. Verificación: test de contrato cubre cada filtro por separado y la combinación sin resultados. `[modelo: sonnet]`
- [ ] 4.2 Endpoint de detalle expandido de un `AuditEvent` que devuelve el payload completo sin truncar. Verificación: test de contrato con payload extenso confirma ausencia de truncado. `[modelo: sonnet]`
- [ ] 4.3 Endpoint y caso de uso de export CSV del audit log filtrado (incluye payload serializado) con su propio `AuditEvent` de export; ejecución en segundo plano cuando el volumen supera el umbral configurado. Verificación: test de contrato valida el `AuditEvent` de export y el modo background sobre el umbral. `[modelo: sonnet]`
- [ ] 4.4 Soporte de parámetros de filtro pre-aplicados en la URL para deep links desde otras vistas (tablero, Cuotas). Verificación: test de contrato confirma que un parámetro de entidad pre-aplica el filtro correspondiente al abrir la vista. `[modelo: sonnet]`
- [ ] 4.5 UI del audit log global conforme a `design/VISTAS/07-admin-operacion.md` §5: filtros, tabla densa, fila expandible, badge append-only/inmutable, exportar CSV, paginación clásica. Verificación: test de componente cubre expandir fila y estado sin resultados. `[modelo: sonnet]`
- [ ] 4.6 Confirmar en API que no existe ninguna ruta de edición/borrado sobre `AuditEvent`, ni siquiera para Admin. Verificación: test de contrato confirma 404/405 sobre intentos de `PUT`/`PATCH`/`DELETE` en el recurso de audit log. `[modelo: sonnet]`
- [ ] 4.7 Textos y labels del audit log global, incluido el catálogo de tipos de evento agrupado por categoría en el selector de filtro. Verificación: catálogo i18n completo. `[modelo: haiku]`

## 5. Salud del sistema (vista 39, alcance acotado)

- [ ] 5.1 Caso de uso de estado de servicios: gateway/LLM, PostgreSQL, Langfuse y MCP servers registrados (`c09-mcp-tools`), con estado, latencia y momento del último chequeo. Verificación: test de contrato cubre operativo/degradado/caído para cada servicio. `[modelo: sonnet]`
- [ ] 5.2 Manejo del caso "sin MCP servers registrados más allá del de fábrica": mostrar ese único servidor o el estado vacío correspondiente. Verificación: test de contrato cubre ambos casos. `[modelo: sonnet]`
- [ ] 5.3 UI de salud del sistema con alcance acotado a estado de servicios + enlaces externos a Uptime Kuma y dashboards de Langfuse, sin backups/restore/retención/kill-switch (fuera de alcance, ver `design.md` Decisión 5). Verificación: test de componente confirma que la vista no renderiza ninguna acción de mutación. `[modelo: sonnet]`
- [ ] 5.4 Textos y labels de salud del sistema. Verificación: catálogo i18n completo. `[modelo: haiku]`

## 6. Cierre

- [ ] 6.1 Incorporar a `docs/03-glosario-dominio.md` los términos usados por este change que aún no estén registrados (Rol Admin/Técnico/Funcional, Instancia, Sesión, Turno, Perfil de modelo, modelo alterno, tarifas cache hit/miss, `cache_hit_rate`, Cuota, Liberación, Tarjeta HITL, Kill switch, Registro de Prompts, MCP Server), coordinando con la sincronización ya prevista en `a01-fundacion-repo` tarea 1.3 para no duplicar la entrada. Verificación: cero términos usados en este change sin entrada en el glosario. `[modelo: haiku]`
- [ ] 6.2 Review final del change: el guard de rol Admin cubre las 4 superficies, ninguna acción de mutación quedó expuesta, el alcance de "Salud del sistema" coincide exactamente con `docs/07-roadmap.md` fila d19, y specs↔diseño↔tareas son consistentes entre sí. Verificación: checklist del reviewer en el PR. `[modelo: opus]`
