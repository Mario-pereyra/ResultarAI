## Context

`d19-admin-operacion` es un slice vertical de solo lectura: no introduce ninguna entidad de dominio nueva, agrega sobre datos que otros changes ya persisten o emiten (`a03-core-gobernanza` para `AuditEvent`/`PolicyDecision`, `b04-persistencia-postgres` para sesiones/consumo, `b05-gateway-modelos` para tarifas hit/miss y perfil de modelo, `b07-observabilidad` para trazas y naming conventions de Langfuse, `d11-identidad-acceso` para usuarios/grupos, `d16-cuotas-liberaciones` para Cuota/Liberación). El reto de diseño no es modelar dominio nuevo, sino: (1) reutilizar el `PolicyGate` para el guard de rol Admin sin inventar un segundo mecanismo de autorización, (2) definir cómo se agregan datos que hoy viven repartidos entre Postgres y Langfuse sin duplicar lo que Langfuse ya calcula, y (3) acotar el alcance de "Salud del sistema" (vista 39 del design, más amplia que lo que pide el roadmap) sin dejar cabos sueltos.

`design/VISTAS/07-admin-operacion.md` es la fuente normativa de las 4 vistas visuales de este módulo, pero fue escrita antes del pivote 2026-07-09 y antes de que el roadmap acotara "Salud del sistema" a estado + enlaces. Este documento explica cómo se reconcilian ambas fuentes.

## Goals / Non-Goals

**Goals:**

- Guard de rol Admin único, implementado como una condición de rol sobre `ActionRequest`/`PolicyGate` (`a03`), no como un middleware paralelo.
- Agregaciones de telemetría y audit log expuestas como casos de uso de lectura en `app/`, sin lógica de dominio nueva en `core/`.
- Deep links a Langfuse construidos por convención de nombres (documentada en `b07`), nunca por una API adicional del adapter.
- Acotar "Salud del sistema" a lo que pide `docs/07-roadmap.md` (estado de servicios + enlaces), dejando explícito qué parte de `design/VISTAS/07-admin-operacion.md` §6 queda fuera y por qué.

**Non-Goals:**

- Ningún almacenamiento nuevo de series temporales: las agregaciones de telemetría se calculan sobre lo que `b04`/`b07` ya persisten, no se crea un data warehouse propio.
- Ninguna acción de mutación: el guard cubre lectura; edición de cuotas, usuarios, prompts o kill-switches vive en sus propios changes.
- Ningún catálogo cerrado de "tipos de evento" de audit log: se referencia el tipo de mutación que cada change emisor ya define (`d11`, `a03`, y los que sigan) en vez de fijar aquí una lista exhaustiva que otros changes todavía no han especificado.

## Decisions

1. **El guard de rol Admin es una Policy, no un mecanismo nuevo.** Las 4 superficies emiten un `ActionRequest` con `agent`/`skill` fijo de administración y `operation_type: read`; el `PolicyGate` de `a03-core-gobernanza` resuelve `allow`/`deny` según el rol del `user`, igual que cualquier otra acción gobernada. Alternativa descartada: un decorador de autorización específico de `app/` fuera del `PolicyGate` — se descarta porque duplicaría la regla dura 4 (toda decisión pasa por el gate y va al audit log) y crearía dos fuentes de verdad sobre "quién puede qué".
2. **Telemetría se calcula por consulta agregada sobre Postgres, no se re-materializa desde Langfuse.** `b07-observabilidad` es la fuente de trazas y de `cache_hit_rate`/costo por turno; `b04-persistencia-postgres` persiste sesiones y mensajes. La analítica de consumo consulta agregados (SUM/GROUP BY) sobre esas tablas ya persistidas para usuario/grupo/agente/perfil de modelo y periodo. Langfuse queda como la fuente de profundización vía deep link, nunca como backend de consulta síncrona de la consola (evita acoplar la disponibilidad del tablero a la de Langfuse, y ya está cubierto por el escenario "Telemetría de Langfuse degradada"). Alternativa descartada: consultar la API de Langfuse en cada carga del tablero — introduce una dependencia dura de disponibilidad y de límites de tasa sobre una herramienta externa para una pantalla de aterrizaje.
3. **`cache_hit_rate` por usuario se deriva de los mismos contadores hit/miss que ya expone `b05-gateway-modelos` por turno**, agregados por usuario y periodo — no se introduce un cálculo ni una definición de "hit rate" distinta de la que ya usa el tablero global o Langfuse.
4. **El catálogo de "tipo de evento" del audit log global no se fija en este change.** Cada change que emite `AuditEvent` (`a03`, `d11`, y los que sigan: `d16`, `d17`, `d20`) ya declara su propio conjunto de mutaciones auditables. El filtro de "tipo de evento" del audit log global se implementa como un valor abierto derivado de lo emitido, no como un enum cerrado escrito en este spec — evita que `d19` tenga que reabrirse cada vez que otro change agregue un tipo de evento nuevo.
5. **Alcance de "Salud del sistema" recortado respecto de `design/VISTAS/07-admin-operacion.md` §6.** El roadmap (`docs/07-roadmap.md`, fila d19) pide "estado de servicios... con enlaces a Uptime Kuma y dashboards Langfuse — enlazar, no reimplementar", más acotado que el mockup del design (que además incluye backups/prueba de restore, jobs de retención y el kill-switch global de plataforma). Se prioriza el roadmap como fuente de alcance vigente del pivote (`docs/07-roadmap.md` es la fuente que ordena qué entra en cada change; `design/` sigue siendo normativo de cómo se ve cada pieza cuando entre). Backups/restore y jobs de retención quedan para un change de operación de despliegue (candidato: `e24-despliegue-operacion`, que ya trae Docker Compose/backups); el kill-switch global de plataforma queda para una revisión de `d20-gobernanza-plataforma` (que ya trae el kill-switch por agente/tool) o un change dedicado — ningún roadmap actual lo nombra explícitamente, así que se deja como hueco identificado en vez de asumirlo tácitamente en `d19`.
6. **"Bridges" del mockup se traduce a "MCP servers registrados".** El mockup (§6) lista bridges por dispositivo (Edge Connector Windows), que es infraestructura de la Etapa P (personalización Protheus). En el alcance de fábrica, el equivalente genérico es el listado de MCP servers registrados en el Tool Registry (`c09-mcp-tools`); el listado de bridges por dispositivo se reintroduce cuando `d19` (o su revisión) incorpore Etapa P.
7. **Export CSV grande corre en segundo plano** (telemetría y audit log), replicando el patrón ya usado por el mockup del audit log (`design/VISTAS/07-admin-operacion.md` §5) y evitando bloquear un request HTTP por minutos.

## Riesgos / Trade-offs

- [Acoplar el guard de Admin a `PolicyGate` antes de que `b06-runtime-grafos` exista] → Mitigación: el `PolicyGate` de `a03` es una función pura sin dependencia de runtime; se puede invocar desde `app/` como librería sin esperar al grafo de LangGraph.
- [Agregaciones de telemetría lentas si crecen las tablas de mensajes/sesiones sin índices dedicados] → Mitigación: se documenta como tarea de `b04-persistencia-postgres`/este change definir índices por `(user, created_at)`/`(agent, created_at)`; no bloquea la especificación funcional.
- [Recortar "Salud del sistema" deja backups/restore y kill-switch global sin change asignado] → Mitigación: documentado explícitamente en `proposal.md` (No-objetivos) y aquí (Decisión 5) para que no se pierda al planear `e24`/`d20`.
- [El filtro abierto de "tipo de evento" del audit log puede quedar poco descubrible en la UI si el catálogo crece mucho] → Mitigación: se agrupa por categoría (identidad, cuotas, HITL, config, seguridad) en el selector, sin fijar los códigos exactos en este spec.

## Open Questions

- ¿La CRUD de defaults/overrides de Cuota (pestaña "Cuotas" de la vista 33) se especifica finalmente en `d16-cuotas-liberaciones` o en `d19-admin-operacion`? `d16-cuotas-liberaciones/proposal.md` (No-objetivos) la difiere "junto a `d19-admin-operacion` / configuración de instancia", mientras que el alcance asignado a este change la excluye explícitamente. Este change asume que permanece fuera de `d19` (consistente con la instrucción de no redefinir cuotas) y deja la resolución para cuando se revise `d16` o se escriba `d20`.
- ¿Dónde entra el kill-switch global de plataforma ("apagar el chat de la plataforma") y el flujo de prueba de restore de backups? Ningún change del roadmap vigente los nombra explícitamente (ver Decisión 5); se recomienda decidirlo antes de escribir `d20` o `e24`.
