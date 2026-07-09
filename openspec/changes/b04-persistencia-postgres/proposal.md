# Proposal — b04-persistencia-postgres

## Why

`a03-core-gobernanza` define `StatePort` y el contrato `AuditEvent` como interfaces puras en `core/`, pero sin un adapter que los materialice nada sobrevive a un reinicio y las dos garantías que sostienen la economía del producto quedan en el aire: **append-only / branch-never-rewrite** ([design/FUNCIONALIDADES.md](../../../design/FUNCIONALIDADES.md) §14) y el **Audit Log append-only e inmutable** (regla dura 4, [docs/06-seguridad-gobernanza.md](../../../docs/06-seguridad-gobernanza.md)). Este change entrega el adapter Postgres detrás de `StatePort` más las migraciones Alembic, con el modelo de datos que hace de esas garantías una **invariante física de la base** —no una convención de aplicación—: la historia jamás se reescribe porque editar/regenerar es una rama nueva, y el audit log rechaza UPDATE/DELETE a nivel de motor. Abre la Etapa B: sin él, `b06-runtime-grafos` no tiene dónde persistir la conversación ni sus decisiones.

## What Changes

- Se añade el adapter **`persistence_postgres`** (`adapters/persistence_postgres/`, bounded context `orchestration`/estado) que implementa `StatePort` de `a03` contra Postgres, con **transacciones explícitas** y sin filtrar detalles del motor hacia `core/`.
- Se añade **Alembic** para migraciones versionadas; toda migración autogenerada se **revisa a mano** antes de aplicarse (la autogeneración no capta constraints ni grants).
- Modelo de **sesiones y mensajes append-only**: tabla `messages` con `parent_id` — editar un mensaje o regenerar una respuesta crea una **rama** nueva; el selector de versiones ("versión 1/2") se apoya en este árbol; la historia JAMÁS se reescribe (**branch-never-rewrite**). Las ramas comparten adjuntos y prefijo cacheable.
- **Stickiness de perfil de modelo**: una sesión vive en un solo `model_profile`; cambiar de modelo = rama/sesión nueva explícita — nunca se mezclan perfiles dentro de una rama (constraint en BD, no solo en app).
- **Marcadores de compactación** como parte del modelo de sesión: la compactación al 80% de la ventana ocurre **una sola vez**, en frontera de turno, y queda registrada como evento inmutable (coherente con append-only: no reescribe historia).
- **Audit Log persistido**: tabla `audit_log` append-only **sin UPDATE ni DELETE**, con enforcement **físico** (grants de rol + triggers que rechazan la mutación, no solo disciplina de aplicación) y consulta por filtros (usuario, tenant, agente, skill, tool, rango temporal, decisión). Persiste el contrato `AuditEvent` de `a03`.
- **Schema de attachments** según [design/ANEXO-ATTACHMENTS.md](../../../design/ANEXO-ATTACHMENTS.md) §5: tabla `attachments` (uuid, `sha256` para dedup, `status`, `scan_result` con hallazgos N2/N3) + su `extraction` (`full_text`, `inserted_text` **inmutable** una vez fijado, `token_count`, `extractor_version`). **Solo el schema y sus invariantes** — el pipeline de extracción llega en `d14-attachments`.
- Se usan **UUIDv7** como claves donde el orden temporal importa (mensajes, eventos de auditoría), para ordenar por clave sin depender de relojes de aplicación.

## Capabilities

### New Capabilities

- `conversation-persistence`: sesiones y mensajes en Postgres; ramas por `parent_id` (branch-never-rewrite), selector de versiones, stickiness de `model_profile`, marcadores de compactación e invariantes append-only aplicadas en la base.
- `attachment-storage`: schema de `attachments` + `extraction` conforme al ANEXO §5, con sus invariantes (dedup por `sha256`, `inserted_text` inmutable, `scan_result` como metadato) y retención configurable por instancia. Solo el modelo de datos.
- `audit-persistence`: tabla `audit_log` append-only con enforcement físico (grants/triggers que rechazan UPDATE/DELETE) y consulta por filtros; persistencia del contrato `AuditEvent`.

### Modified Capabilities

*(ninguna — `openspec/specs/` está vacío; no existen specs previas)*

## No-objetivos

- **Sin pipeline de extracción de adjuntos** (validación magic bytes, parseo por tipo, sanitización anti-injection, escaneo N2/N3, truncado): eso es `d14-attachments`. Aquí solo el schema donde ese pipeline escribirá.
- **Sin API de chat**: streaming SSE, edición=rama en runtime, regeneración y selector en la UI son `d13-chat-conversacion`. Aquí solo el modelo de datos que esos flujos usarán.
- **Sin motor de cuotas ni liberaciones** (`d16-cuotas-liberaciones`): no se crean tablas de presupuesto ni contadores de consumo.
- **Sin runtime**: no se ejecuta LangGraph ni se crean grafos (`b06`); el adapter persiste estado, no orquesta.
- **Sin lógica de dominio nueva en `core/`**: los contratos `StatePort` y `AuditEvent` los define `a03`; este change los implementa, no los redefine.
- **Sin binarios en la base**: el binario del adjunto vive en el volumen de archivos de la VM (ANEXO §5); Postgres guarda metadatos y extracción de texto, sin S3 externo.

## Bounded context afectado

`orchestration` (estado de conversación) y `governance` (persistencia del Audit Log), materializados **fuera de `core/`** en `adapters/persistence_postgres/`. El adapter implementa los Ports de `core/` y traduce hacia Postgres; no decide política ni negocio (regla de dependencia, [docs/02-arquitectura.md](../../../docs/02-arquitectura.md)). No importa otros adapters (contrato de independencia de import-linter, `a01`).

## Impact

- `resultarai/adapters/persistence_postgres/`: implementación de `StatePort`, repositorios de sesiones/mensajes/adjuntos/audit, modelos SQLAlchemy y configuración de conexión.
- `alembic/` (raíz o dentro del adapter): entorno de migraciones + revisiones iniciales revisadas a mano (schema de sesiones, mensajes, attachments, extraction, audit_log; triggers y grants de inmutabilidad).
- `tests/contracts/`: contract test del adapter contra `StatePort`; tests de invariantes (rama nueva no reescribe historia; UPDATE/DELETE sobre `audit_log` rechazado; `inserted_text` inmutable; dedup por `sha256`; stickiness de `model_profile`) contra un Postgres local.
- `docker compose` / setup de entorno (`docs/05`): servicio Postgres para desarrollo y CI.
- Referencia del blueprint: audit log como **event sourcing acotado** a una tabla ([docs/02-arquitectura.md](../../../docs/02-arquitectura.md), [docs/06-seguridad-gobernanza.md](../../../docs/06-seguridad-gobernanza.md)); ANEXO §5 (almacenamiento y retención) como fuente normativa del schema de adjuntos.
