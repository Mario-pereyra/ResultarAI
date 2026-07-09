# manifest-validation

## Purpose

CLI de validación, fail-fast al arranque y verificación en CI de todos los manifiestos.

## Requirements

### Requirement: CLI de validación de manifiestos

El proyecto SHALL exponer un comando CLI, ejecutable vía uv, que valide todos los manifiestos de `manifests/` contra sus schemas Pydantic y sus reglas de referencia cruzada, sin arrancar la plataforma ni acceder a red. El comando MUST terminar con exit code 0 cuando todo valida y distinto de 0 cuando algún Manifest falla, reportando archivo y causa.

#### Scenario: CLI en verde sobre manifiestos válidos

- **WHEN** se ejecuta el CLI de validación sobre los manifiestos de fábrica de ejemplo
- **THEN** todos validan y el comando termina con exit code 0

#### Scenario: CLI falla ante un Manifest inválido

- **WHEN** un Manifest viola su schema (p. ej. campo obligatorio ausente) y se ejecuta el CLI
- **THEN** el comando termina con exit code distinto de 0 nombrando el archivo y el error

#### Scenario: CLI detecta una referencia colgante

- **WHEN** una Skill referencia una Tool inexistente y se ejecuta el CLI
- **THEN** el comando falla reportando la referencia cruzada rota

#### Scenario: CLI no accede a red

- **WHEN** se ejecuta el CLI de validación sin conectividad
- **THEN** completa la validación igual, porque solo lee YAML y aplica schemas

### Requirement: Validación fail-fast al arranque

La aplicación SHALL validar todos los manifiestos al arrancar y MUST abortar el arranque (fail-fast) si alguno no valida contra su schema o sus referencias cruzadas. Un arranque con manifiestos inválidos MUST NOT dejar la plataforma en servicio; el error MUST identificar el Manifest culpable.

#### Scenario: Arranque exitoso con manifiestos válidos

- **WHEN** la aplicación arranca con todos los manifiestos válidos
- **THEN** los Registries quedan construidos y la plataforma continúa el arranque

#### Scenario: Arranque abortado por Manifest inválido

- **WHEN** la aplicación arranca con un Manifest que viola su schema
- **THEN** el arranque se aborta de inmediato citando el Manifest culpable, sin quedar en servicio

#### Scenario: Arranque abortado por referencia colgante

- **WHEN** al arrancar un Agent habilita una Skill inexistente
- **THEN** el arranque se aborta señalando la referencia cruzada rota

#### Scenario: Manifest draft no impide el arranque

- **WHEN** existe un Manifest `draft` válido junto a los `active`
- **THEN** el arranque continúa y el `draft` no se carga como invocable

### Requirement: Validación de manifiestos en CI en cada PR

El pipeline de CI SHALL ejecutar la validación de todos los manifiestos en cada push y pull request a `main`, reutilizando el mismo CLI de validación. Un PR con cualquier Manifest inválido o con referencias colgantes MUST dejar la CI en rojo y no poder considerarse listo.

#### Scenario: CI en verde con manifiestos válidos

- **WHEN** un PR no altera la validez de ningún Manifest
- **THEN** el job de validación de manifiestos pasa en verde

#### Scenario: CI en rojo por Manifest inválido

- **WHEN** un PR introduce un Manifest que viola su schema
- **THEN** el job de validación termina en rojo y el PR no puede considerarse listo

#### Scenario: CI en rojo por referencia colgante

- **WHEN** un PR borra una Tool aún referenciada por una Skill
- **THEN** el job de validación falla reportando la referencia cruzada rota

#### Scenario: CI reutiliza el CLI de validación

- **WHEN** el job de CI de manifiestos se ejecuta
- **THEN** invoca el mismo comando CLI que un desarrollador correría localmente, sin lógica duplicada
