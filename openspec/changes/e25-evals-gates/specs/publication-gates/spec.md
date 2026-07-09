# publication-gates — Delta Spec (e25-evals-gates)

> Contexto de transición: los gates de publicación de `d20-gobernanza-plataforma` y `d21-builders` nacen **pluggables en modo placeholder** (Nota de desacople del roadmap, 2026-07-09): mientras `e25-evals-gates` no esté archivado, publicar solo muestra la advertencia "score ausente" y no bloquea. Como los specs de `d20`/`d21` aún no están archivados en `openspec/specs/`, esta transición se documenta con requisitos **ADDED** (no MODIFIED): estos requisitos REEMPLAZAN el modo placeholder por el gate real.

## ADDED Requirements

### Requirement: El gate real reemplaza el modo placeholder

Al enchufar `e25-evals-gates`, el gate de publicación SHALL pasar de modo placeholder (advertencia visible, no bloqueo) a modo real (bloqueo verificado por el sistema). Las publicaciones realizadas mientras el gate operaba en modo placeholder SHALL seguir siendo válidas históricamente: el sistema MUST NOT re-evaluar ni invalidar retroactivamente versiones ya publicadas. Toda decisión del gate (publicación permitida o bloqueada) SHALL registrarse en el Audit Log append-only.

#### Scenario: Publicación previa a e25 sigue siendo válida históricamente

- **WHEN** una versión de prompt fue publicada mientras el gate operaba en modo placeholder (antes de enchufar `e25-evals-gates`)
- **THEN** esa versión sigue siendo válida y activa, y el sistema MUST NOT bloquearla ni re-evaluarla retroactivamente

#### Scenario: Tras e25, publicar sin corrida de evals queda bloqueado

- **WHEN** el gate real está activo y no existe una corrida de evals para el hash vigente del borrador
- **THEN** el botón Publicar SHALL estar deshabilitado con el motivo "evals pendientes" mostrado como texto (no solo tooltip), y el intento queda registrado en el Audit Log

### Requirement: Publicar exige score ≥ 80% y cero safety en rojo, verificado por el sistema

El gate de publicación SHALL habilitar Publicar solo cuando la corrida vigente para el hash del borrador cumpla **ambas** condiciones: score ≥ 80% **Y** cero casos `safety` en FAIL. El sistema MUST verificar el gate por sí mismo (imposible saltárselo con un checkbox o acción manual). Cuando el gate no se cumple, el botón Publicar SHALL quedar deshabilitado con el detalle de los casos fallados (`design/VISTAS/08-admin-gobernanza.md` §8.1 y §8.6; `design/FLUJOS.md` Flujo F).

#### Scenario: Score 79% bloquea la publicación

- **WHEN** la corrida vigente del borrador obtiene un score de 79% (sin casos `safety` en FAIL)
- **THEN** el botón Publicar SHALL estar deshabilitado con el motivo "score < 80%" y el detalle de los casos fallados

#### Scenario: Un caso safety en rojo bloquea aunque el score sea 95%

- **WHEN** la corrida vigente obtiene 95% de casos OK pero tiene ≥1 caso `safety` en FAIL
- **THEN** el botón Publicar SHALL estar deshabilitado con el motivo "bloqueado por safety", sin importar que el score global supere el 80%

#### Scenario: Score ≥ 80% y cero safety habilita Publicar

- **WHEN** la corrida vigente obtiene un score ≥ 80% y cero casos `safety` en FAIL, para el hash vigente del borrador
- **THEN** el sistema SHALL habilitar el botón Publicar y, al publicar, la decisión queda en el Audit Log

### Requirement: El gate de CI bloquea el pipeline con score < 80%

El pipeline de CI SHALL ejecutar el runner de evals sobre los datasets de los Agentes y Skills activos y MUST terminar en rojo si el score es < 80% o si hay ≥1 caso `safety` en FAIL, impidiendo que el cambio se considere listo.

#### Scenario: Score bajo en CI bloquea el pipeline

- **WHEN** una corrida de CI sobre los datasets activos obtiene un score < 80%
- **THEN** el job de evals SHALL terminar con exit code distinto de 0 y el pipeline queda en rojo

#### Scenario: Safety en rojo en CI bloquea aunque el score pase

- **WHEN** una corrida de CI obtiene un score ≥ 80% pero con ≥1 caso `safety` en FAIL
- **THEN** el job de evals SHALL terminar en rojo por el hard-fail individual de `safety`

### Requirement: El score de evals vigente aparece en la ficha técnica del Agente

El score de evals de la versión activa SHALL mostrarse en la ficha técnica del Agente (capa Técnico/Admin del catálogo, `d15-catalogo-agentes`; `design/FUNCIONALIDADES.md` §6), como número y fecha, sin detalle por caso.

#### Scenario: La ficha técnica muestra el score vigente

- **WHEN** un Técnico abre la ficha técnica de un Agente con una versión activa que tiene score de evals
- **THEN** la ficha muestra el score y la fecha de la corrida, sin exponer el detalle por caso (reservado a la vista 43, solo Admin)

### Requirement: El gate nunca se salta si el runner no está disponible

Si el runner de evals no responde, el sistema MUST mantener Publicar **bloqueado** (fail-closed): la ausencia de una corrida válida para el hash vigente nunca habilita la publicación (`design/VISTAS/08-admin-gobernanza.md` §8.1 estado "Degradado" y §8.6 error `RUNNER_OFFLINE`).

#### Scenario: Runner caído mantiene Publicar bloqueado

- **WHEN** el Admin intenta correr evals y el runner no está disponible
- **THEN** el sistema muestra un error accionable y el botón Publicar SHALL permanecer deshabilitado hasta obtener una corrida válida
