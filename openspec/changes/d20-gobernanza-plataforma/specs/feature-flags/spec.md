# feature-flags — Delta Spec (d20-gobernanza-plataforma)

> Vista de diseño: `design/VISTAS/08-admin-gobernanza.md §8.4` (`38-admin-flags`). Flujo E2E: `design/FLUJOS.md` Flujo I (kill-switch). Alcance: solo Admin.

## ADDED Requirements

### Requirement: Tabla de feature flags con scope

El sistema SHALL exponer una tabla de feature flags con clave (identificador, no traducible), descripción, scope (`global`, `agente`, `rol`) y estado on/off, para encender o apagar capacidades sin deploy. Cada cambio de flag SHALL quedar en el Audit Log (quién, cuándo, de→a) y mostrarse inline. Los cambios concurrentes SHALL resolverse con optimistic lock.

#### Scenario: Cambiar un flag sin deploy queda auditado

- **WHEN** el Admin conmuta `workflows.enabled` de off a on
- **THEN** la capacidad se habilita sin deploy y el cambio queda en el Audit Log con usuario, fecha-hora y de→a, visible inline

#### Scenario: Cambio concurrente rechazado por optimistic lock

- **WHEN** otro Admin cambió el mismo flag entre la carga y el clic del Admin actual
- **THEN** el sistema rechaza el cambio con "el flag cambió hace un momento — recargá" y no aplica un estado mentiroso

### Requirement: Ninguna regla dura es controlable por flag

El sistema SHALL garantizar que ningún feature flag pueda desactivar una regla dura de plataforma: no existe flag para apagar HITL en escrituras ni para habilitar SQL libre contra el ERP. Esa ausencia es deliberada.

#### Scenario: No existe flag para desactivar HITL

- **WHEN** el Admin busca un flag que apague la aprobación HITL de escrituras o que permita SQL libre
- **THEN** el sistema no ofrece tal flag; esas reglas duras no son flageables

### Requirement: Kill-switch por agente con apagado efectivo en menos de un minuto

El sistema SHALL ofrecer un kill-switch por Agent que lo apague de forma efectiva en **menos de 1 minuto y sin deploy**. Apagar un Agent es una acción crítica: SHALL exigir confirmación con **motivo obligatorio** antes de aplicarse.

#### Scenario: Apagar un agente exige motivo y aplica en menos de un minuto

- **WHEN** el Admin apaga un Agent desde `38-admin-flags`
- **THEN** el sistema exige un motivo obligatorio (confirmación deshabilitada sin texto) y, al confirmar, el corte queda efectivo en menos de 1 minuto sin deploy

### Requirement: Efectos coordinados del kill-switch de agente

Cuando un Agent queda apagado, el sistema SHALL aplicar todos estos efectos: (1) rechazar los turnos nuevos hacia ese Agent; (2) dejar terminar o abortar con aviso los streams en curso; (3) **congelar las tarjetas HITL** pendientes de ese Agent marcándolas "agente suspendido" (contrato con `d17`); (4) mostrar el Agent como "No disponible temporalmente" en el catálogo (contrato con `d15`); (5) notificar a los usuarios con sesiones activas vía el centro de notificaciones (contrato con `d12`). Todos los efectos SHALL quedar auditados.

#### Scenario: Kill-switch congela tarjetas HITL y deshabilita el agente en el catálogo

- **WHEN** el Admin apaga un Agent con tarjetas HITL pendientes y sesiones activas
- **THEN** las tarjetas HITL de ese Agent quedan congeladas con estado "agente suspendido", el catálogo lo muestra "No disponible temporalmente", se rechazan turnos nuevos, se notifica a los usuarios con sesiones activas y el evento queda en el Audit Log

#### Scenario: Los usuarios ven un estado accionable sin jerga interna

- **WHEN** un usuario Funcional con un chat abierto envía un mensaje hacia el Agent apagado
- **THEN** el sistema responde con un estado accionable ("Este agente está en mantenimiento. Tu conversación quedó guardada.") sin exponer detalles internos

### Requirement: Kill-switch por tool

El sistema SHALL ofrecer un kill-switch por Tool que la desactive sin deploy. Al desactivarla, las sesiones en curso SHALL ver la Tool fallar con un estado `TOOL_DISABLED`; los Agents cuya versión la incluye en su toolset SHALL seguir declarándola (el toolset es fijo por versión de Agent). Desactivar SHALL exigir motivo.

#### Scenario: Desactivar una tool la hace fallar en sesiones en curso

- **WHEN** el Admin desactiva una Tool con motivo
- **THEN** las sesiones que la invoquen la ven fallar con `TOOL_DISABLED`, el toolset horneado en cada versión de Agent la sigue declarando, y el cambio queda auditado

### Requirement: Reactivación restaura y notifica

Reactivar un Agent o una Tool apagados SHALL restaurar su operación (catálogo disponible, tarjetas HITL descongeladas, turnos aceptados) y SHALL notificar la vuelta al servicio a los usuarios afectados. La reactivación SHALL quedar auditada.

#### Scenario: Reactivar un agente restaura catálogo y notifica

- **WHEN** el Admin reactiva un Agent previamente apagado
- **THEN** el catálogo vuelve a mostrarlo disponible, las tarjetas HITL congeladas se descongelan, los turnos nuevos se aceptan, se notifica a los usuarios y la reactivación queda en el Audit Log

### Requirement: El kill-switch es el complemento runtime del status deprecated

El kill-switch operativo SHALL ser coherente con el ciclo de vida de manifiestos (`a02`): es el complemento **runtime** del status `deprecated` de un Manifest. Apagar por kill-switch NO reescribe el Manifest ni su status; corta la ejecución en runtime de forma reversible.

#### Scenario: Kill-switch no altera el manifiesto

- **WHEN** el Admin apaga un Agent por kill-switch
- **THEN** el Manifest del Agent y su status en el registro quedan intactos; solo el runtime queda cortado y es reversible al reactivar
