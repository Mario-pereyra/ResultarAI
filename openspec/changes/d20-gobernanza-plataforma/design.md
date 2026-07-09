# Design — d20-gobernanza-plataforma

## Context

Slice vertical (backend + UI) del bounded context `governance`, solo Admin, que da a la plataforma "de fábrica" el control operativo de runtime sin deploy y con todo auditado. Cubre cuatro vistas normativas de `design/VISTAS/08-admin-gobernanza.md` (`34-prompts`, `35-tools`, `38-flags`, `40-config-instancia`) y dos flujos E2E (`design/FLUJOS.md` F y I). Excluye por diseño la vista `36-conexiones` (Etapa P) y la vista `43-evals` (`e25`).

Restricciones vigentes: `core/` no importa frameworks (la gobernanza es lógica de `app/` sobre config viva en DB, no un contrato del núcleo); auditoría append-only (regla dura 4); términos exactos del glosario. Ajuste del pivote 2026-07-09 aplicado: los agentes concretos del `design/` (DocAgent/ValidationAgent/DevAgent) se leen como `default_chat` + agente de ejemplo; las tools de ejemplo son de un server MCP genérico, no `protheus_*` (Etapa P).

La decisión crítica que moldea todo el change es la **Nota de desacople** (`docs/07-roadmap.md`): el runner de evals lo ejecuta el product owner al final (`e25`), así que el gate de publicación **nace pluggable** — el contrato existe desde ya y opera en modo placeholder hasta que `e25` esté archivado.

## Goals / Non-Goals

**Goals:**

- Registro de Prompts con Postgres como fuente de runtime, versiones inmutables, activar/rollback sin deploy y espejo Git automático.
- Gate de publicación con contrato estable y dos modos (placeholder/enforcing) intercambiables sin reescribir el flujo de publicación.
- Feature flags + kill-switch por Agent y por Tool con efectos coordinados (<1 min, sin deploy) y auditados.
- Vista del Tool Registry con riesgo inmutable en runtime, permisos por rol/agente y matrices de visibilidad y capacidades como config viva.
- Configuración de instancia completa como fuente de defaults, no constantes de código.

**Non-Goals:**

- Runner de evals, datasets y golden set (`e25`); perfiles de conexión y bridges (Etapa P); builders (`d21`).
- Motor de cuotas (`d16`), centro de notificaciones (`d12`), catálogo (`d15`), tarjetas HITL (`d17`): se consumen por contrato, no se implementan aquí.
- Cualquier cambio en `core/`.

## Decisions

1. **Postgres como fuente de runtime de prompts; Git como espejo de solo lectura.** Alternativa (Git como fuente) descartada: activar/rollback sin deploy exige un puntero mutable en DB, y editar en caliente en un editor externo rompe la auditabilidad. El espejo a `prompts/` se escribe en el `publish` para code review y arqueología, nunca se lee en runtime.

2. **Gate de publicación como port/estrategia pluggable (`PublicationGate`).** El flujo de `publish` invoca un contrato estable con dos implementaciones: `PlaceholderGate` (score ausente = advertencia, publica) y `EnforcingGate` (score < 80% o `safety` en rojo = bloqueo). La selección depende de si `e25` está archivado (config de instancia/feature flag), no de reescribir el flujo. Alternativa (hardcodear el bloqueo ahora) descartada por la Nota de desacople: bloquearía toda publicación mientras no exista runner. El gate se evalúa contra el **hash** del contenido del `draft`, de modo que editar tras correr evals invalida la corrida.

3. **Kill-switch como corte de runtime reversible, no mutación de Manifest.** Complemento runtime del status `deprecated` (`a02`): apagar corta la ejecución sin reescribir el Manifest ni su status en el registry. Alternativa (marcar el Manifest `deprecated` al apagar) descartada: mezcla el ciclo de vida declarativo (PR) con la operación de emergencia (un clic, reversible en <1 min).

4. **Efectos del kill-switch por contratos con otros slices.** d20 emite los efectos y los consumidores los aplican: congelar tarjetas HITL (`d17`), "No disponible temporalmente" en el catálogo (`d15`), notificar sesiones activas (`d12`). d20 define el contrato del evento de kill-switch; no reimplementa esas vistas. Alternativa (que d20 escriba directo en las tablas de HITL/catálogo) descartada por acoplamiento.

5. **Clasificación de riesgo de Tools inmutable en runtime; solo por PR.** La consola muestra la clasificación (siempre con palabra) y bloquea su edición; HITL en escritura/destructiva marcado y bloqueado. Coherente con "toolset fijo por versión de Agent" (`c09`). Lo que sí es config viva: permisos rol×tool y las matrices de visibilidad/capacidades, versionadas y auditadas en DB.

6. **Matrices (visibilidad agente×rol, capacidades por vista) como config viva versionada en DB.** Consumidas por `d15` (catálogo) y por la shell. Cambian sin deploy, con historial y auditoría. Alternativa (matriz en YAML de manifiesto) descartada: la asignación por rol es operación de Admin, no contrato que exija PR; la semántica de cada capacidad sí cambia por PR.

7. **Toda mutación de gobernanza es append-only en auditoría.** Publicaciones, activaciones, rollbacks, cambios de flag, kill-switches y cambios de config generan `AuditEvent` inmutables. Reusa el Audit Log de `a03`/`b04`; d20 no crea un mecanismo de auditoría paralelo.

## Risks / Trade-offs

- **[El modo placeholder del gate se vuelve permanente y se publica siempre sin evals]** → Mitigación: la advertencia "se publica sin evals" es visible y auditada; el cambio a `EnforcingGate` es automático al archivar `e25` (la selección del gate no es un olvido manual). El contrato ya existe, no hay migración de flujo.
- **[Kill-switch que no propaga todos sus efectos deja tarjetas HITL "vivas" en un agente apagado]** → Mitigación: el escenario de spec exige congelar HITL + deshabilitar catálogo + notificar como un solo efecto auditado; test de integración que verifica los cinco efectos.
- **[Editar el espejo Git y creer que cambia el runtime]** → Mitigación: spec explícita de que el runtime ignora `prompts/`; el snapshot es solo lectura para runtime.
- **[Deriva entre matriz de visibilidad (d20) y catálogo (d15)]** → Mitigación: la matriz es el contrato único que `d15` consume; se especifica aquí y `d15` la lee, sin copia local.
- **[Acoplar d20 a slices aún no implementados (d12/d15/d16/d17)]** → Mitigación: d20 depende de sus contratos (evento de kill-switch, config de cuota/TTL, matriz), no de su implementación; los slices consumidores se archivan por separado.

## Migration Plan

- No hay datos legados de gobernanza (greenfield). El seed de fábrica crea: la versión inicial `default_chat@1` en `published`+activa, la matriz de visibilidad por defecto y la config de instancia por defecto (branding `default`, retención 90 días, umbral cuota 80%, TTL HITL por defecto).
- Rollout: el gate arranca en `PlaceholderGate`; al archivar `e25` se activa `EnforcingGate` sin tocar el flujo de publicación.
- Rollback operativo: activar/rollback de prompts y reactivación de kill-switch son la propia estrategia de reversión sin deploy; los cambios de config y matrices son reversibles por su historial versionado.

## Open Questions

*(ninguna — el gate pluggable, la fuente de runtime en Postgres y los contratos con d12/d15/d16/d17 quedan decididos aquí; el runner real de evals se resuelve en `e25`).*
