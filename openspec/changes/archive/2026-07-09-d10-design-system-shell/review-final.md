# Review final — d10-design-system-shell (tarea 8.2)

**Reviewer:** verificación independiente contra el código real (no contra reportes de implementadores).
**Diff revisado:** `d71c80b..HEAD` (9 commits, 102 archivos, +18.947/-34).
**Fecha:** 2026-07-09.

## Veredicto

**APROBADO CON OBSERVACIONES** — todas las observaciones son de severidad BAJA o informativas; ninguna bloquea el archive. Los 8 comandos de verificación y la suite Python dan exit 0, CI en `success`, el portado de tokens es verbatim salvo el único desvío autorizado, y los 31 escenarios de `specs/` están cubiertos por código + test/script.

---

## 1. Resultado literal de los comandos (corridos por el reviewer desde `frontend/`)

| Comando | Resultado | Exit |
|---|---|---|
| `npm run lint` | eslint sin hallazgos | 0 |
| `npm run typecheck` | `tsc --noEmit` limpio | 0 |
| `npm run test` | **29 archivos, 320 tests passed** | 0 |
| `npm run audit:colors` | "sin coincidencias. Todos los componentes consumen tokens semánticos." | 0 |
| `npm run audit:strings` | "sin coincidencias en app/ ni components/shell/." | 0 |
| `npm run check:contrast` | "40 pares… Todos los pares cumplen el umbral AA en los 4 sets." | 0 |
| `npm run build` | Next 16.2.10, compiló OK, rutas `/`, `/api/theme`, `/styleguide` | 0 |
| `uv run pytest -q` (repo) | **339 passed, 1 warning** (esperado) | 0 |
| `gh run list` (rama) | última corrida `CI` → **completed / success** | — |

---

## 2. Solo tokens semánticos (sin hex hardcodeado)

- ✔ `npm run audit:colors` en verde; el script (`scripts/check-hardcoded-colors.mjs`) busca `#hex`/`rgb()`/`rgba()` fuera de la capa de tokens.
- ✔ Revisión manual: los componentes (`styles/components/*.css`, `styles/shell.css`) referencian solo `var(--token)`, `currentColor` o `color-mix(... var(--token) ...)`.
- ✔ Desviaciones de literal justificadas y **documentadas en código**: `.notif-bell__count` y `.shell-sidebar__badge` evitan el blanco puro del mockup en tema claro resolviéndolo vía `var(--danger-ink)` (`styles/shell.css:11-18`) — mantienen el rol semántico sin introducir literal.
- ✔ `.toast__close` (`styles/components/toast.css:39-55`) es una adición del componente React (cierre manual, no existe en el mockup estático) y usa solo tokens.

## 3. Consistencia con `design/` (muestreo de 5 clases portadas)

Comparación byte a byte frontend ↔ `design/mockups/tokens.css`:

| Clase | Fuente design | Frontend | Resultado |
|---|---|---|---|
| `.btn` (+variantes/estados/spinner) | §5.2 | `styles/components/button.css` | ✔ verbatim |
| `.overlay`/`.modal` | §5.18 | `styles/components/modal.css` | ✔ verbatim |
| `.ai-banner` | §5.25 (líneas 1039-1051) | `styles/shell.css:60-72` | ✔ verbatim |
| `.toast-stack`/`.toast` | §5.10 | `styles/components/toast.css` | ✔ verbatim (core idéntico) |
| 4 sets de tokens color (76 valores) | §3.1-3.4 | `styles/tokens.css:106-223` | ✔ solo 2 desvíos autorizados |

**Comparación sistemática de los 4 sets de tokens** (script ad-hoc que extrae `--token: valor` de ambos archivos): de ~76 declaraciones de color, **exactamente 2 difieren, y son las autorizadas**:

- `light·default --ink-faint`: `#6e7787` → `#6d7686`
- `dark·totvs --ink-faint`: `#74879b` → `#7a8da1`

Ningún otro desvío silencioso. ✔

- ✔ Ambas anotaciones existen y son coherentes: `frontend/styles/tokens.css:145-147` y `:175-177` (desvío consciente, ratio real) + `openspec/BACKLOG-DESCUBRIMIENTOS.md:19` (mockup 4.44:1/4.48:1 real bajo el declarado, ajuste a 4.505:1/4.852:1, `design/` prohibido de tocar).

## 4. Matriz de capacidades (`lib/capabilities.ts` ↔ tabla "Diferencias por rol", Vista 3)

Fila por fila contra `design/VISTAS/01-acceso-shell.md:208-215`:

| Fila del design | capabilities.ts | Resultado |
|---|---|---|
| Catálogo·Chat·Workflows·Aprobaciones·Mi espacio → ✅ ✅ ✅ | `BASE_SECTIONS` para los 3 roles | ✔ |
| Administración·Construcción → — — ✅ | solo `admin` agrega `administracion`,`construccion` | ✔ |
| Badge de rol → FUNCIONAL/TÉCNICO/ADMIN | `RoleBadge` + `roles` en es.json | ✔ |

- ✔ Test `lib/capabilities.test.ts` recorre los 3 roles con valores escritos a mano (no derivados de la constante → un cambio accidental rompe el test).
- ⚠ Ver Hallazgo 4: filas "Taxímetro" y "Dot gateway + perfil LLM" (topbar, no sidebar) no se renderizan; fuera de la matriz `Section[]` y de los scenarios de este change.

## 5. i18n

- ✔ `npm run audit:strings` verde; alcance `app/` + `components/shell/` (excluye `components/ui/**` con justificación: reciben texto por props). Grep manual sobre `components/ui/*.tsx` no halló español hardcodeado. ✔
- ✔ Voseo: `messages/es.catalog.test.ts` recorre TODAS las hojas del catálogo contra una denylist de tuteo/usted (heurística documentada, no exhaustiva).
- ✔ ICU: `Shell.topbar.notificationsAriaLabel` y `Shell.sidebar.approvalsAriaLabel` usan `{count, plural, =0/one/other}` (es.json:32,43; test las verifica).
- ✔ Placeholders nombrados: `userMenuLabel: "…{name}, rol {role}"` (es.json:44), sin concatenación.
- ✔ Formatos es-BO: `lib/format-bo.ts` vía `Intl.*`; `format-bo.test.ts` asevera `11/06/2026 14:32` (dd/mm/aaaa HH:mm 24h).

## 6. Cobertura specs ↔ implementación (31 escenarios)

> Nota: el enunciado de 8.2 dice "24 escenarios"; el conteo real de `specs/` es **31** (design-system 13 + app-shell 12 + i18n 6). Los 31 están cubiertos.

### design-system (13/13)
| Escenario | Evidencia | ✔ |
|---|---|---|
| Los 4 sets están completos | `styles/tokens.css:106-223` + comparación sistemática | ✔ |
| dark·default es el default | `styles/tokens.css:107-108` (`:root` = dark·default) | ✔ |
| Escala de espaciado completa | `tokens.css:63-95` (`--sp-1..10`, radios, dur, z) | ✔ |
| Breakpoints 380/768/1200 | `tokens.css:97-101` + `@media 768px` en componentes | ✔ |
| Columna numérica alineada | `tokens.css:240-242` `.mono`/`.num` tabular-nums | ✔ |
| Auditoría sin hex | `audit:colors` verde | ✔ |
| Agregar brand no toca componentes | componentes solo `var(--token)` | ✔ |
| Botón loading | `button.test.tsx:60-66` (aria-busy, texto conservado) | ✔ |
| Modal trampa de foco | `modal.test.tsx:26-57` (Tab cicla ambos sentidos) | ✔ |
| Tabla densa mono | `table.test.tsx:15-39` (`table--dense` + `.num`) | ✔ |
| Contraste automatizado | `check-contrast.ts` 10 pares×4 sets = 40, todos AA | ✔ |
| Foco visible | `styles/focus-visible.test.ts` (regla por selector + allowlist de `outline:none`) | ✔ |
| Styleguide 4 sets | `styleguide-content.test.tsx:36-62` (Set de las 4 combos) | ✔ |

### app-shell (12/12)
| Escenario | Evidencia | ✔ |
|---|---|---|
| Layout de escritorio | `shell.css` sidebar 240 / topbar 56; banner ~28 padding-driven; estructura en `shell-frame.test` | ◑ (ver Hallazgo 2) |
| Sidebar colapsable persistente | `shell-frame.tsx:38-72` localStorage round-trip | ◑ (ver Hallazgo 1) |
| Banner sin acción de cierre | `ai-banner.tsx` (sin botón/handler) | ✔ |
| Banner se acorta en móvil | `ai-banner.tsx` full+short + `shell.css:477-485` `@media` | ✔ |
| Rol Funcional no ve Admin | `sidebar.test.tsx:57-69` (`queryByText…toBeNull`) | ✔ |
| Rol Admin ve todo | `sidebar.test.tsx:71-82` | ✔ |
| Badge de rol en menú | `topbar.tsx:150` + `role-badge.test.tsx` | ✔ |
| Alternar tema persiste | `api/theme/route.test.ts` (toggle + maxAge 1 año) | ✔ |
| Gateway caído no bloquea | `shell-frame.test.tsx:90-107` | ✔ |
| Redacción por rol | `gateway-error.test.tsx:19-40` (3 roles) | ✔ |
| Skip-link primer foco | `shell-frame.test.tsx:115-124` | ✔ |
| Drawer trampa de foco móvil | `sidebar.test.tsx:94-109` (aria-modal + 15 Tab) | ✔ |

### i18n-foundation (6/6)
| Escenario | Evidencia | ✔ |
|---|---|---|
| Auditoría de strings | `audit:strings` verde | ✔ |
| Textos en voseo | `es.catalog.test.ts:69-81` | ✔ |
| Botón +25% no rompe | `styles/text-expansion.test.ts` + `sidebar.test.tsx:151-175` | ✔ |
| Placeholder nombrado | `es.json:44` `{name}/{role}` | ✔ |
| Contador ICU | `es.catalog.test.ts:83-90` | ✔ |
| Fecha es-BO | `format-bo.test.ts:20-26` | ✔ |

## 7. tasks.md

- ✔ Todas las tareas `[x]` corresponden a trabajo real del diff (scaffold, CI, tokens, 11 componentes, shell, i18n, contraste, styleguide, CLAUDE.md/README).
- ⚠ El enunciado dice "27 tareas"; el conteo real es **33 tareas `[x]`** de 34 (solo 8.2 sin marcar). La cifra 27 del enunciado es inexacta; la sustancia (todo lo marcado = trabajo real) se cumple.

## 8. Contratos temporales

- ✔ `SessionContext` documentado como reemplazable por **d11** en código (`lib/session-context.tsx`, `shell-frame`) + `frontend/README.md` + `design.md` Decisión 6 y Risk 2.
- ✔ `capabilities.ts` documentado como reemplazable por **d20** (`lib/capabilities.ts:5-14` + `design.md` Decisión 7). Riesgo "mock queda pegado" señalado en `design.md` Risks.

---

## Hallazgos

**H1 — BAJA · cobertura de test.** El escenario "Sidebar colapsable persistente" está *implementado* (`shell-frame.tsx:38-72`, localStorage read post-montaje + write on toggle) pero **ningún test asevera el round-trip de persistencia** (escribir → recargar → restaurar). Los tests solo cubren el toggle (callback + `aria-pressed` en `sidebar.test.tsx`) y limpian localStorage en `beforeEach`. Recomendación (no bloqueante): agregar un test que monte con `localStorage` pre-sembrado y verifique que arranca colapsado.

**H2 — INFO/BAJA · límite de jsdom.** El escenario "Layout de escritorio" cita banner 28px / sidebar 240px / topbar 56px. `shell.css` lleva 240px y 56px; el banner es padding-driven (28px es la altura resultante del portado verbatim, no un literal). No hay aserción runtime de las dimensiones px (jsdom no calcula layout); se cubre estructuralmente (`shell-frame.test`) y visualmente en `/styleguide`. Aceptable.

**H3 — INFO · discrepancias numéricas del enunciado.** El enunciado de 8.2 dice "24 escenarios" (real: **31**) y "27 tareas [x]" (real: **33**). Todo el trabajo real está cubierto; solo se corrige la cifra para trazabilidad.

**H4 — BAJA · consistencia con design/.** El topbar no renderiza el **dot de gateway + perfil LLM** (admin-only) ni el **taxímetro** (técnico/admin) que la tabla "Diferencias por rol" de Vista 3 lista. Ambos dependen de telemetría/chat de changes posteriores (d12/d13) y **no aparecen en ningún scenario de las specs de este change**, por lo que no hay incumplimiento de spec. Sin embargo, esta omisión respecto de la tabla completa del design **no está listada explícitamente** en los Non-Goals de `design.md`. Recomendación (no bloqueante): anotar la diferimiento en `design.md` o el README.

**H5 — BAJA · nombre de test más amplio que su aserción.** `sidebar.test.tsx:111` "Esc cierra el drawer y devuelve el foco al disparador" solo asevera que `onCloseDrawer` fue llamado; **no** verifica el retorno de foco. El retorno de foco lo provee `useFocusTrap`, cuyo comportamiento sí está aseverado en `modal.test.tsx:59-71` (mismo hook). Riesgo real bajo; recomendación: acotar el título o agregar la aserción de foco.

**H6 — INFO · inconsistencia aguas arriba en design/.** En `dark·totvs`, el comentario inline del mockup declara `--ink-faint … 5.1:1` mientras `frontend/tokens.css` y el BACKLOG refieren "4.8 declarado en DESIGN-SYSTEM.md §5.3". Es una inconsistencia *dentro de* `design/` (fuente de verdad), fuera del alcance de este change (prohibido tocar `design/`); ya está registrada como pendiente en `BACKLOG-DESCUBRIMIENTOS.md`.

---

## Checklist del reviewer

- ✔ Componentes usan solo tokens semánticos (audit:colors + revisión manual).
- ✔ 31/31 escenarios de `specs/` cubiertos por código + test/script (2 con matiz: H1 sin test de round-trip, H2 límite jsdom).
- ✔ CI en verde (última corrida `success`).
- ✔ Suite Python intacta (339 passed).
- ✔ Consistencia con `design/`: portado verbatim, único desvío autorizado confirmado y solo ese.
- ✔ Contratos temporales documentados (d11/d20).
- ◑ Observaciones menores H1-H6 (ninguna bloqueante).
