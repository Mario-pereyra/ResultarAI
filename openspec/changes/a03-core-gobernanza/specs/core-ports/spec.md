# core-ports — Delta Spec (a03-core-gobernanza)

## ADDED Requirements

### Requirement: Los Ports se definen en core como Protocol

`core/ports/` SHALL definir los seis Ports como interfaces `typing.Protocol`: `LLMPort`, `ToolPort`, `TracePort`, `StatePort`, `PolicyPort` y `RetrievalPort`. Cada Port lo implementa un Adapter en `adapters/` (que traduce, no decide). `core/ports/` SHALL no importar ningún Adapter ni framework (regla de dependencia de `docs/02`, verificada por import-linter en `a01`).

#### Scenario: Ports libres de dependencias de adapters

- **WHEN** se ejecuta `lint-imports` y `mypy` sobre `core/ports/`
- **THEN** ningún Port importa `resultarai.adapters`, `resultarai.app` ni frameworks (langgraph, litellm, langfuse, fastapi, httpx), y los seis `Protocol` existen

#### Scenario: Un Adapter conforme satisface el Protocol

- **WHEN** una clase de `adapters/` implementa todos los métodos declarados por un Port
- **THEN** el chequeo estructural de tipos (mypy) la acepta como implementación de ese Port sin herencia explícita

### Requirement: LLMPort — única puerta a los modelos

`LLMPort` SHALL declarar el contrato mínimo para invocar un modelo de lenguaje, de modo que toda llamada a modelo pase por su Adapter (LiteLLM en `b05`) y nunca por un SDK de proveedor directo (regla dura 2).

#### Scenario: Contrato de invocación de modelo presente

- **WHEN** se inspecciona `LLMPort`
- **THEN** declara al menos un método de invocación de modelo cuyo Adapter concreto se implementa en un change posterior, sin acoplar `core/` a ningún proveedor

### Requirement: ToolPort — ejecución de Tools solo tras decisión allow

`ToolPort` SHALL declarar el contrato para ejecutar una Tool a través de su Adapter. Como contrato de dominio, una Tool SHALL invocarse únicamente cuando el Policy Gate haya devuelto un `PolicyDecision` de efecto `allow` para esa acción (tools solo vía skills, regla dura 3; el Default Chat nunca ejecuta tools directamente).

#### Scenario: Ejecución de Tool precedida por decisión allow

- **WHEN** el runtime va a ejecutar una Tool vía `ToolPort`
- **THEN** existe un `PolicyDecision` de efecto `allow` para esa acción; si la decisión fuera `deny` o `escalate_hitl`, la Tool no se invoca

### Requirement: TracePort — hooks de trazabilidad

`TracePort` SHALL declarar el contrato para emitir trazas de cada paso, implementado por el Adapter de observabilidad (Langfuse en `b07`), sin acoplar `core/` a ninguna librería de tracing.

#### Scenario: Contrato de traza presente

- **WHEN** se inspecciona `TracePort`
- **THEN** declara el contrato mínimo para registrar trazas de un paso, cuyo Adapter concreto llega en un change posterior

### Requirement: StatePort — estado de conversación y grafo

`StatePort` SHALL declarar el contrato para cargar y persistir el estado de una conversación o grafo, implementado por un Adapter (Postgres en `b04`), sin que `core/` conozca el motor de almacenamiento.

#### Scenario: Contrato de estado presente

- **WHEN** se inspecciona `StatePort`
- **THEN** declara el contrato mínimo para cargar y persistir estado, cuyo Adapter concreto llega en un change posterior

### Requirement: PolicyPort — implementación del gate reemplazable

`PolicyPort` SHALL declarar el contrato que abstrae la evaluación de políticas, de modo que la implementación del Policy Gate pueda reemplazarse por un motor externo (OPA/Cedar) sin tocar el resto del sistema (`docs/06`).

#### Scenario: Backend de políticas intercambiable

- **WHEN** se sustituye el Adapter que implementa `PolicyPort` por otro backend de políticas
- **THEN** los llamadores en `core/` y `app/` no cambian, porque dependen solo del `Protocol` `PolicyPort`

### Requirement: RetrievalPort como placeholder RAG con Adapter nulo

`RetrievalPort` SHALL declararse como contrato mínimo de recuperación (placeholder RAG por diseño, `docs/07` decisión 5) acompañado de un Adapter nulo que devuelve siempre un resultado vacío. Este change SHALL dejar constancia explícita de la decisión de **no implementar RAG**: la puerta queda abierta (contrato + Adapter nulo), la recuperación real llega en la Etapa P.

#### Scenario: El Adapter nulo devuelve vacío

- **WHEN** se invoca el Adapter nulo de `RetrievalPort` con cualquier consulta
- **THEN** devuelve un resultado vacío, sin acceder a ninguna fuente de datos ni realizar I/O

#### Scenario: RAG no se implementa en este change

- **WHEN** se revisa el alcance entregado por `a03-core-gobernanza`
- **THEN** solo existen el `Protocol` `RetrievalPort` y su Adapter nulo, y no hay ninguna implementación de recuperación real
