# consumption-view — Delta Spec (d16-cuotas-liberaciones)

## ADDED Requirements

### Requirement: Mi consumo del día y del mes contra la Cuota

La vista **Mi consumo** (`design/VISTAS/06-mi-espacio.md` vista 23) SHALL mostrar a cada usuario su consumo del día y del mes contra sus Cuotas, con dos tarjetas (`Hoy` / `Este mes`) que muestran `usado / límite` en la unidad de presupuesto de la instancia, el porcentaje y el texto de renovación ("se renueva a medianoche" / "se renueva el dd/mm/aaaa"). El propósito es que nadie llegue al límite por sorpresa.

#### Scenario: Dos tarjetas con usado, límite y renovación

- **WHEN** un usuario abre Mi consumo
- **THEN** ve una tarjeta `Hoy` y una tarjeta `Este mes`, cada una con `usado / límite`, su porcentaje y su texto de renovación

#### Scenario: La Cuota siempre existe aunque no haya consumo

- **WHEN** un usuario nuevo sin consumo del período abre Mi consumo
- **THEN** las tarjetas muestran `0 / límite` (la Cuota siempre existe) y la tabla de sesiones muestra su estado vacío, nunca un error

### Requirement: Capa de Mi consumo por rol

Mi consumo SHALL mostrar capas distintas por Rol conforme a `design/VISTAS/06-mi-espacio.md` vista 23. **Funcional**: barras de Cuota hoy/mes (`usado / límite` y porcentaje) y sesiones recientes (agente, inicio, turnos, costo); nunca tokens, cache ni nombres de modelo. **Técnico**: lo anterior más la columna de tokens; sin anillo de cache ni hit-rate. **Admin**: lo anterior más la capa de telemetría (anillo de cache hit del mes, columna hit-rate por sesión, ahorro estimado). Lo no visible NO SHALL renderizarse (ni columnas vacías ni candados).

> Nota de diseño (vista 23): el costo en la unidad de presupuesto aparece para TODOS los roles en esta vista —incluido Funcional— porque la Cuota se define en presupuesto y la barra `usado / límite` sería ilegible sin la cifra; la regla "Funcional no ve costos" aplica a la experiencia de chat, no a esta página. Funcional jamás ve tokens, cache ni modelos.

#### Scenario: Funcional ve la barra de Cuota sin tokens ni modelos

- **WHEN** un usuario con Rol Funcional abre Mi consumo
- **THEN** ve las barras de Cuota `usado / límite` con su porcentaje y las sesiones con costo, y NO ve columna de tokens, anillo de cache, hit-rate ni nombres de modelo

#### Scenario: Técnico ve tokens pero no la telemetría de cache

- **WHEN** un usuario con Rol Técnico abre Mi consumo
- **THEN** ve la columna de tokens en las sesiones y NO ve el anillo de cache ni la columna hit-rate (telemetría agregada exclusiva de Admin)

#### Scenario: Admin ve la capa de telemetría de cache

- **WHEN** un usuario con Rol Admin abre Mi consumo
- **THEN** ve, además de lo anterior, el anillo de cache hit del mes, la columna hit-rate por sesión y el ahorro estimado

### Requirement: Estados de aviso y bloqueo reflejados en Mi consumo

Las barras de Cuota SHALL reflejar el estado del alcance: normal (<80%), aviso (≥80%, `is-warn`) y bloqueado (≥100%, `is-over`), coherente con el aviso del composer del chat. Un cambio de estado que ocurra con la vista abierta (por ejemplo 79%→80%) SHALL anunciarse por `aria-live` "polite" (WCAG 2.1 AA). En estado bloqueado SHALL ofrecerse la acción "Solicitar liberación" y, si ya hay una Liberación en curso, su estado en lugar del botón.

#### Scenario: La barra pasa a aviso con la vista abierta

- **WHEN** el consumo cruza el 80% mientras el usuario tiene Mi consumo abierto
- **THEN** la barra pasa al estado de aviso (`is-warn`) y el cambio se anuncia por `aria-live` "polite" sin robar el foco

#### Scenario: En bloqueo aparece la acción de Liberación

- **WHEN** un alcance de la Cuota del usuario está al 100% y no hay Liberación en curso
- **THEN** Mi consumo muestra el estado bloqueado y la acción "Solicitar liberación"; si ya hay una Liberación `pendiente`, muestra su estado en lugar del botón

### Requirement: Mis solicitudes de Liberación con su estado

Mi consumo SHALL mostrar el estado de las Liberaciones que el propio usuario pidió: `pendiente`, `concedida` o `denegada`, con la decisión y el motivo visibles (`design/FUNCIONALIDADES.md` §10, vista 23). Una Liberación concedida SHALL reflejarse en la barra recalculada con el límite ampliado; una denegada SHALL mostrar el comentario del Admin.

#### Scenario: Solicitud enviada queda pendiente y confirma

- **WHEN** el usuario envía una Liberación desde el bloqueo
- **THEN** ve una confirmación de envío y el estado `pendiente` ("enviada hace …"), sin poder duplicar el envío mientras siga pendiente

#### Scenario: Concedida recalcula la barra; denegada muestra el motivo

- **WHEN** el Admin resuelve la Liberación del usuario
- **THEN** si fue concedida, la barra se recalcula con el límite ampliado y se marca `concedida`; si fue denegada, se marca `denegada` y se muestra el comentario del Admin

### Requirement: Mi consumo es estrictamente personal

Mi consumo SHALL mostrar únicamente el consumo y las Liberaciones del usuario autenticado. Ningún usuario SHALL ver el consumo de otro desde esta vista; la agregación por usuario o grupo vive en la consola Admin (`d19-admin-operacion`).

#### Scenario: Un usuario nunca ve el consumo de otro

- **WHEN** el usuario A abre Mi consumo
- **THEN** solo ve su propio consumo y sus propias Liberaciones; ninguna fila, tarjeta ni solicitud de otro usuario aparece
