# tool-permissions — Delta Spec (d20-gobernanza-plataforma)

> Vista de diseño: `design/VISTAS/08-admin-gobernanza.md §8.2` (`35-admin-tools`). Matrices en `design/FUNCIONALIDADES.md §11`. Alcance: solo Admin.

## ADDED Requirements

### Requirement: Vista administrativa del Tool Registry

El sistema SHALL exponer una vista administrativa del Tool Registry (definido en `c09`) que liste las Tools agrupadas por server MCP, mostrando por cada Tool su nombre, descripción, clasificación de riesgo, si requiere HITL, límites operativos (rate, timeout) y estado. La vista es de solo Admin.

#### Scenario: Listar las tools del registro por server MCP

- **WHEN** el Admin abre `35-admin-tools`
- **THEN** el sistema muestra las Tools agrupadas por su server MCP, cada una con su clasificación de riesgo, HITL, límites y estado

### Requirement: La clasificación de riesgo es visible pero no editable en runtime

La clasificación lectura/escritura/riesgo de una Tool SHALL mostrarse siempre con su palabra (LECTURA/ESCRITURA/DESTRUCTIVA) pero SHALL ser de solo lectura en runtime. Cambiar la clasificación NO SHALL ser posible desde la consola; requiere un PR sobre el Tool Manifest. Todo intento de editarla en runtime SHALL rechazarse.

#### Scenario: Intento de editar la clasificación de riesgo en runtime es rechazado

- **WHEN** el Admin intenta reclasificar una Tool (por ejemplo de ESCRITURA a LECTURA) desde la consola
- **THEN** el sistema rechaza el cambio e indica que la clasificación de riesgo solo cambia por PR sobre el Tool Manifest, no en runtime

### Requirement: HITL obligatorio en tools de escritura o destructivas

Para una Tool clasificada como escritura o destructiva, el requerimiento de HITL SHALL mostrarse marcado y bloqueado (no desmarcable en runtime), reflejando la regla dura de que las escrituras siempre pasan por aprobación humana.

#### Scenario: HITL no desmarcable en una tool de escritura

- **WHEN** el Admin abre el detalle de una Tool de escritura
- **THEN** el checkbox "Requiere HITL" aparece marcado y bloqueado, con la nota de que es regla de plataforma no configurable

### Requirement: Permisos de tools por rol y por agente

El sistema SHALL permitir configurar, como config viva en DB, qué Tools puede recibir cada rol (matriz rol×tool) sin deploy. Los cambios SHALL quedar auditados y aplicar solo a sesiones nuevas (stickiness); las sesiones en curso conservan su toolset. Un rol Funcional NUNCA SHALL poder recibir Tools destructivas.

#### Scenario: Quitar una tool a un rol aplica a sesiones nuevas

- **WHEN** el Admin desmarca una Tool para el rol Técnico habiendo sesiones activas
- **THEN** el cambio se guarda auditado, aplica a las sesiones nuevas y advierte que las sesiones en curso conservan su toolset

#### Scenario: Funcional no puede recibir tools destructivas

- **WHEN** el Admin intenta marcar una Tool destructiva para el rol Funcional
- **THEN** el sistema mantiene el checkbox bloqueado e indica el motivo

### Requirement: Matriz de visibilidad agente×rol como config viva versionada

El sistema SHALL mantener una matriz de visibilidad agente×rol (qué Agents ve cada rol) como configuración viva en DB, versionada y auditada, sin deploy. Esta matriz SHALL ser consumida por el catálogo (`d15`) para filtrar qué ve cada rol.

#### Scenario: Cambiar la visibilidad de un agente sin deploy

- **WHEN** el Admin oculta un Agent para el rol Funcional en la matriz de visibilidad
- **THEN** el cambio se persiste versionado y auditado sin deploy, y el catálogo (`d15`) deja de mostrar ese Agent al rol Funcional

### Requirement: Matriz de capacidades por vista y rol

El sistema SHALL mantener una matriz de capacidades por vista y rol (qué capa ve cada rol en cada vista) como configuración viva en DB, versionada y auditada. La semántica de cada capacidad cambia por PR; la asignación por rol es config.

#### Scenario: Ajustar la capa visible de un rol en una vista

- **WHEN** el Admin cambia qué capa ve el rol Técnico en una vista dada
- **THEN** el cambio se persiste versionado y auditado, sin deploy, y afecta lo que ese rol ve en esa vista
