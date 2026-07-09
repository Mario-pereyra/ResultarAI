# Review final — c09-mcp-tools (tarea 5.1)

**Reviewer:** agente de revisión (modelo opus) · **Fecha:** 2026-07-09
**Alcance revisado:** `git diff 18319c6..HEAD` (6 commits, ~4.160 líneas, 38 archivos).
**Veredicto:** **APROBADO CON OBSERVACIONES** (observaciones menores, ninguna bloqueante).

---

## 1. Coherencia specs ↔ implementación ↔ tests

Cada `Requirement`/`Scenario` de los 3 delta specs tiene código y un test que prueba lo que
el escenario afirma (verificado contra el código real, no contra los reportes).

### `specs/mcp-tools/spec.md`

| Scenario | Código | Test | ✔/✘ |
|---|---|---|---|
| Conexión e initialize con negociación de capacidades | `session.py:257-272` (`__aenter__`→`initialize`+`ensure_tools_capability`), `:92-103` | `test_client_lifecycle.py:51-59` (server real stdio) + `:71-79` (capability ausente→`McpCapabilityError`) | ✔ |
| El cliente MCP no vive en core | import-linter `forbidden_modules` incluye `mcp` (`pyproject.toml:101`) | `uv run lint-imports` (KEPT, ver §8) | ✔ |
| Listado completo con paginación | `session.py:67-89` (`paginate_tool_descriptors` sigue `cursor`/`nextCursor`) | `test_client_discovery.py:28-44` (verifica `seen_cursors == [None, "page-2"]`) | ✔ |
| Descriptor sin inputSchema válido rechazado | `descriptors.py:52-61,89-91` (descarte silencioso si `type != "object"`/`None`) | `test_client_discovery.py:65-80` | ✔ |
| Invocación de lectura autorizada devuelve resultado tipado | `session.py:304-322`, `client.py:111-120` | `test_client_invocation.py:51-79` (content + `structured_content` validado por SDK) | ✔ |
| Argumentos que no cumplen el inputSchema no se envían | `session.py:214-235,320` (valida ANTES de `call_tool`) | `test_client_invocation.py:85-112` (spy sobre `session.call_tool` que falla si se emite) | ✔ |
| MCP Server local por stdio (`stderr` = logging) | `transports.py:83-91` | `test_transport_stdio.py:41-58` (round-trip) + `:84-113` (stderr a archivo, JSON-RPC intacto) | ✔ |
| MCP Server remoto por Streamable HTTP (session-id/protocol-version) | `transports.py:92-98` (SDK gestiona headers) | `test_transport_http.py:36-57` (server stateful uvicorn real; 2ª request prueba propagación de `Mcp-Session-Id`) | ✔ |
| Protocol Error de Tool desconocida | `session.py:161-184`, `client.py:121-126` (`McpError`→`ToolProtocolFailure`) | `test_client_errors.py:88-115` (fixture low-level real emite `-32602`) | ✔ |
| Tool Execution Error con feedback accionable | `session.py:187-211` (`isError:true`→`ToolExecutionFailure`, mensaje íntegro) | `test_client_errors.py:145-172,214-221` | ✔ |
| El server de ejemplo expone lectura y escritura simulada | `example_server/server.py:46-166` (echo/get_current_time/calculate/record_note) | `test_example_server.py:86-104` | ✔ |
| La escritura simulada no produce efecto real | `example_server/server.py:156-166` | `test_example_server.py:130-144` (marca "simulado/sin efecto real" + directorio intacto) | ✔ |

Nota fuerte a favor: `test_client_errors.py` documenta y prueba que FastMCP envuelve la Tool
desconocida en `isError:true` (no `-32602`), y usa un fixture de bajo nivel conforme a la spec
(`fixtures/protocol_error_server.py`) para ejercer el `-32602` genuino. Los dos mecanismos de
error quedan separados por **tipo** (`ToolCallOutcome`/`ToolExecutionFailure`/`ToolProtocolFailure`):
un `isError:true` es imposible de confundir con éxito por construcción.

### `specs/tool-registry-binding/spec.md`

| Scenario | Código | Test | ✔/✘ |
|---|---|---|---|
| Tool del server sin ToolManifest activo no existe | `binding.py:83-96` (`get_invocable`→`None`), `governed.py:171-181,205-250` | `test_binding.py:115-122` + `test_governed.py:94-116` (deny sin gate ni tools/call, 1 AuditEvent) | ✔ |
| Tool con ToolManifest activo sí es invocable | `binding.py:93-96` | `test_binding.py:124-128` | ✔ |
| El binding resuelve server y tool_name desde el manifiesto | `binding.py:65-80` (todo del manifiesto) | `test_binding.py:134-145` | ✔ |
| La clasificación no se puede cambiar en runtime | `tool.py:97,177` (`frozen=True` en submodelos y ToolManifest), `binding.py:55` | `test_binding.py:151-173` (reasignar `risk.operation_type`/`risk.level`/`binding.*`→`ValidationError`) | ✔ |
| Las annotations del server no alteran la clasificación | `binding.py:66-80` (nunca lee `annotations`), `descriptors.py:26-42` (solo informativas) | `test_binding.py:179-197` (`readOnlyHint` engañoso sobre write; sigue WRITE/CRITICAL) | ✔ |
| tool_name inexistente en el server invalida el binding | `binding.py:127-143,146-157` | `test_binding.py:208-215,227-236` (check puro + server real) | ✔ |
| Lectura permitida se ejecuta y se audita | `governed.py:198-203,279-315` | `test_governed.py:122-146` (allow + tools/call real + AuditEvent con `result_summary`) | ✔ |
| Lectura sin Policy que la permita se bloquea | `governed.py:198-201,269-277` | `test_governed.py:152-170` (deny-by-default, sin tools/call) | ✔ |
| Escritura escala a HITL siempre y no se ejecuta | `governed.py:195-196,252-267` (incondicional, antes del gate) | `test_governed.py:176-209` (con Policy que autoriza writes, igual escala; sin tools/call) | ✔ |
| La tool de lectura del server de ejemplo corre end-to-end | `governed.py` + `resolve_executable_toolset` | `test_governed.py:215-249` (usa `resolve_executable_toolset`, regla dura 3, contra server real) | ✔ |

### `specs/tool-call-visibility/spec.md`

| Scenario | Código | Test | ✔/✘ |
|---|---|---|---|
| Cada invocación produce un registro visible colapsable | `visibility.py:119-142` (`project_visible_tool_call`, `collapsed_by_default=True`) | `test_tool_call_visibility.py:43-69` | ✔ |
| Truncado del resultado con marca explícita | `visibility.py:104-116` (`… [truncado]`) | `test_tool_call_visibility.py:72-97` (además verifica AuditEvent origen frozen intacto) | ✔ |
| Funcional ve lenguaje simple | `visibility.py:157-166` (`parameters=None` para Funcional) | `test_tool_call_visibility_role.py:39-60` (no filtra valores crudos) | ✔ |
| Técnico y Admin ven parámetros completos | `visibility.py:166` | `test_tool_call_visibility_role.py:63-81` | ✔ |
| Escritura escalada se muestra en espera de aprobación | `visibility.py:27-51,147-148` (`escalate_hitl`→`PENDING_APPROVAL`) | `test_tool_call_visibility.py:114-130` + `_role.py:84-98` (nunca ejecutada en ningún rol) | ✔ |
| Lectura permitida se muestra como ejecutada | `visibility.py:47-49` | `test_tool_call_visibility.py:133-145` | ✔ |

**Ningún escenario queda sin test ni con test que pruebe algo distinto a lo declarado.**

---

## 2. Conformidad spec MCP 2025-11-25 ✔

- Pin `mcp==1.28.1` en `pyproject.toml:16`; el doc `compliance-mcp-2025-11-25.md` verifica
  `LATEST_PROTOCOL_VERSION == "2025-11-25"` y su presencia en `SUPPORTED_PROTOCOL_VERSIONS`.
- Lifecycle (`initialize`+capabilities+`notifications/initialized`): delegado al SDK vía
  `session.initialize()` (`session.py:264`), con exigencia adicional de capability `tools`.
- `tools/list` paginado, `tools/call` con `inputSchema`/`outputSchema`/`content`/
  `structuredContent`/`isError`, transports stdio y Streamable HTTP, modelo de error dual:
  todos presentes y probados (ver §1). La tabla de compliance mapea cada punto a la
  clase/módulo del SDK; **0 desvíos** declarados y confirmados.

---

## 3. Clasificación inmutable en runtime ✔

- `ToolManifest` con `model_config = ConfigDict(..., frozen=True)` (`tool.py:177`) y todos sus
  submodelos vía `_StrictSubModel` (`tool.py:97`). `ResolvedToolBinding` frozen (`binding.py:55`).
- El binding lee `operation_type`/`risk_level` **exclusivamente** del manifiesto
  (`binding.py:66-80`); las `annotations` del descriptor jamás entran a la gobernanza.
- No existe ningún camino de reclasificación en runtime: reasignar cualquiera de estos campos
  lanza `ValidationError` (probado en `test_binding.py:151-173`).

---

## 4. Toda invocación por Policy Gate + AuditEvent ✔ (con 1 observación menor)

Recorrido exhaustivo de `governed.py::invoke`: **cada** camino emite exactamente un `AuditEvent`
y **ninguno** emite `tools/call` sin `allow`:

| Camino | AuditEvent | ¿tools/call? |
|---|---|---|
| Tool inexistente (`_registry_miss`, `:205-250`) | 1 (`deny`, `tool_not_in_registry`) — sin gate | No |
| Escritura (`_write_escalates_to_hitl`, `:252-267`) | 1 (`escalate_hitl`) — incondicional, antes del gate | No |
| Lectura `deny`/`escalate` del gate (`_audit_without_execution`, `:269-277`) | 1 | No |
| Lectura `allow`, éxito o `ToolExecution`/`ToolProtocolFailure` (`:279-315`) | 1 (con `result_summary`) | Sí (solo aquí) |
| Lectura `allow`, fallo local del cliente antes de `tools/call` (`:303-306`) | 1 (`result_summary` = error) | No |

- Único emisor de `tools/call` en producción: `governed.py:302` → `client.execute`, alcanzable
  solo tras `decision.effect == "allow"` (`:198-203`). Defensa en profundidad: `client.execute`
  vuelve a rechazar toda decisión ≠ `allow` sin abrir sesión (`client.py:105-107`). No hay
  `session.call_tool` sin guardia en el código de producción (grep confirmado).
- Verificación "NO se emite tools/call": los tests usan un `_spy_resolver` que apunta a un
  comando inexistente; si el executor abriera sesión, fallaría al lanzar el subproceso
  (`test_governed.py:69-71,101,159,193`).

---

## 5. Cero lógica MCP en core/ ✔

- `grep -rn "import mcp|from mcp" resultarai/core/` → **sin imports del SDK** (solo menciones en
  docstrings, permitidas).
- import-linter: contrato "El nucleo no conoce el mundo exterior" con `mcp` en
  `forbidden_modules` (`pyproject.toml:101`). Resultado: **3 contratos KEPT, 0 broken**.

---

## 6. Reglas duras de CLAUDE.md ✔

- **1** (core sin frameworks): KEPT; `core/audit/visibility.py` y `core/manifests/tool.py` solo
  usan stdlib + Pydantic.
- **3** (tools solo vía skills): el e2e resuelve el toolset con `resolve_executable_toolset`
  antes de invocar (`test_governed.py:220-227`).
- **4** (deny-by-default + audit): deny-by-default en lectura (`test_governed.py:152-170`);
  escritura→`escalate_hitl` incondicional; toda decisión auditada.
- **6** (sin manifiesto no existe): `resolve_tool_binding` vía `get_invocable` (solo `active`).
- **9** (docs/comentarios español, código inglés): los 12 archivos nuevos de `adapters/tools_mcp`
  y `core/audit/visibility.py` cumplen (docstrings/comentarios en español, identificadores en
  inglés). Nota: los enum de rol usan los términos exactos del glosario (`admin`/`tecnico`/
  `funcional`, `visibility.py:54-64`).
- **5** (sin SQL libre): reforzada en el schema (`tool.py:134-143`), manifiestos de fábrica con
  `allow_sql_freeform: false`.

---

## 7. Coherencia tasks.md ✔

Las 17 tareas de implementación marcadas `[x]` (1.1–1.7, 2.1–2.4, 3.1–3.2, 4.1–4.4)
corresponden a trabajo presente en el diff (verificado archivo por archivo). Solo la 5.1
(este review) queda pendiente. Observación menor: la parte "1 lectura" de la tarea 4.3
(`example_echo.yaml` + `example_echo_eval.yaml`) **preexistía** de `a02-core-manifiestos`
(commit `6a21179`); el diff de c09 solo añade el manifiesto de escritura
(`example_record_note.yaml`) y su eval. Ambos manifiestos validan y pasan la validación cruzada
contra el server real (`test_binding.py:217-225`). Trabajo sustantivamente completo.

---

## 8. Los 5 comandos de calidad (corridos por el reviewer) — TODOS EN VERDE

| Comando | Resultado literal |
|---|---|
| `uv run pytest` | `338 passed, 1 warning in 25.37s` (1 warning = `DeprecationWarning` esperado de `streamablehttp_client` del SDK dentro de un fixture; el código de producción usa la variante no deprecada, `transports.py:40`) |
| `uv run ruff check .` | `All checks passed!` |
| `uv run ruff format --check .` | `152 files already formatted` |
| `uv run mypy resultarai tests` | `Success: no issues found in 152 source files` |
| `uv run lint-imports` | `Contracts: 3 kept, 0 broken.` |

---

## Hallazgos

Ningún defecto bloqueante. Observaciones (para decisión del orquestador):

1. **[LOW] `EndpointResolutionError` tras decisión `allow` no emite AuditEvent.**
   `governed.py:294-296`: si el `endpoint_resolver` no mapea el `endpoint_ref` del binding, el
   executor lanza `EndpointResolutionError` **después** de que el Policy Gate devolvió `allow`,
   sin emitir el `AuditEvent` de esa decisión. Estrictamente, es una decisión `allow` sin evento
   auditado. Mitigantes: (a) es un error de configuración interno (el `endpoint_resolver` lo
   construye `app/` y debería contener todo `endpoint_ref` de un manifiesto activo); (b) no se
   emite `tools/call` ni hay efecto lateral no auditado — falla ruidosamente antes de ejecutar;
   (c) inalcanzable con los manifiestos de fábrica. **Sin test** para este camino. Sugerencia
   (no bloqueante): emitir un `AuditEvent` (p. ej. `deny`/error de configuración) antes de
   lanzar, o cubrirlo con un test que fije el comportamiento esperado.

2. **[COSMÉTICO] Números desactualizados en `compliance-mcp-2025-11-25.md`.**
   La tabla "Estado de la verificación" (líneas 56-60) reporta `274 passed` y `124 files`, escrita
   en la tarea 1.1 (primer commit). El estado final real es `338 passed` / `152 files`. Los
   comandos siguen en verde; solo confunde a un lector. Sugerencia: actualizar o anotar que son
   cifras del momento de la tarea 1.1.

3. **[INFORMATIVO] La garantía de auditoría vive en el executor, no en el cliente.**
   `McpToolClient.execute` y `McpToolSession.call_tool` son públicos y confían en la
   `PolicyDecision` recibida (el cliente solo garantiza "nunca `tools/call` sin `allow`"). Un
   llamador que construyera a mano `PolicyDecision(effect="allow")` y llamara al cliente
   directamente saltaría el binding del registro + gate + AuditEvent del `GovernedToolExecutor`.
   Es el diseño documentado (Decision 4 del `design.md`): el flujo gobernado es el único punto de
   entrada previsto y el cliente es el adapter del `ToolPort`. No es una violación de la spec (el
   requirement se cumple por el flujo gobernado), pero conviene que quien extienda el código sepa
   que la autorización/auditoría no la impone el cliente por sí solo.
