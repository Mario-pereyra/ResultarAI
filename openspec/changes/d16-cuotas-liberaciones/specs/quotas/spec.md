# quotas — Delta Spec (d16-cuotas-liberaciones)

## ADDED Requirements

### Requirement: Jerarquía de alcances de la Cuota

Una **Cuota** SHALL existir en cuatro alcances anidados —`global`, `grupo`, `usuario` y `sesion`— modelados con un schema Pydantic en `core/`. Cada alcance SHALL declarar su límite en la unidad de presupuesto de la instancia y su período de renovación. Un turno SHALL evaluarse contra los cuatro alcances aplicables; el margen efectivo es el del alcance más restrictivo. Conforme a `design/FUNCIONALIDADES.md` §4/§11 y `design/FLUJOS.md` Flujo E.

#### Scenario: El alcance más restrictivo determina el margen

- **WHEN** un usuario tiene margen en su Cuota `usuario`, `grupo` y `global`, pero su Cuota de `sesion` ya no alcanza para el costo estimado del turno
- **THEN** la evaluación bloquea el turno y reporta `sesion` como el alcance que bloqueó, sin emitir la llamada al modelo

#### Scenario: Todos los alcances con margen permiten el turno

- **WHEN** los cuatro alcances aplicables (`global`, `grupo`, `usuario`, `sesion`) tienen margen para el costo estimado del turno
- **THEN** la evaluación autoriza el gasto y la llamada al modelo puede emitirse

### Requirement: Defaults de Cuota como configuración de instancia

Los límites por defecto de cada alcance SHALL ser configuración de instancia, no constantes embebidas en el código de `core/`. Un alcance sin override SHALL tomar el default de instancia para ese alcance; un override por entidad (grupo, usuario o sesión) SHALL prevalecer sobre el default.

#### Scenario: Entidad sin override toma el default de instancia

- **WHEN** se evalúa la Cuota de un usuario que no tiene override propio
- **THEN** su límite de alcance `usuario` es el default de instancia para ese alcance, resuelto en configuración y no como constante de código

#### Scenario: Override por entidad prevalece sobre el default

- **WHEN** un grupo tiene un override de límite distinto del default de instancia
- **THEN** la evaluación de la Cuota `grupo` de sus miembros usa el override y no el default

### Requirement: Evaluación de la Cuota antes de cada llamada LLM

La Cuota SHALL evaluarse ANTES de CADA llamada al modelo (regla dura de `CLAUDE.md`). La evaluación SHALL ser una función pura sobre el consumo vigente de cada alcance, sus límites y el costo estimado del turno, sin I/O ni red. Si algún alcance no tiene margen para el costo estimado, la llamada al modelo NO SHALL emitirse.

#### Scenario: Sin margen no se emite la llamada al modelo

- **WHEN** el consumo de un alcance aplicable más el costo estimado del turno alcanza o supera su límite
- **THEN** la evaluación devuelve bloqueo, la llamada al modelo no se emite, y el turno no consume presupuesto

#### Scenario: Evaluación determinista

- **WHEN** el mismo consumo vigente, los mismos límites y el mismo costo estimado se evalúan dos veces
- **THEN** ambas evaluaciones devuelven el mismo resultado (autoriza o bloquea, y el mismo alcance bloqueante), sin depender de reloj, red ni estado externo

### Requirement: Estimación del costo con tarifas de cache hit/miss separadas

La estimación del costo del turno SHALL usar las **tarifas de cache hit/miss separadas** del perfil de modelo que atenderá el turno (contrato de `model-profiles`/`model-gateway` de `b05-gateway-modelos`), nunca una tarifa única. Tras la respuesta, el consumo real SHALL registrarse a partir de los contadores de cache hit y cache miss del `usage` (b05), reconciliando la reserva estimada con el costo efectivo.

#### Scenario: La estimación aplica ambas tarifas del perfil

- **WHEN** se estima el costo de un turno para un perfil de modelo con tarifas de cache hit y de cache miss distintas
- **THEN** la estimación aplica la tarifa hit a los tokens estimados como hit y la tarifa miss a los tokens estimados como miss, y no una tarifa promedio única

#### Scenario: El consumo real reconcilia la reserva

- **WHEN** el modelo responde y reporta contadores de cache hit y cache miss en su `usage`
- **THEN** el consumo registrado del turno se calcula con las tarifas hit/miss del perfil sobre esos contadores, reemplazando la reserva estimada previa

### Requirement: Umbral de aviso configurable al 80%

Cada Cuota con umbral de aviso SHALL emitir un aviso no intrusivo al cruzar su umbral (80% por defecto, configurable por instancia). El aviso SHALL ser informativo y NO SHALL bloquear el turno. La Cuota de alcance `sesion` puede no tener umbral de aviso (corta al 100% sin avisar), según `design/VISTAS/07-admin-operacion.md` vista 33.

#### Scenario: Aviso al cruzar el 80% sin bloquear

- **WHEN** el consumo de un usuario cruza el 80% de su Cuota (umbral configurado)
- **THEN** el sistema marca el estado de aviso para ese alcance y el turno se emite normalmente (el aviso no bloquea)

#### Scenario: Umbral configurado distinto del default

- **WHEN** una instancia configura el umbral de aviso en 90% para un alcance
- **THEN** el aviso se dispara al 90% y no al 80%

### Requirement: Bloqueo al 100% con estado QUOTA accionable

Al alcanzar el 100% de cualquier alcance aplicable, el sistema SHALL bloquear los turnos nuevos con el estado accionable `QUOTA` (`design/FUNCIONALIDADES.md` §4, `10-errores.html`), cuyo texto indica que se alcanzó el límite y que se renueva a medianoche, y que ofrece la vía de "Solicitar liberación" (capacidad `quota-releases`). El estado `QUOTA` es un código invariante y no se traduce.

#### Scenario: 100% bloquea con estado QUOTA

- **WHEN** el consumo de un alcance aplicable alcanza o supera el 100% de su límite
- **THEN** los turnos nuevos se rechazan con estado `QUOTA`, el composer queda deshabilitado y se ofrece la acción "Solicitar liberación"

#### Scenario: Cuota diaria agotada con cuota mensual sana

- **WHEN** la Cuota diaria de un usuario está al 100% pero su Cuota mensual tiene margen
- **THEN** el turno se bloquea igualmente con estado `QUOTA` (basta que un alcance aplicable no tenga margen), y el bloqueo diario manda

### Requirement: Renovación diaria a medianoche en la zona horaria de la instancia

Las Cuotas de período diario SHALL renovarse a la medianoche de la zona horaria configurada para la instancia, devolviendo el consumo del período a cero. El texto del bloqueo `QUOTA` SHALL indicar esta renovación ("se renueva a medianoche").

#### Scenario: A medianoche el consumo diario vuelve a cero

- **WHEN** transcurre la medianoche de la zona horaria de la instancia
- **THEN** el consumo del período diario de cada Cuota diaria vuelve a cero y un usuario antes bloqueado por su Cuota diaria puede volver a emitir turnos

#### Scenario: La renovación usa la zona horaria de la instancia, no UTC fija

- **WHEN** la instancia está configurada en una zona horaria distinta de UTC
- **THEN** la renovación diaria ocurre a la medianoche local de esa zona y no a la medianoche UTC

### Requirement: Consistencia bajo llamadas concurrentes cerca del límite

El registro de consumo SHALL ser atómico de modo que dos evaluaciones concurrentes cerca del límite nunca produzcan gasto doble por encima del tope. Cuando el margen restante de un alcance solo alcanza para un turno, a lo sumo una de dos llamadas concurrentes SHALL autorizarse; la otra SHALL bloquearse con estado `QUOTA`.

#### Scenario: Dos llamadas concurrentes cerca del límite no sobregastan

- **WHEN** dos turnos concurrentes del mismo alcance se evalúan estando el margen restante suficiente para uno solo
- **THEN** exactamente uno se autoriza y el otro se bloquea con estado `QUOTA`, y el consumo registrado del alcance nunca supera su límite (no hay gasto doble por encima del tope)

#### Scenario: La reserva atómica evita la condición de carrera

- **WHEN** dos evaluaciones leen el mismo consumo vigente antes de que cualquiera registre su gasto
- **THEN** el mecanismo de reserva atómica serializa el registro de consumo, de modo que la segunda observa el gasto de la primera y no puede autorizar un turno que superaría el límite

### Requirement: La Cuota es un gate independiente y adicional al Policy Gate

La evaluación de la Cuota SHALL ser un control ortogonal al Policy Gate: un turno SHALL pasar AMBOS controles para llegar al modelo. El Policy Gate autoriza la acción (usuario, tenant, skill, tool, riesgo); la Cuota autoriza el gasto. Un bloqueo por Cuota NO SHALL representarse como un `PolicyDecision`, y una acción denegada por el Policy Gate nunca llega a consumir Cuota.

#### Scenario: Acción policy-denied no consume Cuota

- **WHEN** el Policy Gate resuelve una acción con efecto `deny`
- **THEN** no se emite llamada al modelo y no se consume ni evalúa Cuota para ese turno

#### Scenario: Acción policy-allowed pero sin margen de Cuota

- **WHEN** el Policy Gate resuelve una acción con efecto `allow` pero el usuario está al 100% de un alcance aplicable
- **THEN** el turno se bloquea con estado `QUOTA` (no con un `PolicyDecision`), pese a que el Policy Gate lo autorizó
