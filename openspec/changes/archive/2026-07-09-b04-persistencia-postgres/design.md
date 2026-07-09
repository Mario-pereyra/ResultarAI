# Design — b04-persistencia-postgres

## Context

`a03-core-gobernanza` entrega `StatePort` (Protocol) y el contrato `AuditEvent` como dominio puro en `core/`, sin persistencia. Este change los implementa contra Postgres en `adapters/persistence_postgres/` ([docs/05](../../../docs/05-estructura-y-convenciones.md): `StatePort → Postgres (estado, audit log)`) y añade Alembic. El reto no es CRUD: es codificar como **invariantes físicas de la base** dos garantías que el resto del producto asume dadas — branch-never-rewrite ([design/FUNCIONALIDADES.md](../../../design/FUNCIONALIDADES.md) §14) y el Audit Log append-only e inmutable ([docs/06](../../../docs/06-seguridad-gobernanza.md)) — y el schema de adjuntos del [ANEXO §5](../../../design/ANEXO-ATTACHMENTS.md). Constraint dura: `core/` no conoce Postgres; el adapter traduce y no decide (regla de dependencia, verificada por import-linter en `a01`).

## Goals / Non-Goals

**Goals:**

- Adapter Postgres detrás de `StatePort` con transacciones explícitas y sin fugas del motor hacia `core/`.
- Modelo de sesiones/mensajes con ramas (`parent_id`), stickiness de `model_profile`, marcador de compactación y adjuntos, con append-only garantizado por la base.
- `audit_log` append-only con enforcement físico (grants + triggers) y consulta por filtros.
- Schema de adjuntos del ANEXO §5 (attachments + extraction + inserción por mensaje), listo para que `d14` escriba en él.
- Alembic con migraciones reversibles revisadas a mano.

**Non-Goals:**

- Pipeline de extracción (`d14`), API de chat (`d13`), cuotas (`d16`), runtime de grafos (`b06`), job operativo de purga por retención (se habilita en `e24`, aquí solo el schema lo soporta).

## Decisions

1. **Enforcement físico de inmutabilidad en dos capas.** `audit_log` (y las filas/columnas append-only de mensajes e `inserted_text`) se protegen con (a) **revocación de grants** UPDATE/DELETE al rol de aplicación y (b) **triggers `BEFORE UPDATE OR DELETE` que hacen `RAISE EXCEPTION`**. Defensa en profundidad: si una migración futura reotorga un grant por error, el trigger sigue frenando la mutación; y el trigger documenta la intención en el propio schema. Alternativa descartada: enforcement solo en la capa de aplicación (repositorio que "no hace UPDATE") — insuficiente, la regla dura 4 exige que la base lo rechace, no la disciplina.

2. **La app corre con un rol restringido; las migraciones con un rol privilegiado.** El rol de la plataforma core tiene INSERT/SELECT pero no UPDATE/DELETE sobre las tablas append-only. Alembic corre como rol de migración (dueño del schema) que sí puede crear/alterar. Evita que "la app no puede borrar" también signifique "la app no puede migrar".

3. **UUIDv7 como clave donde importa el orden temporal** (mensajes, `audit_log`). Ordena por clave sin depender del reloj de aplicación y sin un índice temporal adicional. Generación **en una sola fuente** (app-side con librería mantenida, o `uuidv7()` nativo si el Postgres destino es ≥18); se fija al implementar según la versión objetivo. Alternativa descartada: `bigserial` — acopla el orden a un secuencial global y complica sharding/exportación; UUID aleatorio v4 — pierde localidad temporal y fragmenta el índice.

4. **`inserted_text` vive en una fila de inserción por mensaje, no en la extracción.** `extraction` guarda `full_text` **una vez por adjunto** (reutilizado por dedup); una tabla de **inserción mensaje↔adjunto** guarda `inserted_text`, `token_count`, `truncated` — inmutable. Así las ramas comparten byte-idéntica la misma fila de inserción (prefijo cacheable) y "pedir otra parte del archivo" es una **inserción nueva** cortada de `full_text` sin re-parsear (ANEXO §5). Alternativa descartada: `inserted_text` como columna de `extraction` — rompería el caso de dos truncados distintos del mismo archivo.

5. **Stickiness estructural: `model_profile` es atributo de la sesión.** Todos los mensajes de una sesión comparten su `model_profile`; un intento de insertar un mensaje con perfil divergente lo rechaza un trigger/CHECK. **Editar/regenerar = rama dentro de la misma sesión** (mismo perfil); **cambiar de modelo = sesión nueva** con `forked_from` opcional al origen. Mantiene la invariante "una sesión, un perfil" trivial de verificar. Alternativa descartada: `model_profile` por mensaje sin ligar a la sesión — permitiría mezclar perfiles en una rama, violando el principio de transparencia de modelo.

6. **Dedup por `(tenant, sha256)`, no por `sha256` global.** El ANEXO §5 dice "misma instancia"; lo estrechamos a **por tenant** para respetar el aislamiento por tenant de [docs/06](../../../docs/06-seguridad-gobernanza.md) (la reutilización de `full_text` entre tenants filtraría la existencia de un archivo). Es superset-compatible con el ANEXO.

7. **Binario fuera de la base.** Postgres guarda metadatos + texto extraído; el binario vive en el volumen de archivos de la VM referenciado por `storage_path` (uuid, sin extensión, fuera del webroot). Sin S3 externo (ANEXO §5: los documentos del cliente no salen de la instancia).

8. **Triggers y grants son DDL hecho a mano en las migraciones.** `alembic revision --autogenerate` **no** capta triggers, grants ni funciones; se escriben con `op.execute(...)` y su `downgrade` los revierte. El autogenerate se usa solo para tablas/índices y se **revisa a mano** antes de commitear (constraint naming convention de SQLAlchemy para diffs y downgrades limpios). DDL en Postgres es transaccional: cada migración corre en su transacción.

9. **Los tests de invariantes corren contra un Postgres real.** Grants y triggers no son observables con un doble en memoria; el contract test de `StatePort` y los tests de invariante (rechazo de UPDATE/DELETE, `inserted_text` inmutable, stickiness, dedup) usan un Postgres local/efímero en CI. Coherente con `tests/contracts/` de [docs/05](../../../docs/05-estructura-y-convenciones.md).

## Risks / Trade-offs

- **Triggers añaden costo por escritura** → Mitigación: las escrituras de auditoría y mensajes no son el hot path frente al costo de una llamada LLM; el trigger es un `RAISE` condicional trivial.
- **Reotorgar un grant por descuido en una migración futura** → Mitigación: la capa de triggers sigue bloqueando; un test de invariante en CI falla si UPDATE/DELETE deja de ser rechazado.
- **Generación de UUIDv7 en dos fuentes (app y DB) desordenaría claves** → Mitigación: una sola fuente decidida al implementar; documentada en el módulo del adapter.
- **Dedup por tenant reduce el ahorro frente a dedup global** → Trade-off aceptado: el aislamiento por tenant pesa más que el ahorro de re-extraer un archivo idéntico entre clientes distintos (caso raro en una instancia interna).
- **`inserted_text` inmutable + retención**: purgar `full_text` pero conservar `inserted_text` deja texto de cliente vivo mientras viva la conversación → es el comportamiento requerido (ANEXO §5); la retención del binario/`full_text` es el control, y el escaneo N3 (`d14`) evita que entren secretos.

## Migration Plan

1. **Revisión inicial de schema** (Alembic): `sessions`, `messages` (+`parent_id`, índices por `session_id`/`parent_id`), `attachments`, `extractions`, inserción `message_attachments`, `audit_log`, y marcador de compactación (columna en la rama o tabla propia — ver Open Questions). Autogenerada y **revisada a mano**.
2. **Revisión de inmutabilidad**: funciones + triggers `BEFORE UPDATE OR DELETE` y `REVOKE` de grants sobre las tablas append-only, vía `op.execute`. `downgrade` elimina triggers/funciones y restaura privilegios.
3. **Rollback**: `alembic downgrade` reversible en ambas revisiones; en entornos ya poblados, el downgrade de la revisión 2 solo afecta reglas de inmutabilidad (no borra datos).
4. **Deploy**: las migraciones se ejecutan con el rol de migración durante el arranque/despliegue (el wiring de Compose y el rol de app llegan en `e24`); la plataforma core se conecta con el rol restringido.

## Open Questions

- **Marcador de compactación**: ¿columna(s) en la rama/sesión o tabla append-only propia? Se resuelve al implementar según cómo `b06` emita el evento de frontera de turno; en ambos casos es inmutable.
- **UUIDv7 nativo (`uuidv7()`, Postgres 18) vs generación app-side**: se fija según la versión de Postgres objetivo de la instancia; ambas cumplen el orden temporal por clave.
