# Orquestador de implementación — ResultarAI (continuación: d11 §3 → e24)

> **Uso:** en una sesión nueva de Claude Code sobre la raíz de este repo, escribe:
> `Lee PROMPT-CONTINUACION.md y actúa según sus instrucciones.`

---

## Tu rol

Eres el **orquestador** de la implementación de ResultarAI. Vienes de sesiones anteriores que completaron e implementaron los changes **a01 → d10** (todos archivados) y las **secciones 1 y 2 de d11-identidad-acceso**. Tu trabajo: terminar `d11` (desde la **sección 3** de su `tasks.md`) y continuar el roadmap en orden hasta `e24-despliegue-operacion`.

**NO implementes `e25-evals-gates`** (lo ejecuta el product owner; los gates de d20/d21 operan en modo placeholder).

Tú no escribes el grueso del código: **delegas cada tarea a un subagente** (herramienta Agent) con el modelo de su tag `[modelo: haiku|sonnet|opus]`, usando la skill **`/asignar-modelo`** para ratificar el escalón antes de cada delegación. Verificas el resultado, integras, corres la suite, commiteas por sección y pusheas. Trabaja de forma autónoma.

## Estado actual del repo (verificado 2026-07-09)

- **Rama:** `claude/prompt-implementacion-st0jn9` (push directo a esa rama en origin).
- **Suites en verde:** Python `uv run pytest` → **390 passed**; frontend (`cd frontend`) → **321 tests**, lint/typecheck/build/audit:colors/audit:strings/check:contrast OK. CI de GitHub Actions en verde (6 jobs: 5 Python + frontend).
- **Archivados:** a01, a02, a03, b04, b05, b06, b07, c08, **c09-mcp-tools**, **d10-design-system-shell** (specs sincronizadas en `openspec/specs/`).
- **d11-identidad-acceso EN CURSO**: secciones 1 y 2 completas y pusheadas (`c3db9cf`, `e2f63b6`); checkboxes 1.1–1.7 y 2.1–2.6 marcados en su `tasks.md`. **Siguiente: sección 3.**
- Docker Postgres de tests corriendo (`resultarai_postgres`); Node 22 + npm para `frontend/`.

## Lo ya construido de d11 (NO lo rehagas — constrúyele encima)

**Sección 1 — modelo de datos** (`resultarai/adapters/persistence_postgres/models.py` + migración `724789ea8df4`):
`users` (role/status con CHECK, username CITEXT único, must_change_password, preferred_language/theme, totp_required), `auth_sessions` (id = **SHA-256 hex del token**, doble expiración, índices), `totp_secrets` (secreto **cifrado**, jamás plano), `totp_backup_codes` (hash Argon2id, used_at), `login_attempts` (account_ref normalizado), `groups`/`group_members` (única fuente de membresía; users.group_id NO existe), `usage_agreement_versions` (version_number monotónico)/`usage_agreement_acceptances`, `identity_audit_events` (**append-only por trigger**, contrato id/event_type/actor_user_id/target_ref/timestamp/details JSONB).

**Sección 2 — núcleo de seguridad** (`resultarai/app/identity/`, 35 tests en `tests/app/identity/`):
- `passwords.py`: `hash_password`/`verify_password`/`needs_rehash` (Argon2id), `validate_password_policy` (≥12 chars, 4 clases), `generate_temporary_password`.
- `sessions.py`: `create_session`/`validate_session`/`revoke_session`/`revoke_all_sessions`, `SessionConfig.from_env()`, `SESSION_COOKIE`, `set_session_cookie`/`clear_session_cookie` (Secure/HttpOnly/SameSite=Lax). Token firmado con itsdangerous; en DB solo SHA-256.
- `dependency.py`: `get_current_user` (userId SOLO de la cookie de sesión), `require_admin`, proveedores inyectables `get_db`/`get_session_config` (se sobreescriben con `app.dependency_overrides`).
- `rate_limit.py`: `record_failed_attempt`/`is_account_locked`/`account_lock_status`/`clear_attempts`, `RateLimitConfig.from_env()` (`IDENTITY_LOGIN_MAX_ATTEMPTS`, `IDENTITY_LOGIN_WINDOW_SECONDS`), constante `ACCOUNT_LOCKED`.
- `totp.py`: `enroll` (secreto cifrado Fernet con `IDENTITY_TOTP_ENCRYPTION_KEY`), `verify_code`, `generate_backup_codes`/`verify_backup_code` (un solo uso).
- `csrf.py`: `issue_csrf_token`/`verify_csrf`/`require_csrf`, `CSRF_COOKIE`, `CSRF_HEADER`, `set_csrf_cookie`.

**Convención obligatoria:** ruff B008 prohíbe `Depends(...)` como default → usa `Annotated[T, Depends(...)]` (patrón ya presente en `dependency.py`).

**Decisiones ya tomadas (BACKLOG-DESCUBRIMIENTOS.md las registra — no las reabras):**
- Tabla de sesiones de identidad = `auth_sessions` (colisión con `sessions` de conversaciones de b04).
- Auditoría de identidad = tabla propia `identity_audit_events` (el `audit_logs` de b04 es Policy-Gate-shaped).
- ADR-0008 §4 ("ports en core") NO aplica: identity vive en `app/identity` sin tocar `core/` (design d11 Decision 10 manda).
- Sugerencia validada para 3.1/3.2: cuando el login exige TOTP, NO crear sesión aún — devolver token firmado corto ("pending_totp", itsdangerous, ~5 min) y crear la sesión recién tras `POST /api/auth/totp/verify`.

## Metodología por change (idéntica a las sesiones anteriores)

1. `openspec/changes/<change>/`: lee proposal.md, design.md, specs/ y tasks.md COMPLETOS antes de delegar.
2. Ejecuta las tareas **en orden por sección**. Por cada sección (o grupo coherente):
   - Invoca `/asignar-modelo` y delega a un subagente con `model` = el tag de la tarea. Prompt del subagente AUTOCONTENIDO: tarea textual, scenarios de la spec que cubre, archivos a leer (lista explícita), reglas duras pertinentes, verificación exacta. El subagente NO commitea.
   - Tareas independientes pueden ir en agentes paralelos SOLO con conjuntos de archivos disjuntos (decláralos "TUS archivos / PROHIBIDO tocar"). Nunca dos `npm run build` o dos agentes sobre el mismo archivo a la vez.
   - Si un subagente falla 2 veces → sube un escalón (haiku→sonnet→opus); si opus falla, hazlo tú. Si un agente muere a medias, evalúa su trabajo en disco ANTES de relanzar (git status + correr la suite) — suele estar casi completo y solo faltan lint/format.
3. Verifica TÚ tras cada sección: `uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy resultarai tests && uv run lint-imports` (+ en frontend: `npm run lint && npm run typecheck && npm run test && npm run audit:colors && npm run audit:strings && npm run check:contrast && npm run build`). Revisa exit codes REALES (`set -o pipefail`; un `| tail` puede enmascarar fallos).
4. Marca los checkboxes `[x]` en tasks.md, **commit por sección** (convención `feat|test|docs|chore(<scope>): descripción (Sección N)` en español, cuerpo con bullets) y **push inmediato**.
5. Al completar todas las tareas: review final con subagente **opus** sobre el diff completo del change (checklist en `review-final.md` dentro del change; escéptico: scenario→test contra código real). Cierra los hallazgos LOW tú mismo; los diferidos van a `openspec/BACKLOG-DESCUBRIMIENTOS.md`.
6. `openspec archive <change> --yes --json` → commit `chore(openspec): archivar cambio <change> y sincronizar especificaciones` → push → actualiza la línea "Etapa activa" de CLAUDE.md → siguiente change.

## Reglas duras (además de las 9 de CLAUDE.md)

- **Alcance = las specs del change.** Descubrimientos → `openspec/BACKLOG-DESCUBRIMIENTOS.md`, no los implementes.
- Nunca debilites un requirement o test para que pase; si un scenario es incumplible, deténte y explica.
- Open Questions ya decididas: **b06** compaction una vez POR SESIÓN; **d16** costo visible para rol Funcional (vista 23 manda).
- Huecos que van al BACKLOG (no resolver): CRUD de definiciones de cuota (d19, vista 33) y UI admin de backups/retención (vista 39 §6).
- Pausa y pregunta al usuario SOLO ante bloqueos reales (credenciales, permisos, decisión de producto).

## Instrucciones inmediatas — d11 desde la sección 3

1. Lee `CLAUDE.md`, `openspec/changes/d11-identidad-acceso/{design.md,tasks.md}` y los 3 specs (`authentication`, `user-management`, `usage-agreement`).
2. Lee la API real de `resultarai/app/identity/` y los modelos de `persistence_postgres/models.py` (lo listado arriba).
3. **Secciones 3–6** (todas `[modelo: sonnet]`, un solo agente o dos secuenciales): casos de uso + routers FastAPI en `resultarai/app/api/` (con `create_app()`), endpoints de auth (login con rate limit y error genérico anti-enumeración con dummy hash, totp/verify con pending_totp, logout, password, TOTP personal, wizard retomable), admin (alta con temporal de un solo uso, suspend, role —bloqueado para uno mismo—, reset, sessions/revoke, require-totp, grupos, `GET /api/admin/users` lista mínima para la UI, todo con require_admin+require_csrf y 403 para no-admin), acuerdo (status/accept/publicar versión/guard `AGREEMENT_PENDING` reutilizable), y auditoría: **exactamente un `IdentityAuditEvent` por mutación** (event_type tipo "user.created", "agreement.accepted"). Tests de contrato con TestClient + Postgres real (patrón de `tests/app/identity/conftest.py`), cubriendo cada scenario de las specs de esas secciones.
4. **Secciones 7–8** (UI, sonnet + haiku para i18n): vistas `01-login` y `02-primer-acceso` (wizard 3 pasos, checkbox bloqueante del acuerdo) y consola admin de alta (modales crear usuario/grupo con contraseña temporal mostrada UNA vez, lista mínima con acciones). Reusa los componentes de `frontend/components/ui/` y el shell de d10; textos SIEMPRE en `messages/es.json` (voseo); las auditorías `audit:colors`/`audit:strings` de CI deben seguir en verde. El frontend habla con el backend vía fetch a `/api/*` (configura rewrite de Next a `BACKEND_URL` en dev y mockea fetch en los tests de Vitest).
5. **Secciones 9–10** (opus): tests de seguridad explícitos (fuerza bruta→ACCOUNT_LOCKED y liberación por ambas vías; sesión revocada/expirada→401 en TODO endpoint autenticado; userId ajeno ignorado en un endpoint por sección; atributos de cookie y rechazo sin CSRF), glosario (10.1: términos nuevos + `identity_audit_log`→documenta `identity_audit_events` como término propio), CLAUDE.md (10.2), review final opus (10.3) y archivado.
6. Después de d11: continúa el roadmap en orden — d12-notificaciones, d13-chat-conversacion, d14-attachments, d15-catalogo-agentes, d16-cuotas-liberaciones, d17-hitl-aprobaciones, d18-mi-espacio, d19-admin-operacion, d20-gobernanza-plataforma, d21-builders, e22-workflows-deterministas, e23-memoria-usuario, e24-despliegue-operacion. (`e25` NO.)

## Resiliencia

El progreso vive en los checkboxes de tasks.md y en los commits pusheados: antes de repetir trabajo, verifica `git log --oneline -15`, `git status` y los checkboxes del change activo. Si hay archivos sin commitear de un agente cortado, corre la suite para evaluar si el trabajo está completo antes de relanzar nada.

## Hecho cuando

Los 24 changes (hasta e24) archivados, `openspec/specs/` refleja lo construido, suites Python+frontend y CI en verde, y `e24` pasa su smoke E2E. `e25-evals-gates` queda intacto como único change activo.
