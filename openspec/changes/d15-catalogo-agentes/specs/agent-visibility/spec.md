# agent-visibility — Delta Spec (d15-catalogo-agentes)

## ADDED Requirements

### Requirement: Contrato de lectura de la matriz de visibilidad agente×rol

El sistema SHALL exponer un contrato de solo lectura que, dado un agente publicado en el Agent Registry (`a02-core-manifiestos`) y el rol del usuario autenticado (Admin, Técnico o Funcional), devuelve si ese agente es visible para ese rol. Este change SHALL implementar únicamente el lado de lectura del contrato; crear, editar o versionar entradas de la matriz de visibilidad es responsabilidad de `d20-gobernanza-plataforma` (`design/FUNCIONALIDADES.md` §11 "Matriz de visibilidad agente×rol").

#### Scenario: Consulta de visibilidad con entrada explícita en la matriz

- **WHEN** existe una entrada explícita en la matriz de visibilidad para el par (agente, rol)
- **THEN** el contrato de lectura devuelve esa entrada tal como está configurada, sin aplicar ningún default

#### Scenario: El contrato de lectura no ofrece operaciones de escritura

- **WHEN** un caso de uso de `d15-catalogo-agentes` invoca el contrato de visibilidad
- **THEN** solo puede consultar el resultado por (agente, rol); ningún endpoint de este change permite crear, editar ni borrar una entrada de la matriz

### Requirement: Defaults por status del agente cuando no hay override explícito

Cuando no exista una entrada explícita en la matriz de visibilidad para un par (agente, rol) — incluido mientras `d20-gobernanza-plataforma` no esté archivado — el sistema SHALL aplicar los defaults documentados en `design/VISTAS/03-catalogo.md`: los agentes con estado comercial `activo` o `beta` SHALL ser visibles para Admin, Técnico y Funcional; los agentes `próximamente` SHALL ser visibles por default para Técnico y Admin, y ocultos para Funcional salvo habilitación explícita; los agentes `deprecado` SHALL ser visibles únicamente para Admin.

#### Scenario: Agente activo visible sin configuración explícita

- **WHEN** un agente tiene estado comercial `activo` y no existe entrada explícita en la matriz para ningún rol
- **THEN** el contrato de lectura devuelve visible para Admin, Técnico y Funcional

#### Scenario: Agente próximamente oculto para Funcional por default

- **WHEN** un agente tiene estado comercial `próximamente` y no existe entrada explícita en la matriz
- **THEN** el contrato de lectura devuelve visible para Admin y Técnico, y oculto para Funcional

#### Scenario: Agente deprecado visible solo para Admin

- **WHEN** un agente tiene estado comercial `deprecado` y no existe entrada explícita en la matriz
- **THEN** el contrato de lectura devuelve visible únicamente para Admin

### Requirement: Piso de seguridad — toolset de escritura nunca visible para Funcional

El sistema SHALL ocultar al rol Funcional, sin excepción y sin que ninguna entrada de la matriz de visibilidad pueda anularlo, cualquier agente cuyo toolset (Skills habilitadas del `AgentManifest` × Tools que cada Skill declara, con clasificación lectura/escritura fija por versión según `a02-core-manifiestos`/`c09-mcp-tools`) incluya al menos una Tool clasificada `escritura`. Este piso es la garantía de que un Funcional nunca ve un agente cuyo toolset excede sus permisos.

#### Scenario: Un Funcional no ve un agente con tools de escritura aunque la matriz lo marque visible

- **WHEN** la matriz de visibilidad tiene una entrada explícita que marca como visible para Funcional un agente que declara al menos una Tool clasificada `escritura`
- **THEN** el contrato de lectura devuelve oculto para Funcional; el piso de seguridad prevalece sobre la entrada de la matriz

#### Scenario: Un agente de solo lectura sigue las reglas normales de la matriz

- **WHEN** un agente no declara ninguna Tool clasificada `escritura`
- **THEN** su visibilidad para Funcional sigue la entrada explícita de la matriz o, en su ausencia, el default por estado comercial

### Requirement: No revelar existencia a un rol sin acceso

Ante un acceso directo (deep link) a un agente que no es visible para el rol del usuario, o a un identificador de agente inexistente, el sistema SHALL responder con el mismo resultado en ambos casos, sin distinguir "no existe" de "existe pero tu rol no tiene acceso".

#### Scenario: Deep link a agente fuera de la matriz del rol

- **WHEN** un usuario Funcional accede directo a la ficha de un agente que no es visible para su rol
- **THEN** el sistema responde el mismo estado que ante un identificador de agente inexistente, sin filtrar la existencia del agente

### Requirement: Cambios de visibilidad en caliente

Un cambio en la matriz de visibilidad, o en el toolset de un agente que active o desactive el piso de seguridad, SHALL reflejarse a partir de la próxima consulta del catálogo; el sistema no SHALL requerir un despliegue para que el cambio tome efecto.

#### Scenario: Un agente desaparece de la grilla tras un cambio de matriz

- **WHEN** el Admin quita un agente de la matriz de visibilidad de un rol mientras un usuario de ese rol está navegando el catálogo
- **THEN** el agente ya no aparece en la siguiente carga del catálogo para ese usuario, sin necesidad de un despliegue

### Requirement: Visibilidad de fábrica sin matriz configurada

En una instancia de fábrica, antes de que exista ninguna entrada explícita en la matriz de visibilidad, el sistema SHALL mostrar `default_chat` y el agente de ejemplo de `a02-core-manifiestos` (ambos con estado comercial `activo` y sin Tools de escritura) como visibles para Admin, Técnico y Funcional, por aplicación del default de la Requirement "Defaults por status del agente cuando no hay override explícito".

#### Scenario: Catálogo de fábrica sin matriz configurada

- **WHEN** una instancia recién desplegada no tiene ninguna entrada en la matriz de visibilidad
- **THEN** Admin, Técnico y Funcional ven `default_chat` y el agente de ejemplo en su catálogo
