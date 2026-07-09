## ADDED Requirements

### Requirement: Definición versionada e inmutable de un Workflow

Un `WorkflowDefinition` SHALL identificarse por `slug` + `version` (p. ej. `informe-adjunto@1.0`) y SHALL ser inmutable una vez publicada: pasos, orden de pasos e inputs tipados declarados quedan fijos para esa versión. Publicar un cambio de pasos, orden o inputs SHALL requerir una `version` nueva, nunca editar la versión activa.

#### Scenario: Publicar una versión nueva no altera la anterior

- **WHEN** se publica `informe-adjunto@1.1` con un paso adicional
- **THEN** `informe-adjunto@1.0` sigue existiendo sin cambios y las Corridas ya creadas contra `1.0` conservan sus pasos originales

#### Scenario: La versión activa no se edita en el lugar

- **WHEN** se intenta modificar los pasos o los inputs de una `WorkflowDefinition` ya publicada sin cambiar su `version`
- **THEN** el registro rechaza el cambio: solo una `version` nueva puede declarar pasos o inputs distintos

### Requirement: Determinismo entre Corridas de una misma versión

Para una misma `version` de un Workflow, el orden y la identidad de los pasos SHALL ser idéntico en cada Corrida: el orden de ejecución no lo decide el LLM ni ninguna condición dinámica del contenido procesado.

#### Scenario: Misma versión produce siempre los mismos pasos en el mismo orden

- **WHEN** se ejecutan dos Corridas distintas de `informe-adjunto@1.0` con inputs diferentes
- **THEN** ambas Corridas exponen la misma lista de pasos, en el mismo orden e índice (`n de N`), independientemente del contenido de los inputs o del resultado de un paso anterior

### Requirement: Contrato de Paso — tipos permitidos

Un `WorkflowStep` SHALL ser de exactamente uno de tres tipos: llamada LLM (invoca `LLMPort`), Tool (invoca una Tool ya declarada en el Tool Registry de `c09-mcp-tools`, vía Skill) o pausa HITL (un paso de escritura que el Policy Gate resuelve con `escalate_hitl`). Ningún otro tipo de paso SHALL existir en esta etapa.

#### Scenario: Paso de tipo no soportado es rechazado

- **WHEN** se intenta registrar una `WorkflowDefinition` con un paso cuyo tipo no es `llm`, `tool` ni `hitl_pause`
- **THEN** el registro rechaza la definición antes de publicarla

#### Scenario: Paso de tipo Tool solo invoca Tools ya registradas

- **WHEN** un paso de tipo Tool referencia un identificador de Tool
- **THEN** ese identificador SHALL corresponder a una Tool con `ToolManifest` activo en el Tool Registry (`c09-mcp-tools`); si no existe o no está activa, la `WorkflowDefinition` no se publica

### Requirement: Registro de Workflows por código, sin manifiesto YAML ni builder visual

Un `WorkflowDefinition` SHALL declararse en código Python dentro de `core/orchestration/workflows/` y publicarse mediante el `WorkflowRegistry`, sin manifiesto YAML propio y sin ninguna consola de creación o edición visual. Publicar o modificar un Workflow SHALL requerir un cambio de código revisado por PR.

#### Scenario: No existe ruta de creación visual

- **WHEN** se audita la superficie de producto de este change
- **THEN** ninguna vista permite crear, editar pasos o versionar un Workflow desde la interfaz; la única vía es el `WorkflowRegistry` cargado desde código

#### Scenario: El registro expone solo Workflows con status publicado

- **WHEN** el `WorkflowRegistry` construye el catálogo consultable
- **THEN** solo aparecen las versiones de `WorkflowDefinition` marcadas como publicadas; una versión en desarrollo no es visible ni ejecutable

### Requirement: Máquina de estados del Paso

Cada paso de una Corrida SHALL transitar exclusivamente entre los estados `pendiente`, `en curso`, `completado`, `fallido` y `esperando aprobación`, en ese orden causal: `pendiente → en curso → (completado | fallido | esperando aprobación)`. Un paso ya `completado` SHALL no volver a ejecutarse dentro de la misma Corrida.

#### Scenario: Un paso completado no se re-ejecuta

- **WHEN** un paso 3 falla y la Corrida se reintenta desde ese punto
- **THEN** los pasos 1 y 2, ya `completado`, no vuelven a ejecutarse; la Corrida continúa desde el paso 3

#### Scenario: Transición inválida es rechazada

- **WHEN** se intenta mover un paso directamente de `pendiente` a `completado` sin pasar por `en curso`
- **THEN** la máquina de estados pura rechaza la transición

### Requirement: Máquina de estados de la Corrida

Una Corrida (`WorkflowRun`) SHALL transitar entre `configurando`, `en ejecución`, `esperando aprobación` (solo alcanzable y solo retornable hacia `en ejecución`) y los estados terminales `completada`, `fallida` y `cancelada`. Ningún estado terminal SHALL transicionar a otro estado.

#### Scenario: Estado terminal es definitivo

- **WHEN** una Corrida alcanza el estado `completada`
- **THEN** ninguna acción posterior la mueve a `en ejecución`, `fallida` ni `cancelada`; una nueva ejecución exige una Corrida nueva

#### Scenario: Pausa por HITL retorna solo a en ejecución

- **WHEN** una Corrida en `esperando aprobación` recibe la aprobación del paso pausado
- **THEN** la Corrida vuelve a `en ejecución` y continúa desde el paso siguiente al pausado

### Requirement: Listado de workflows según matriz workflow×rol

El listado de workflows SHALL mostrar únicamente las versiones publicadas visibles para el rol del usuario autenticado, según la misma lógica de matriz de visibilidad que `agent-visibility` (`d15-catalogo-agentes`): default Técnico+Admin cuando no hay override explícito de la instancia. Un rol sin ningún workflow habilitado SHALL no ver la entrada "Workflows" en la navegación.

#### Scenario: Rol sin workflows habilitados no ve la sección

- **WHEN** el rol Funcional no tiene ningún workflow habilitado por configuración de instancia
- **THEN** la entrada "Workflows" no aparece en la navegación de ese usuario

#### Scenario: Listado respeta la visibilidad por rol

- **WHEN** un usuario Técnico consulta el listado y la instancia habilita 3 workflows para Técnico y 5 para Admin
- **THEN** el listado devuelve exactamente los 3 workflows habilitados para Técnico

### Requirement: Ficha de workflow con capa técnica restringida

Cada workflow del listado SHALL mostrar, para todo rol con visibilidad: nombre, qué produce, cantidad de pasos, inputs requeridos y owner. Costo estimado por Corrida y versión activa (identificador `slug@version`) SHALL mostrarse únicamente a Técnico y Admin.

#### Scenario: Funcional no ve costo estimado ni versión

- **WHEN** un usuario Funcional con visibilidad abre el listado
- **THEN** cada card muestra qué produce, pasos e inputs, pero no muestra costo estimado ni el identificador de versión

#### Scenario: Técnico ve la capa técnica completa

- **WHEN** un usuario Técnico abre el listado
- **THEN** cada card muestra además el costo estimado por Corrida y la versión activa en formato `slug@version`

### Requirement: Formulario tipado validado antes de ejecutar

Antes de crear una Corrida, el formulario SHALL validar todos los inputs tipados declarados por la versión activa de la `WorkflowDefinition`; la Corrida SHALL no crearse mientras falte un input obligatorio o un archivo esperado. El botón de ejecutar SHALL permanecer deshabilitado con el motivo visible de qué falta.

#### Scenario: Ejecutar deshabilitado con motivo visible

- **WHEN** el formulario tiene un input obligatorio vacío
- **THEN** el botón de ejecutar está deshabilitado y un texto junto a él enumera qué falta, sin dejar un botón inerte sin explicación

#### Scenario: Formulario válido crea la Corrida en configurando

- **WHEN** todos los inputs obligatorios y archivos esperados están completos y se confirma
- **THEN** se crea una Corrida en estado `configurando` con los parámetros congelados y transiciona a `en ejecución`

### Requirement: Archivos esperados con tipo, posición y presupuesto fijados por el workflow

Cada archivo esperado que declara una `WorkflowDefinition` SHALL fijar su tipo permitido, el paso en el que su contenido extraído se inyecta (posición) y el presupuesto de tokens/tamaño de esa extracción; el usuario SHALL no poder alterar esos parámetros desde el formulario. La extracción SHALL reutilizar el pipeline de `d14-attachments` (validación de magic bytes, sanitización, escaneo N2/N3).

#### Scenario: Archivo fuera del tipo declarado es rechazado

- **WHEN** el workflow declara un archivo esperado de tipo `xlsx` y el usuario adjunta un `.pdf`
- **THEN** el formulario rechaza el archivo con un motivo accionable, sin crear la Corrida

#### Scenario: El usuario no puede cambiar la posición ni el presupuesto de extracción

- **WHEN** un archivo esperado válido se adjunta
- **THEN** su contenido extraído se inyecta en el paso y con el presupuesto que la `WorkflowDefinition` fija, sin control de usuario sobre esos parámetros

### Requirement: Ejecución en vivo con estado por paso y streaming de progreso

La vista de ejecución SHALL mostrar el estado de cada paso (`pendiente`, `en curso`, `completado`, `fallido`, `esperando aprobación`) actualizado por streaming mientras la Corrida avanza. Si la conexión de streaming se interrumpe, la Corrida SHALL continuar en el servidor y la vista SHALL re-sincronizarse al reconectar, sin perder progreso.

#### Scenario: El estado de cada paso se actualiza en vivo

- **WHEN** un paso pasa de `pendiente` a `en curso` en el servidor
- **THEN** la vista de ejecución conectada por streaming refleja ese cambio sin recargar la página

#### Scenario: La Corrida continúa si la vista se desconecta

- **WHEN** la conexión de streaming se cae mientras un paso está `en curso`
- **THEN** la Corrida sigue avanzando en el servidor y, al reconectar, la vista se re-sincroniza con el estado real de todos los pasos

### Requirement: Pausa HITL en el paso de escritura reutiliza la Tarjeta HITL

Un paso de tipo pausa HITL SHALL invocar la Tool de escritura vía Policy Gate; cuando el Policy Gate resuelva la acción con `PolicyDecision.effect = escalate_hitl`, el paso SHALL transicionar a `esperando aprobación` y la Corrida a `esperando aprobación`, mostrando la **misma Tarjeta HITL** que `d17-hitl-aprobaciones` (mismo componente, mismas reglas: expiración = rechazo automático auditado, segunda aprobación en acciones irreversibles). Este change SHALL no reimplementar ni duplicar la Tarjeta HITL.

#### Scenario: El paso de escritura declara la decisión escalate_hitl del Policy Gate

- **WHEN** el paso de tipo pausa HITL invoca la Tool de escritura simulada
- **THEN** el `PolicyDecision` resuelto tiene efecto `escalate_hitl`, el paso queda en `esperando aprobación` y se crea la misma Solicitud de aprobación que consume `d17-hitl-aprobaciones`

#### Scenario: Aprobación reanuda la Corrida en el paso siguiente

- **WHEN** la Tarjeta HITL asociada al paso pausado se aprueba
- **THEN** el paso pasa a `completado`, la Corrida vuelve a `en ejecución` y continúa con el paso siguiente

#### Scenario: Expiración de la tarjeta es rechazo auditado y falla el paso

- **WHEN** la Tarjeta HITL asociada al paso pausado expira sin decisión
- **THEN** se registra un rechazo automático auditado (`d17-hitl-aprobaciones`), el paso pasa a `fallido` y la Corrida pasa a `fallida`

### Requirement: Evaluación de cuota antes de cada paso de llamada LLM

Antes de emitir cada paso de tipo llamada LLM, el motor de Workflows SHALL evaluar la cuota vigente del usuario (`d16-cuotas-liberaciones`) con la misma estimación de tarifas hit/miss que el chat. Si la cuota no alcanza, el paso SHALL no emitirse: la Corrida queda en `fallida` con el estado `QUOTA` accionable, nunca a mitad de una llamada sin aviso.

#### Scenario: Cuota insuficiente antes de un paso LLM detiene la Corrida

- **WHEN** un paso de tipo llamada LLM va a emitirse y la cuota del usuario ya está en 100%
- **THEN** el paso no se emite, la Corrida pasa a `fallida` con estado `QUOTA` y un CTA para solicitar liberación o ver consumo

#### Scenario: Cuota suficiente permite continuar

- **WHEN** un paso de tipo llamada LLM va a emitirse y la cuota del usuario tiene margen
- **THEN** la llamada se emite normalmente y el consumo del paso se descuenta de la cuota

### Requirement: Trazas por Corrida

Cada Corrida y cada uno de sus pasos SHALL emitir eventos vía `TracePort` (`b07-observabilidad`), de modo que una Corrida completa —incluidos sus pasos LLM, Tool y pausa HITL— sea reconstruible como una traza única con costo y duración por paso.

#### Scenario: Una Corrida es reconstruible por su traza

- **WHEN** una Corrida completa termina en `completada`
- **THEN** existe una traza que permite reconstruir, en orden, cada paso ejecutado, su duración, su costo (si aplica) y las decisiones del Policy Gate involucradas

### Requirement: Resultado descargable asociado a la Corrida

Al completarse, una Corrida SHALL generar un artefacto de resultado descargable (xlsx o md, generado server-side) asociado de forma permanente a esa Corrida. El resultado SHALL incluir trazabilidad mínima: quién ejecutó, cuándo, con qué inputs y (Técnico/Admin) costo de la Corrida.

#### Scenario: El resultado queda disponible tras completar

- **WHEN** la última tarea de una Corrida se completa
- **THEN** un artefacto descargable (xlsx o md) queda asociado a esa Corrida y accesible desde su vista de resultado y desde el historial

#### Scenario: Corrida fallida no genera resultado completo

- **WHEN** una Corrida termina en `fallida`
- **THEN** no se genera el artefacto de resultado completo; la vista de resultado muestra el estado de error con enlace al paso que falló

### Requirement: Notificación al finalizar, fallar o cancelar una Corrida

Al alcanzar cualquier estado terminal (`completada`, `fallida`, `cancelada`), la Corrida SHALL emitir, vía el contrato genérico de `d12-notificaciones`, una notificación al usuario dueño de la Corrida con el tipo correspondiente y un deep link a su resultado o detalle.

#### Scenario: Notificación al completar con la vista cerrada

- **WHEN** una Corrida termina en `completada` mientras el usuario tiene la pestaña cerrada
- **THEN** se emite una notificación con deep link al resultado, visible la próxima vez que el usuario abre la plataforma

#### Scenario: Notificación distingue el estado terminal alcanzado

- **WHEN** una Corrida termina en `fallida` o en `cancelada`
- **THEN** la notificación emitida usa el tipo correspondiente a ese estado, distinto del tipo usado para `completada`

### Requirement: Historial de Corridas con visibilidad propia y de Admin

El historial SHALL listar las Corridas propias del usuario (inputs, estado, resultado si existe, costo si Técnico/Admin); el rol Admin SHALL además poder ver las Corridas de cualquier usuario. Ningún rol distinto de Admin SHALL ver Corridas ajenas.

#### Scenario: Usuario no-Admin solo ve sus propias Corridas

- **WHEN** un usuario Técnico consulta el historial
- **THEN** solo aparecen las Corridas que él mismo inició, nunca las de otro usuario

#### Scenario: Admin ve todas las Corridas

- **WHEN** un usuario Admin consulta el historial
- **THEN** puede ver y filtrar las Corridas de cualquier usuario de la instancia

### Requirement: Re-ejecución crea una Corrida nueva con inputs precargados

"Re-ejecutar" sobre una Corrida terminada SHALL precargar el formulario con los mismos inputs (incluidos los archivos, si aún existen) de la Corrida original y, al confirmar, SHALL crear una **Corrida nueva**; la Corrida original SHALL permanecer sin cambios en el historial.

#### Scenario: Re-ejecutar no sobrescribe la Corrida original

- **WHEN** el usuario re-ejecuta una Corrida completada con los mismos inputs
- **THEN** se crea una Corrida nueva con su propio identificador y la Corrida original sigue visible e inalterada en el historial

#### Scenario: Re-ejecutar con versión de workflow cambiada lo advierte

- **WHEN** el usuario re-ejecuta una Corrida cuya `WorkflowDefinition` tiene hoy una `version` activa distinta a la usada originalmente
- **THEN** el formulario precargado muestra una advertencia indicando que la Corrida nueva usará la versión activa actual, distinta de la original

### Requirement: Cancelación auditada sin reversión automática

El dueño de una Corrida o un Admin SHALL poder cancelar una Corrida en `en ejecución` o `esperando aprobación`. Al cancelar, el paso en curso se detiene, los pasos ya `completado` quedan registrados tal cual (nada se revierte automáticamente) y la Corrida pasa a `cancelada`; la cancelación SHALL producir un `AuditEvent`.

#### Scenario: Cancelar detiene sin revertir lo ya ejecutado

- **WHEN** se cancela una Corrida con 2 pasos ya `completado` y un tercero `en curso`
- **THEN** los 2 pasos completados permanecen registrados sin cambios, el paso en curso se detiene y la Corrida pasa a `cancelada`

#### Scenario: Cancelar con pausa HITL pendiente retira la solicitud

- **WHEN** se cancela una Corrida que está en `esperando aprobación`
- **THEN** la Solicitud de aprobación asociada se retira, quedando registrado el evento en el audit log, y la Corrida pasa a `cancelada`

#### Scenario: Cancelación queda auditada

- **WHEN** cualquier Corrida se cancela
- **THEN** se produce un `AuditEvent` con usuario, timestamp y estado de los pasos al momento de cancelar

### Requirement: Workflow de ejemplo de fábrica end-to-end

La plataforma SHALL publicar de fábrica un Workflow genérico sin ERP —"Generar informe a partir de un adjunto"— con exactamente tres pasos fijos: (1) lectura/extracción del adjunto declarado como input, (2) llamada LLM que produce un informe a partir del contenido extraído, (3) Tool de escritura simulada del MCP Server de ejemplo (`c09-mcp-tools`) que dispara la pausa HITL. Este Workflow SHALL demostrar el ciclo completo: formulario → pasos en vivo → pausa HITL → resultado descargable → historial.

#### Scenario: El workflow de ejemplo corre de punta a punta con una pausa HITL

- **WHEN** un usuario habilitado completa el formulario del workflow de ejemplo con un adjunto válido y ejecuta
- **THEN** el paso de lectura y el paso LLM se completan en orden, el paso de escritura simulada pausa la Corrida con la Tarjeta HITL, y al aprobar la Corrida se completa con un resultado descargable asociado

#### Scenario: Rechazar la pausa dentro del ejemplo termina la Corrida como fallida

- **WHEN** la Tarjeta HITL del paso de escritura simulada del workflow de ejemplo se rechaza
- **THEN** el paso queda `fallido`, la Corrida pasa a `fallida` y se emite la notificación de workflow fallido
