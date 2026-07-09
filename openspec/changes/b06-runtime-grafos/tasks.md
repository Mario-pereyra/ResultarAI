## 1. Contratos puros de `core/routing` (Skill Router y ciclo del turno)

- [x] 1.1 Definir `RoutingDecision` (`action: answer_directly|activate_skill`, `target` opcional, `reason`) en `resultarai/core/routing/skill_router.py`, inmutable. Test: `tests/core/test_routing_decision.py`, sin red. `[modelo: opus]`
- [x] 1.2 Implementar `SkillRouter.decide(turn, routing_manifest)` puro: match de intent contra las reglas activas del Routing Manifest, fallback `answer_directly` con razón que declara la ausencia de coincidencia. Test: `tests/core/test_skill_router.py` cubre los 3 escenarios de `specs/skill-router/spec.md` (intent conocido, general, desconocido), sin red. `[modelo: opus]`
- [x] 1.3 Implementar `to_action_request(routing_decision, turn_context)` que traduce una `RoutingDecision` en el `ActionRequest` que consumirá `PolicyPort` (contrato de `a03-core-gobernanza`). Test: `tests/core/test_skill_router_audit.py` verifica que `activate_skill` y `answer_directly` producen un `ActionRequest` coherente con los campos de la spec (skill, operation_type, risk_level), sin red. `[modelo: opus]`
- [x] 1.4 Definir `TurnPhase` (`receive`, `route`, `execute_graph`, `respond`) y la función pura `steps_requiring_gate(turn)` que enumera, para un turno dado, qué pasos del grafo requieren evaluación del Policy Gate (responder, activar skill, compaction). Test: `tests/core/test_turn_phases.py`, sin red. `[modelo: opus]`
- [x] 1.5 Implementar la regla pura de compaction en `resultarai/core/routing/compaction.py`: `should_compact(session_context_usage, model_profile_window, already_compacted)` → bool, umbral 80%, una sola vez por sesión. Test: `tests/core/test_compaction_rule.py` cubre los escenarios de `specs/context-compaction/spec.md` sobre el umbral y el "una sola vez", sin red. `[modelo: opus]`

## 2. Fixtures y dobles para tests

- [ ] 2.1 Crear fixture de Routing Manifest de ejemplo en `tests/core/fixtures/routing_manifest_default_chat.yaml`, reutilizando la forma del manifiesto de fábrica de `a02-core-manifiestos`, con las 3 reglas usadas en los escenarios de `skill-router` (`erp_query` → `activate_skill`, `general_question` → `answer_directly`, sin regla para intent desconocido). Verificación: el fixture valida contra el schema de Routing Manifest de `a02` (test de carga). `[modelo: haiku]`
- [ ] 2.2 Crear dobles deterministas de `PolicyPort`, `LLMPort`, `TracePort` y `StatePort` en `tests/contracts/fixtures/doubles.py` (respuestas `allow`/`deny`/`escalate_hitl` configurables por test; `LLMPort` doble devuelve texto fijo; `TracePort`/`StatePort` dobles registran en memoria para aserciones). Verificación: `tests/contracts/test_doubles_smoke.py` instancia cada doble y confirma que cumple el `Protocol` correspondiente. `[modelo: haiku]`
- [ ] 2.3 Crear fixture de sesión (`tests/contracts/fixtures/session_near_limit.py`) con historial de mensajes cuyo tamaño se acerca y cruza el 80% de la ventana de un perfil de modelo de prueba, para los tests de compaction. `[modelo: haiku]`

## 3. Adapter `runtime_langgraph`: graph template de respuesta directa

- [ ] 3.1 Crear `resultarai/adapters/runtime_langgraph/default_chat_graph.py`: nodos `receive`, `route` (invoca `SkillRouter` de `core/routing`), `execute_graph`, `respond` (invoca `LLMPort`); sin ningún nodo que invoque `ToolPort`. `[modelo: sonnet]`
- [ ] 3.2 Cablear el nodo de Policy Gate por paso: antes de `respond` y antes de una eventual activación de skill, construye el `ActionRequest` (vía `to_action_request` de `core/routing`) y llama a `PolicyPort`; rama a `allow` (continúa), `deny` (nodo de respuesta de restricción) o `escalate_hitl` (nodo de suspensión). `[modelo: sonnet]`
- [ ] 3.3 Implementar el nodo de compaction: en la frontera de turno, llama a `should_compact` (`core/routing/compaction.py`) vía el estado de sesión de `StatePort`; si aplica, pasa por el Policy Gate, genera el resumen como mensaje nuevo append-only (sin tocar mensajes previos) y marca la sesión como compactada en `StatePort`. `[modelo: sonnet]`
- [ ] 3.4 Emitir eventos de traza vía `TracePort` en cada fase del ciclo del turno (`receive`, `route`, `execute_graph`, `respond`) con un `turn_id` común, y el indicador `compacted=true` con el rango resumido cuando aplica compaction. `[modelo: sonnet]`
- [ ] 3.5 Registrar `default_chat_graph` bajo el nombre resuelto desde `runtime.graph` del Agent Manifest de `default_chat` (`a02`), sin que `resultarai/core/` importe `langgraph` en ningún punto de la resolución. `[modelo: sonnet]`

## 4. Tests de contrato del runtime

- [ ] 4.1 `tests/contracts/test_default_chat_graph_direct_answer.py`: turno sin skill activada responde directo, `LLMPort` invocado, ningún `ToolPort` invocado (escenarios de `specs/agent-runtime/spec.md`, requirement "Graph template de respuesta directa"). `[modelo: sonnet]`
- [ ] 4.2 `tests/contracts/test_default_chat_graph_turn_cycle.py`: turno completo emite trazas de las 4 fases con `turn_id` común; turno interrumpido no reporta fases posteriores. `[modelo: sonnet]`
- [ ] 4.3 `tests/contracts/test_default_chat_graph_policy_gate.py`: los 3 escenarios de Policy Gate por paso (`allow` continúa, `deny` detiene sin ejecutar y responde con restricción, `escalate_hitl` suspende), cada uno verificando el `AuditEvent` emitido. `[modelo: sonnet]`
- [ ] 4.4 `tests/contracts/test_default_chat_graph_no_tools.py`: inspección de nodos del grafo confirma que ninguno invoca `ToolPort`. `[modelo: sonnet]`
- [ ] 4.5 `tests/contracts/test_compaction_trigger.py`: turno que cruza el 80% dispara compaction en la frontera siguiente (no a mitad de turno); disparar la compaction pasa por el Policy Gate. `[modelo: sonnet]`
- [ ] 4.6 `tests/contracts/test_compaction_once_per_session.py`: sesión ya compactada no vuelve a compactar; emite evento trazable de umbral alcanzado sin re-disparo. `[modelo: sonnet]`
- [ ] 4.7 `tests/contracts/test_compaction_append_only.py`: mensajes previos conservan contenido y `parent_id`; el resumen se agrega como mensaje nuevo; indicador `compacted=true` con rango resumido queda disponible para el turno siguiente. `[modelo: sonnet]`
- [ ] 4.8 `tests/contracts/test_compaction_replay_as_new_message.py`: repetir contenido compactado (releer un adjunto) se procesa como mensaje nuevo append-only sin revertir el resumen. `[modelo: sonnet]`

## 5. Cierre

- [ ] 5.1 Revisión final del change: `uv run lint-imports` confirma que `resultarai/adapters/runtime_langgraph` es el único módulo con `import langgraph` y que `resultarai/core/routing` sigue sin frameworks; suite completa (`ruff check`, `mypy`, `pytest`) en verde; los 3 No-objetivos del proposal (sin skills reales, sin tools, sin API HTTP) verificados por inspección del diff. `[modelo: opus]`
