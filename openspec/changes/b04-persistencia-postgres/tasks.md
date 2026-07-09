# Tasks — b04-persistencia-postgres

## 1. Fundación de persistencia (Alembic y conexión)

- [ ] 1.1 Añadir al grupo de dependencias del adapter (`pyproject.toml`): SQLAlchemy, Alembic, driver Postgres (psycopg) y librería UUIDv7; declarar el servicio Postgres en el `docker compose` de desarrollo/CI. Verificación: `uv sync` termina sin errores y `docker compose up postgres` levanta la base. `[modelo: haiku]`
- [ ] 1.2 Inicializar el entorno Alembic dentro de `adapters/persistence_postgres/` (`env.py`, `naming_convention` de constraints para diffs/downgrades limpios, rol de migración vs. rol de aplicación). Verificación: `alembic upgrade head` sobre una base vacía crea `alembic_version` sin errores. `[modelo: haiku]`
- [ ] 1.3 Configurar la conexión y la sesión SQLAlchemy con transacciones explícitas, sin fugar el motor hacia `core/`. Verificación: `uv run lint-imports` en verde (contratos de frontera e independencia de adapters de `a01`) y test de humo de conexión. `[modelo: sonnet]`

## 2. Sesiones, mensajes y ramas (conversation-persistence)

- [ ] 2.1 Definir el modelo de datos de `sessions` y `messages` (clave UUIDv7, `parent_id`, `model_profile` a nivel de sesión, índices por `session_id`/`parent_id`) según decisiones 3–5 del design. Verificación: cubre los escenarios "La sesión sobrevive a un reinicio" y "Los mensajes se ordenan por clave" de la spec. `[modelo: opus]`
- [ ] 2.2 Definir las invariantes append-only de mensajes (inmutabilidad de contenido) y de stickiness (`model_profile` del mensaje igual al de su sesión) como constraints/triggers. Verificación: cubre "Se rechaza mutar el contenido de un mensaje" y "Se rechaza un mensaje con perfil de modelo distinto". `[modelo: opus]`
- [ ] 2.3 Definir el marcador de compactación inmutable en frontera de turno (a lo sumo uno por rama). Verificación: cubre "La compactación se registra una sola vez". `[modelo: opus]`
- [ ] 2.4 Escribir la migración Alembic de estas tablas (autogenerada y **revisada a mano**) y los tests de invariante contra un Postgres real (rama nueva no reescribe historia; stickiness; compactación única). Verificación: `alembic upgrade head`/`downgrade` reversibles y tests en verde. `[modelo: sonnet]`

## 3. Adjuntos (attachment-storage)

- [ ] 3.1 Definir el schema de `attachments` conforme al ANEXO §5 (uuid, `sha256`, `status` como enum cerrado, `scan_result` jsonb, `storage_path`, refs de sesión/mensaje nullable). Verificación: cubre "persiste todos los campos del ANEXO §5" y "Se rechaza un status fuera del conjunto permitido". `[modelo: opus]`
- [ ] 3.2 Definir `extractions` (`full_text`, `extractor_version`) y la inserción `message_attachments` (`inserted_text` inmutable, `token_count`, `truncated`), más la invariante de dedup `(tenant, sha256)` (decisiones 4 y 6 del design). Verificación: cubre "Se rechaza mutar inserted_text", "Una rama reutiliza inserted_text byte-idéntica" y los escenarios de dedup. `[modelo: opus]`
- [ ] 3.3 Escribir la migración Alembic del schema de adjuntos (revisada a mano) y los tests de invariante contra Postgres real (inmutabilidad de `inserted_text`, dedup, retención que preserva `inserted_text`). Verificación: `alembic upgrade head`/`downgrade` reversibles y cubre "Purgar el binario preserva la sesión". `[modelo: sonnet]`

## 4. Audit log persistido (audit-persistence)

- [ ] 4.1 Definir el schema `audit_log` que persiste el contrato `AuditEvent` de `a03` (clave UUIDv7, campos de `docs/06`, parámetros resumidos/enmascarados). Verificación: cubre "Cada decisión del Policy Gate deja un evento" y "Los parámetros sensibles se persisten enmascarados". `[modelo: opus]`
- [ ] 4.2 Definir el enforcement físico append-only del `audit_log`: REVOKE de grants UPDATE/DELETE al rol de aplicación + triggers `BEFORE UPDATE OR DELETE` que hacen `RAISE EXCEPTION` (decisiones 1–2 del design). Verificación: cubre "La base rechaza un UPDATE", "La base rechaza un DELETE" y "La corrección es un evento nuevo". `[modelo: opus]`
- [ ] 4.3 Implementar la consulta del `audit_log` por filtros (usuario, tenant, agente, skill, tool, rango temporal, decisión, `trace_id`). Verificación: cubre "Consulta por usuario y rango temporal" y "Reconstrucción por trace_id". `[modelo: sonnet]`
- [ ] 4.4 Escribir la migración Alembic (schema + triggers/grants vía `op.execute`, `downgrade` reversible) y los tests de invariante contra Postgres real (UPDATE/DELETE rechazados por la base). Verificación: `alembic upgrade head`/`downgrade` reversibles y tests de inmutabilidad en verde. `[modelo: sonnet]`

## 5. Adapter StatePort y contract test

- [ ] 5.1 Implementar el adapter `persistence_postgres` que satisface `StatePort` de `a03` sobre los repositorios de sesiones/mensajes/adjuntos/audit, con transacciones explícitas y sin importar otros adapters ni frameworks en `core/`. Verificación: `uv run lint-imports` y `uv run mypy` en verde. `[modelo: sonnet]`
- [ ] 5.2 Escribir el contract test de `StatePort` en `tests/contracts/` contra un Postgres real (persistir y recuperar sesión, rama, adjunto y evento de auditoría). Verificación: contract test en verde. `[modelo: sonnet]`
- [ ] 5.3 Añadir el servicio Postgres efímero al workflow de CI para los tests de contrato e invariante. Verificación: el job de CI corre los tests contra Postgres y queda en verde. `[modelo: haiku]`

## 6. Cierre

- [ ] 6.1 Review final del change: invariantes físicas verificadas por tests (append-only de `audit_log`, branch-never-rewrite, `inserted_text` inmutable, stickiness), frontera de dependencia intacta (`core/` sin Postgres), schema del ANEXO §5 completo y migraciones reversibles. Verificación: checklist del reviewer en el PR. `[modelo: opus]`
