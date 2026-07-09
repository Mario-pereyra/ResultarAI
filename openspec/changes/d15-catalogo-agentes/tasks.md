# Tasks — d15-catalogo-agentes

## 1. Read-model de catálogo (persistencia + fixtures)

- [ ] 1.1 Migración Alembic (`b04-persistencia-postgres`) para `agent_catalog_entry`: `agent_id`, `description`, `limits[]`, `use_cases[]`, `target_roles[]`, `examples[3]`, `owner`, flag `beta`. Verificación: migración corre limpia sobre una base vacía y revierte sin error. `[modelo: sonnet]`
- [ ] 1.2 Sembrar fixture de fábrica de `default_chat`: descripción, límites, 3-5 casos de uso, 3 ejemplos de prompt, owner. Verificación: escenario "Ficha de fábrica completa" de `agent-catalog` pasa para `default_chat`. `[modelo: haiku]`
- [ ] 1.3 Sembrar fixture de fábrica del agente de ejemplo de `a02-core-manifiestos`. Verificación: mismo escenario pasa para el agente de ejemplo. `[modelo: haiku]`
- [ ] 1.4 Repositorio de catálogo (`resultarai/adapters/persistence_postgres/`) que compone el read-model completo cruzando `agent_catalog_entry` con el Agent Registry (`a02`). Verificación: test de integración arma el objeto ficha combinando ambas fuentes sin campos faltantes. `[modelo: sonnet]`

## 2. Contrato de visibilidad (`agent-visibility`)

- [ ] 2.1 Caso de uso `resolve_agent_visibility(agent_id, role)`: consulta de entrada explícita de matriz (stub listo para `d20-gobernanza-plataforma`) + defaults por estado comercial. Verificación: tests de los 3 escenarios de "Defaults por status del agente". `[modelo: sonnet]`
- [ ] 2.2 Piso de seguridad: intersección obligatoria con la clasificación lectura/escritura de Tools (`a02`/`c09-mcp-tools`), no anulable por la matriz. Verificación: test del escenario "Un Funcional no ve un agente con tools de escritura aunque la matriz lo marque visible". `[modelo: opus]`
- [ ] 2.3 Resolución de "no disponible" sin filtrar existencia (deep link fuera de matriz vs. agente inexistente). Verificación: test que compara ambas respuestas y confirma que son indistinguibles. `[modelo: sonnet]`
- [ ] 2.4 Verificación de datos de fábrica: `default_chat` y el agente de ejemplo visibles para los 3 roles sin matriz configurada. Verificación: test del escenario "Catálogo de fábrica sin matriz configurada". `[modelo: haiku]`

## 3. Contrato de kill-switch

- [ ] 3.1 Caso de uso `resolve_agent_enabled(agent_id)` con default "habilitado" ante ausencia de bandera (mientras `d20` no exista). Verificación: test del escenario "Sin bandera de kill-switch configurada, el agente está habilitado". `[modelo: sonnet]`
- [ ] 3.2 Configuración de instancia mostrar-deshabilitado vs. ocultar (valor simple de config, sin UI de administración). Verificación: tests de los 2 escenarios de "Estado de kill-switch por agente". `[modelo: sonnet]`

## 4. Endpoints de catálogo (`app/api`)

- [ ] 4.1 `GET` listar agentes visibles para el rol autenticado (status `active` + `agent-visibility` + kill-switch), con búsqueda por texto y orden fijo. Verificación: tests de contrato de los escenarios de grilla filtrada, búsqueda y orden. `[modelo: sonnet]`
- [ ] 4.2 `GET` ficha de agente por `slug` (capa común siempre; ficha técnica solo si el rol es Técnico o Admin). Verificación: tests de contrato que confirman ausencia total de la ficha técnica en la respuesta para Funcional. `[modelo: sonnet]`
- [ ] 4.3 `POST` iniciar conversación: delega en el endpoint de creación de sesión de `d13-chat-conversacion`, sin reimplementar su lógica. Verificación: test de integración que crea la sesión y confirma el agente asociado. `[modelo: sonnet]`
- [ ] 4.4 Endpoint "Ver como rol" (solo Admin, solo lectura). Verificación: test que confirma que la operación no escribe en `agent_catalog_entry`, en la matriz ni en el audit log. `[modelo: sonnet]`

## 5. Costo estimado y ficha técnica

- [ ] 5.1 Agregación de costo estimado por sesión desde trazas de `b07-observabilidad` sobre una ventana configurable por instancia, con "sin datos todavía" (agente nuevo) y marcador `~` (telemetría degradada). Verificación: tests de ambos escenarios de costo. `[modelo: sonnet]`
- [ ] 5.2 Tabla de Tools de la ficha técnica desde Skills habilitadas del agente + clasificación lectura/escritura (`a02`/`c09-mcp-tools`). Verificación: test del escenario "Tabla de tools marca las de escritura". `[modelo: sonnet]`
- [ ] 5.3 Versión activa como sustituto transitorio de "versión de prompt" (usa `AgentManifest.version` con etiqueta explícita). Verificación: test del escenario "Versión mostrada antes de que exista el Registro de Prompts". `[modelo: sonnet]`
- [ ] 5.4 Placeholder "sin evals aún" en la tab Evals mientras `e25-evals-gates` no esté archivado. Verificación: test del escenario "Ficha técnica sin evals antes de e25". `[modelo: haiku]`

## 6. Frontend — grilla (vista 13)

- [ ] 6.1 Componente de card (`agent-card__cases`, `agent-card__tech`, `agent-card__foot`) con capa técnica condicional por rol, ausente del DOM (no solo oculta) para Funcional. Verificación: test por rol confirma ausencia en el DOM. `[modelo: sonnet]`
- [ ] 6.2 Búsqueda con debounce 200 ms, filtro de disponibilidad y orden fijo (disponibles primero, alfabético). Verificación: tests de interacción de los escenarios de búsqueda y orden. `[modelo: sonnet]`
- [ ] 6.3 Estados de carga (skeleton >300 ms), vacío (rol sin agentes / búsqueda sin resultados) y error `CATALOG_OFFLINE` con reintentar. Verificación: tests de los 3 estados de la grilla. `[modelo: sonnet]`
- [ ] 6.4 Selector "Ver como rol" (solo Admin), re-renderiza sin mutar sesión real. Verificación: test que confirma que la sesión del Admin no cambia tras usarlo. `[modelo: sonnet]`
- [ ] 6.5 Soporte móvil de la grilla (1 columna, CTA a ancho completo, objetivo táctil ≥44 px). Verificación: test/snapshot en viewport 380 px. `[modelo: sonnet]`

## 7. Frontend — ficha de agente (vista 14)

- [ ] 7.1 Cabecera + capa común (descripción, límites, casos de uso, ejemplos clicables que prellenan el composer sin enviar). Verificación: tests de los escenarios de capa común y de ejemplos clicables. `[modelo: sonnet]`
- [ ] 7.2 Ficha técnica con tabs (Resumen/Tools/Prompt/Evals) y roving focus por teclado (WAI-ARIA tabs). Verificación: test de navegación por teclado con flechas y `aria-selected`. `[modelo: sonnet]`
- [ ] 7.3 Estado "no disponible" unificado (inexistente / fuera de matriz / kill-switch oculto) con el mismo mensaje en los 3 casos. Verificación: test que confirma la respuesta idéntica. `[modelo: sonnet]`
- [ ] 7.4 Indicador de kill-switch "No disponible temporalmente" con CTA y ejemplos deshabilitados (visibles, sin acción). Verificación: tests de los 2 escenarios de kill-switch en la ficha. `[modelo: sonnet]`
- [ ] 7.5 Accesibilidad AA de grilla y ficha (contraste en ambos temas, foco visible, aria). Verificación: auditoría automatizada (axe o equivalente) sin violaciones críticas. `[modelo: sonnet]`

## 8. Cierre

- [ ] 8.1 Revisión final de los textos de fábrica (capa común sin jerga técnica; ficha técnica con jerga controlada) contra `design/VISTAS/03-catalogo.md`. Verificación: checklist manual campo por campo. `[modelo: haiku]`
- [ ] 8.2 Review final del change: consistencia specs↔código, piso de seguridad de Funcional verificado con un caso adversarial (matriz mal configurada exponiendo un agente de escritura), confirmación de que no se agregó código a `core/`. Verificación: checklist del reviewer en el PR. `[modelo: opus]`
