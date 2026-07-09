# evals — Delta Spec (e25-evals-gates)

## ADDED Requirements

### Requirement: Datasets de evals versionados en YAML (solo datos sintéticos)

El sistema SHALL almacenar los datasets de evals como archivos YAML versionados en Git bajo `evals/`, uno por Agent, Skill o Workflow. Cada dataset SHALL declarar sus casos con: `input`, salida esperada o criterios de aceptación **deterministas** (comparación exacta/normalizada, contención de subcadena, coincidencia de patrón o aserciones estructurales), y `category`. Cada dataset materializa el `EvalTemplateManifest` correspondiente, que pasa de `status: placeholder` a real. Los datos de los casos SHALL ser **sintéticos**; un dataset con datos reales de cualquier Tenant MUST rechazarse en la revisión humana (referencia: `docs/06-seguridad-gobernanza.md` estrategia de evals placeholder-por-diseño; `design/FUNCIONALIDADES.md` §12).

#### Scenario: Dataset sintético válido se carga

- **WHEN** se carga un dataset YAML de `evals/` cuyos casos declaran `input`, criterio de aceptación determinista y `category`, con datos sintéticos
- **THEN** el dataset valida contra su schema y queda disponible para el runner, y su `EvalTemplateManifest` figura como real (no `placeholder`)

#### Scenario: Dataset con datos reales de cliente es rechazado en revisión

- **WHEN** un caso propuesto para un dataset contiene datos reales de un Tenant (no sintéticos)
- **THEN** la revisión humana MUST rechazar el caso y no se incorpora al dataset

### Requirement: Casos safety con hard-fail individual

Cada dataset SHALL permitir marcar casos con la categoría `safety`. El runner MUST tratar cada caso `safety` en rojo como **hard-fail individual**: un solo caso `safety` en FAIL marca la corrida como BLOQUEANTE sin importar el score global. Esta marca se refleja en la vista `43-admin-evals` (`design/VISTAS/08-admin-gobernanza.md` §8.6) con la fila destacada y la nota "hard-fail individual: bloquea deploy/publicación".

#### Scenario: Un caso safety en rojo bloquea aunque el score global sea alto

- **WHEN** una corrida obtiene 95% de casos OK pero tiene ≥1 caso `safety` en FAIL
- **THEN** la corrida SHALL marcarse como BLOQUEANTE y el detalle destaca la fila `safety` fallada

### Requirement: Runner de evals ejecuta un dataset contra una versión de prompt/agente

El runner de evals SHALL ejecutar un dataset contra una versión de prompt/Agent identificada por el hash de su contenido, invocando el modelo únicamente a través del gateway de modelos (`b05-gateway-modelos`, nunca SDKs de proveedor directos). Cada caso SHALL quedar trazado en Langfuse (`b07-observabilidad`) con un score por caso registrado mediante la API de scores de Langfuse. La corrida SHALL producir un **score por versión** (porcentaje de casos OK) más el **detalle por caso** (esperado, obtenido, resultado PASS/FAIL). El runner MUST ser ejecutable tanto en local como en CI.

#### Scenario: Corrida produce score por versión y detalle por caso

- **WHEN** el runner ejecuta un dataset contra la versión `docagent@13`
- **THEN** produce un score por versión (% de casos OK) y una tabla de detalle por caso con esperado, obtenido y PASS/FAIL

#### Scenario: Cada caso queda trazado en Langfuse con su score

- **WHEN** el runner evalúa cada caso del dataset
- **THEN** cada caso genera una traza en Langfuse con su score registrado vía la API de scores, y toda llamada al modelo pasó por el gateway de modelos

#### Scenario: Corrida ejecutable en local

- **WHEN** un desarrollador ejecuta el runner en local sobre un dataset de `evals/`
- **THEN** obtiene el mismo score por versión y detalle por caso que produciría en CI

### Requirement: La corrida se asocia al hash de la versión evaluada

Toda corrida SHALL quedar asociada al hash de contenido de la versión de prompt evaluada. Si el borrador se edita después de correr los evals, la corrida previa MUST invalidarse (el estado del gate vuelve a "evals pendientes"), porque el gate se evalúa contra el hash vigente (`design/VISTAS/08-admin-gobernanza.md` §8.1 y §8.6).

#### Scenario: Editar el borrador invalida la corrida previa

- **WHEN** existe una corrida verde para el hash `H1` de un borrador y luego el Admin edita el borrador cambiando su hash a `H2`
- **THEN** la corrida de `H1` deja de ser válida para el gate y el estado del borrador vuelve a "evals pendientes"

### Requirement: Cobertura mínima de datasets de Skill

El dataset de cada Skill publicable SHALL contener al menos 3 casos de eval ejecutables, materializando los ≥3 casos que exige el Skills Builder (`d21-builders`, `design/FUNCIONALIDADES.md` §13).

#### Scenario: Skill con menos de 3 casos no cumple la cobertura mínima

- **WHEN** el dataset de una Skill declara menos de 3 casos ejecutables
- **THEN** la cobertura mínima no se cumple y la Skill no puede considerarse lista para publicar

### Requirement: Feedback negativo se convierte en caso de regresión

Los 👎 con comentario marcados como "candidato a regresión" en `b07-observabilidad` SHALL poder convertirse en un caso de eval mediante **revisión humana**, desde la bandeja de la vista `43-admin-evals` (`design/FUNCIONALIDADES.md` §4; `design/FLUJOS.md` Flujo F paso 7). El caso nace con origen `feedback`, entra al golden set como **candidato** con `input` (mensaje del usuario) y `obtenido` (respuesta del Agent) prellenados y `esperado` a completar. Un candidato incompleto (sin `esperado`) MUST NOT ejecutarse en CI. Todo bug de producción SHALL convertirse en un caso de regresión en `evals/`.

#### Scenario: Convertir feedback negativo en caso candidato

- **WHEN** el Admin pulsa "Convertir en caso" sobre un 👎 con comentario en la bandeja de la vista 43
- **THEN** se crea un caso en el golden set con origen `feedback`, `input` y `obtenido` prellenados y `esperado` vacío, marcado como candidato

#### Scenario: Candidato incompleto no corre en CI

- **WHEN** un caso candidato con origen `feedback` no tiene su `esperado` completado
- **THEN** el runner MUST omitirlo en las corridas de CI hasta que la revisión humana lo complete
