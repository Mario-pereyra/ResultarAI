# repo-scaffolding — Delta Spec (a01-fundacion-repo)

## ADDED Requirements

### Requirement: Estructura de paquetes conforme a docs/05

El repo SHALL contener el árbol de paquetes definido en `docs/05-estructura-y-convenciones.md`: `resultarai/core/`, `resultarai/adapters/`, `resultarai/app/`, `manifests/` y `tests/`, cada paquete Python con `__init__.py` y marcador `py.typed`.

#### Scenario: Árbol de paquetes importable

- **WHEN** se ejecuta `uv run python -c "import resultarai.core, resultarai.adapters, resultarai.app"`
- **THEN** la importación termina sin errores y sin efectos secundarios (ningún paquete ejecuta lógica al importarse)

### Requirement: Fronteras arquitectónicas verificadas por máquina

La regla de dependencia SHALL estar codificada en import-linter con tres contratos: (1) `resultarai.core` no importa `resultarai.adapters`, `resultarai.app` ni frameworks (langgraph, litellm, langfuse, fastapi, httpx); (2) capas `app → adapters → core`; (3) independencia entre adapters.

#### Scenario: Violación de frontera detectada

- **WHEN** un módulo de `resultarai/core/` agrega `import litellm` (o cualquier import prohibido) y se ejecuta `uv run lint-imports`
- **THEN** el comando termina con exit code distinto de 0 señalando el contrato violado

#### Scenario: Árbol limpio pasa

- **WHEN** se ejecuta `uv run lint-imports` sobre el esqueleto sin violaciones
- **THEN** los 3 contratos reportan "KEPT" y el exit code es 0

### Requirement: Tooling de calidad ejecutable con comandos únicos

El proyecto SHALL exponer, vía uv, comandos únicos y documentados para lint (`ruff check`), formato (`ruff format --check`), tipos (`mypy` en modo estricto), fronteras (`lint-imports`) y tests (`pytest`).

#### Scenario: Suite de calidad en verde sobre el esqueleto

- **WHEN** se ejecutan los cinco comandos sobre el repo recién clonado con `uv sync`
- **THEN** todos terminan con exit code 0 y al menos un test de humo de `core/` corre sin acceso a red

### Requirement: CI obligatoria en cada cambio

El repo SHALL tener un workflow de GitHub Actions que ejecute la suite completa (lint, formato, tipos, fronteras, tests) en cada push y pull request a `main`.

#### Scenario: CI falla ante una violación

- **WHEN** un commit introduce una violación de frontera o un test roto
- **THEN** el workflow termina en rojo y el PR no puede considerarse listo

### Requirement: Verificación local previa al commit

El repo SHALL tener pre-commit configurado con, como mínimo, ruff (lint+formato) y chequeos de higiene (fin de línea, YAML válido), instalable con un comando documentado.

#### Scenario: Commit con error de lint rechazado localmente

- **WHEN** un desarrollador con pre-commit instalado intenta commitear código que viola ruff
- **THEN** el hook bloquea el commit y muestra el error accionable
