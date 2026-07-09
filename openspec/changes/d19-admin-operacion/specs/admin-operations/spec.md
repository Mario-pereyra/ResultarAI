## ADDED Requirements

### Requirement: Autorización exclusiva de rol Admin para la consola de operación

El tablero de operación, la telemetría y analítica de consumo, el audit log global y la salud del sistema SHALL estar restringidos exclusivamente a cuentas con rol Admin. Un `ActionRequest` de una cuenta con rol Técnico o Funcional sobre cualquiera de estas cuatro superficies SHALL resolverse con efecto `deny` en el `PolicyGate` (`a03-core-gobernanza`) y SHALL producir su `AuditEvent` correspondiente. La respuesta al intento denegado SHALL redirigir al inicio de la sesión del rol sin confirmar la existencia de la ruta (`design/VISTAS/07-admin-operacion.md` §0.1).

#### Scenario: Técnico intenta acceder al tablero de operación

- **WHEN** una cuenta con rol Técnico solicita la vista del tablero de operación (vista 30) o su endpoint equivalente
- **THEN** el `PolicyGate` resuelve `deny`, el sistema redirige al inicio de la sesión del Técnico sin mostrar mensaje ni toast que confirme la ruta, y se registra el `AuditEvent` del intento denegado

#### Scenario: Funcional intenta acceder al audit log global por deep link directo

- **WHEN** una cuenta con rol Funcional navega directamente a la URL del audit log global (vista 37), conociendo o no su existencia
- **THEN** el sistema deniega el acceso, redirige al inicio de la sesión de Funcional, y registra el `AuditEvent` del intento

#### Scenario: Admin con TOTP verificado accede sin fricción

- **WHEN** una cuenta con rol Admin y sesión con TOTP verificado solicita cualquiera de las cuatro superficies de esta capability
- **THEN** el `PolicyGate` resuelve `allow` y la vista o el endpoint responde con los datos correspondientes

### Requirement: Resumen del día en el tablero de operación

El tablero de operación (vista 30, `design/VISTAS/07-admin-operacion.md` §1) SHALL mostrar, para el rango seleccionado (hoy o 7 días), al menos: costo del período con su delta contra el período anterior, `cache_hit_rate` global del período con su tendencia, conteo de escalaciones a Pro (`b05-gateway-modelos`), agentes activos y tasa de error, junto con un resumen de salud de los servicios de la plataforma.

#### Scenario: Admin abre el tablero con datos del día

- **WHEN** un Admin abre el tablero de operación con el rango "Hoy" seleccionado
- **THEN** el sistema muestra costo del día, `cache_hit_rate` del período, escalaciones a Pro, agentes activos y tasa de error, calculados sobre datos ya persistidos (`b04-persistencia-postgres`) y trazados (`b07-observabilidad`)

#### Scenario: Instancia recién instalada sin sesiones

- **WHEN** un Admin abre el tablero de una instancia sin sesiones registradas todavía
- **THEN** los KPIs se muestran en cero o `—` (nunca un error) y las tablas dependientes muestran un estado vacío explicativo

#### Scenario: Telemetría de Langfuse degradada

- **WHEN** el adapter de Langfuse (`b07-observabilidad`) no responde al calcular los KPIs de costo o `cache_hit_rate`
- **THEN** el tablero muestra los montos con el prefijo de estimación y un aviso degradado, sin bloquear el resto del tablero que no depende de esa fuente

### Requirement: Alertas operativas visibles en el tablero

El tablero de operación SHALL mostrar un panel de alertas activas agregando, como mínimo: cuentas o grupos con Cuota en o cerca del umbral de bloqueo (`d16-cuotas-liberaciones`), tarjetas de aprobación HITL próximas a expirar, y kill-switches actualmente activos (`d20-gobernanza-plataforma`). El tablero SHALL leer el estado de estas fuentes sin ofrecer ninguna acción de mutación sobre ellas: la resolución de cada alerta se ejecuta en su propia superficie de gestión.

#### Scenario: Alertas activas agregadas en el panel

- **WHEN** existen simultáneamente una Cuota de grupo al 100%, una tarjeta HITL a menos de 15 minutos de su expiración y un kill-switch de tool activo
- **THEN** el panel de alertas del tablero muestra las tres, cada una con un enlace directo a su superficie de gestión (Cuotas, bandeja HITL, o gobernanza de kill-switches respectivamente)

#### Scenario: Sin alertas activas

- **WHEN** ninguna Cuota está cerca del umbral, ninguna tarjeta HITL está por expirar y ningún kill-switch está activo
- **THEN** el panel de alertas muestra un estado vacío informativo, no un error

#### Scenario: El tablero no puede resolver alertas

- **WHEN** un Admin hace click en una alerta del panel
- **THEN** el sistema navega a la superficie de gestión correspondiente (fuera de esta capability); el tablero mismo no expone un botón de aprobar, denegar ni apagar

### Requirement: Consumo agregado por dimensión y periodo

El sistema SHALL exponer, exclusivamente al rol Admin, el consumo agregado agrupable por usuario, por grupo/equipo (`d11-identidad-acceso`), por agente y por perfil de modelo (`b05-gateway-modelos`), con selector de periodo día/semana/mes, calculado sobre las tarifas de cache hit/miss separadas ya reportadas por `b05-gateway-modelos` y persistidas por `b07-observabilidad`.

#### Scenario: Admin agrupa el consumo por grupo y por semana

- **WHEN** un Admin selecciona agrupación "grupo/equipo" y periodo "semana" en la analítica de consumo
- **THEN** el sistema devuelve el costo agregado por grupo para cada semana del rango, distinguiendo tokens/costo de cache hit y de cache miss

#### Scenario: Admin agrupa el consumo por perfil de modelo

- **WHEN** un Admin selecciona agrupación "perfil de modelo" para el mes en curso
- **THEN** el sistema devuelve el costo agregado por cada perfil de modelo usado en el periodo, incluyendo el consumo atribuido a respuestas de modelo alterno por fallback

### Requirement: Top sesiones caras y cache_hit_rate por usuario

La analítica de consumo SHALL exponer un listado de las sesiones de mayor costo del periodo seleccionado (con enlace a su traza en Langfuse) y el `cache_hit_rate` calculado por usuario, para permitir detectar patrones de uso que rompen sistemáticamente el cache (por ejemplo, ediciones frecuentes que generan ramas nuevas o prompts que varían el prefijo cacheable).

#### Scenario: Admin revisa las sesiones más caras del periodo

- **WHEN** un Admin abre el listado de top sesiones caras para el rango de 7 días
- **THEN** el sistema devuelve las sesiones ordenadas por costo descendente con usuario, agente, perfil de modelo y turnos, cada una con un enlace a su traza

#### Scenario: Usuario con cache_hit_rate anómalamente bajo

- **WHEN** el `cache_hit_rate` calculado para un usuario en el periodo es significativamente menor que el `cache_hit_rate` global del mismo periodo
- **THEN** ese usuario aparece identificable en el listado de `cache_hit_rate` por usuario, permitiendo al Admin investigar el patrón que rompe el cache

### Requirement: Export CSV de telemetría

El sistema SHALL permitir al Admin exportar a CSV el consumo agregado y el listado de top sesiones caras del periodo y agrupación actualmente filtrados. Cada exportación SHALL quedar registrada en el Audit Log.

#### Scenario: Admin exporta el consumo agrupado por usuario del mes

- **WHEN** un Admin, con la analítica filtrada por agrupación "usuario" y periodo "mes", ejecuta "Exportar CSV"
- **THEN** el sistema genera un archivo CSV con los datos agregados exactamente como están filtrados y registra un `AuditEvent` del export

### Requirement: Enlaces a dashboards de Langfuse desde la analítica de consumo

La analítica de consumo SHALL ofrecer enlaces directos a los dashboards nativos de Langfuse para profundizar más allá de lo agregado en la consola, construidos con las naming conventions de traza/sesión/usuario documentadas por `b07-observabilidad`, sin reimplementar ningún gráfico o dashboard que Langfuse ya ofrezca.

#### Scenario: Admin profundiza una sesión desde la analítica

- **WHEN** un Admin tiene el `session_id` de una sesión mostrada en la analítica de consumo y hace click en "Abrir en Langfuse"
- **THEN** el sistema navega a la URL de Langfuse construida con la convención de nombres documentada por `b07-observabilidad`, mostrando esa sesión con todos sus turnos, sin llamar a ninguna API adicional del adapter

### Requirement: Consulta filtrada del audit log global

El audit log global (vista 37, `design/VISTAS/07-admin-operacion.md` §5) SHALL permitir al Admin consultar los `AuditEvent` de toda la instancia filtrando por actor (`user`), tipo de evento, entidad afectada, rango de fechas, y `tenant`/`environment` cuando el evento los incluya, con orden fijo por fecha-hora descendente y paginación clásica.

#### Scenario: Admin filtra por actor y rango de fechas

- **WHEN** un Admin filtra el audit log global por un `user` específico y un rango de fechas
- **THEN** el sistema devuelve únicamente los `AuditEvent` de ese actor dentro del rango, paginados, sin alterar el orden fijo por fecha-hora descendente

#### Scenario: Admin filtra por tipo de evento de gestión de usuarios

- **WHEN** un Admin filtra el audit log global por los tipos de evento emitidos por `d11-identidad-acceso` (alta, cambio de rol, suspensión, reset, revocación de sesiones, exigencia de TOTP)
- **THEN** el sistema devuelve solo los `AuditEvent` de esos tipos, cada uno distinguible por su tipo de mutación conforme al contrato de `d11-identidad-acceso`

#### Scenario: Admin filtra por eventos con contexto de tenant/environment

- **WHEN** un Admin filtra el audit log global por un valor de `tenant` o `environment` específico
- **THEN** el sistema devuelve solo los `AuditEvent` cuyo contexto coincide; los eventos sin ese contexto (por ejemplo, mutaciones de identidad sin acción sobre un `tenant` de ERP) no aparecen en ese filtro

#### Scenario: Sin resultados por filtros

- **WHEN** la combinación de filtros aplicada no coincide con ningún `AuditEvent`
- **THEN** el sistema muestra un estado vacío que ofrece limpiar los filtros, distinto del estado de error

### Requirement: Audit log global de solo lectura, append-only

La consulta del audit log global SHALL ser estrictamente de lectura: ninguna cuenta, incluida Admin, SHALL poder editar ni eliminar un `AuditEvent` desde esta vista, consistente con la invariante append-only e inmutable del `AuditEvent` (`a03-core-gobernanza`). La vista SHALL declarar visiblemente esta condición.

#### Scenario: La vista no ofrece edición ni borrado

- **WHEN** un Admin consulta el audit log global
- **THEN** ninguna fila ni el panel de detalle expandido ofrece una acción de editar o eliminar un `AuditEvent`, y la vista muestra de forma permanente la condición append-only/inmutable

#### Scenario: Payload expandido nunca se trunca silenciosamente

- **WHEN** un Admin expande el detalle de un `AuditEvent` con un payload extenso
- **THEN** el sistema muestra el payload completo (con scroll si corresponde), sin truncarlo, porque el audit log es evidencia forense

### Requirement: Export CSV del audit log global

El sistema SHALL permitir al Admin exportar a CSV el conjunto de `AuditEvent` que resulte de los filtros activos, incluyendo el payload serializado de cada evento. Cada exportación SHALL quedar registrada en el propio Audit Log como un `AuditEvent` distinguible de tipo export.

#### Scenario: Admin exporta el audit log filtrado

- **WHEN** un Admin, con filtros activos de fecha y actor, ejecuta "Exportar CSV" sobre el audit log global
- **THEN** el sistema genera el CSV respetando esos filtros, incluye el payload serializado de cada `AuditEvent`, y registra un `AuditEvent` propio del export

#### Scenario: Export de rango extenso corre en segundo plano

- **WHEN** el rango exportado supera un volumen de registros configurado como umbral de ejecución diferida
- **THEN** el export se ejecuta en segundo plano y notifica al Admin al finalizar, sin bloquear la consulta del audit log mientras tanto

### Requirement: Deep links al audit log global desde otras vistas

El audit log global SHALL aceptar parámetros de filtro pre-aplicados en su URL, de forma que otras vistas de la consola (por ejemplo, el tablero de operación o la bandeja de Cuotas) puedan enlazar directamente a los eventos relevantes de una entidad específica sin que el Admin tenga que reconstruir los filtros a mano.

#### Scenario: Deep link desde el tablero a los eventos de una entidad

- **WHEN** un Admin sigue un enlace desde el tablero de operación que referencia una entidad concreta (por ejemplo, un usuario o una Cuota)
- **THEN** el audit log global se abre con el filtro de entidad ya aplicado, mostrando exactamente los `AuditEvent` de esa entidad

### Requirement: Estado de servicios en la vista de salud del sistema

La vista de salud del sistema (vista 39, alcance acotado a estado y enlaces conforme a `docs/07-roadmap.md`) SHALL mostrar, para cada servicio de la plataforma —gateway/LLM, PostgreSQL, Langfuse y los MCP servers registrados (`c09-mcp-tools`)—, su estado (operativo, degradado, caído), latencia y el momento del último chequeo.

#### Scenario: Servicios operativos

- **WHEN** un Admin abre la vista de salud del sistema y todos los servicios responden dentro de su umbral de latencia
- **THEN** cada servicio se muestra con estado operativo, su latencia y el momento del último chequeo

#### Scenario: Un MCP server registrado está caído

- **WHEN** un MCP server registrado en el Tool Registry (`c09-mcp-tools`) no responde al chequeo de salud
- **THEN** ese MCP server se muestra con estado caído, distinguible del resto de servicios operativos, sin ocultar el resto de la vista

#### Scenario: Sin MCP servers registrados todavía

- **WHEN** la instancia no tiene ningún MCP server registrado más allá del servidor de ejemplo de fábrica
- **THEN** la sección de MCP servers muestra ese único servidor sin error, o un estado vacío si tampoco existe el de fábrica

### Requirement: Enlaces externos desde la salud del sistema

La vista de salud del sistema SHALL ofrecer enlaces externos directos a Uptime Kuma y a los dashboards de Langfuse, abriendo en una pestaña nueva, en vez de reimplementar el historial de uptime o los gráficos de costo/cache que esas herramientas ya ofrecen.

#### Scenario: Admin abre Uptime Kuma desde la vista de salud

- **WHEN** un Admin hace click en el enlace a Uptime Kuma desde la vista de salud del sistema
- **THEN** el sistema abre Uptime Kuma en una pestaña nueva, sin reimplementar su historial de uptime dentro de la consola
