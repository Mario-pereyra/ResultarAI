# user-management Specification

## Purpose
TBD - created by archiving change d11-identidad-acceso. Update Purpose after archive.
## Requirements
### Requirement: Sin registro público — el Admin es el único origen de cuentas

El sistema SHALL no exponer ninguna pantalla ni endpoint de registro público. Toda cuenta de usuario SHALL originarse en un alta ejecutada por un Admin desde la consola de gestión de usuarios.

#### Scenario: No existe ruta de auto-registro

- **WHEN** cualquier usuario, autenticado o no, intenta acceder a una ruta de registro público (frontend o API)
- **THEN** el sistema no ofrece esa ruta; no existe forma de crear una cuenta fuera de la consola de gestión de usuarios del Admin

### Requirement: Alta de cuentas por el Admin

El sistema SHALL permitir a un Admin crear una cuenta indicando nombre, correo o usuario, rol (Admin, Técnico o Funcional) y grupo. El sistema SHALL generar una contraseña temporal de un solo uso y SHALL mostrarla al Admin una única vez, en el momento de la creación.

#### Scenario: Admin crea una cuenta nueva

- **WHEN** un Admin completa el alta de usuario con nombre, usuario, rol y grupo
- **THEN** el sistema crea la cuenta, genera una contraseña temporal de un solo uso, la muestra al Admin en pantalla una única vez, y marca la cuenta para forzar el wizard de primer acceso en su primer login

#### Scenario: La contraseña temporal no puede recuperarse después de mostrarse

- **WHEN** el Admin cierra o navega fuera de la pantalla de confirmación del alta sin copiar la contraseña temporal mostrada
- **THEN** el sistema no ofrece ninguna forma de volver a mostrar esa contraseña; solo queda disponible un nuevo reset

### Requirement: Rol cerrado asignado únicamente por el Admin

El sistema SHALL restringir el rol de una cuenta a exactamente uno de Admin, Técnico o Funcional, asignado por el Admin al crear o editar la cuenta. El sistema SHALL prohibir que un usuario modifique su propio rol por cualquier vía, incluida una petición directa a la API.

#### Scenario: Admin asigna o cambia el rol de una cuenta

- **WHEN** un Admin edita una cuenta y le asigna un rol distinto entre Admin, Técnico o Funcional
- **THEN** el sistema actualiza el rol de la cuenta y ese cambio aplica desde el siguiente login de esa cuenta

#### Scenario: Un usuario no puede cambiar su propio rol

- **WHEN** una petición autenticada de un usuario no-Admin intenta modificar el campo de rol de su propia cuenta, con o sin pasar el campo en el body
- **THEN** el sistema rechaza la operación y el rol de la cuenta permanece sin cambios

### Requirement: Baja y suspensión de cuentas

El sistema SHALL permitir al Admin dar de baja o suspender una cuenta. El sistema SHALL revocar de inmediato todas las sesiones activas de una cuenta suspendida o dada de baja, y todo intento de login posterior con esa cuenta SHALL responder el mismo error genérico de credenciales inválidas del login normal.

#### Scenario: Suspensión revoca sesiones activas

- **WHEN** el Admin suspende una cuenta con sesiones activas
- **THEN** el sistema revoca de inmediato todas esas sesiones y cualquier petición posterior con ellas responde 401

#### Scenario: Login de cuenta suspendida no revela el estado de la cuenta

- **WHEN** un usuario con la cuenta suspendida intenta iniciar sesión con sus credenciales correctas
- **THEN** el sistema responde el error genérico de credenciales inválidas, igual que ante una contraseña incorrecta

### Requirement: Reset de contraseña por el Admin

El sistema SHALL permitir al Admin resetear la contraseña de cualquier cuenta. El reset SHALL generar una nueva contraseña temporal de un solo uso, mostrada al Admin una única vez, SHALL revocar todas las sesiones activas de esa cuenta, y SHALL forzar el wizard de primer acceso en el siguiente login.

#### Scenario: Reset de contraseña genera temporal y revoca sesiones

- **WHEN** el Admin ejecuta el reset de contraseña de una cuenta
- **THEN** el sistema genera una contraseña temporal de un solo uso, la muestra al Admin una única vez, revoca todas las sesiones activas de esa cuenta, y marca la cuenta para forzar el cambio de contraseña en el siguiente login

### Requirement: Revocación de sesiones por el Admin

El sistema SHALL permitir al Admin revocar la sesión de un usuario específico o todas las sesiones de un usuario, independientemente de cualquier otra acción administrativa.

#### Scenario: Admin revoca todas las sesiones de un usuario

- **WHEN** el Admin ejecuta "revocar todas las sesiones" sobre una cuenta
- **THEN** el sistema invalida de inmediato toda sesión activa de esa cuenta y cualquier petición posterior con ellas responde 401

### Requirement: Exigencia de TOTP por el Admin

El sistema SHALL permitir al Admin marcar una cuenta con rol Técnico o Funcional como TOTP-obligatorio. Una cuenta marcada así SHALL forzar el enrolamiento TOTP en su siguiente login, sin ofrecer la opción de posponerlo, hasta completarlo.

#### Scenario: Admin exige TOTP a una cuenta Técnico o Funcional

- **WHEN** el Admin marca una cuenta Técnico o Funcional como TOTP-obligatorio
- **THEN** en el siguiente login de esa cuenta el sistema fuerza el paso de enrolamiento TOTP sin la opción "configurar más tarde", igual que para una cuenta Admin

### Requirement: Autorización de la consola de gestión de usuarios

El sistema SHALL restringir el acceso a las operaciones de gestión de usuarios y grupos (alta, baja, suspensión, cambio de rol, reset, revocación, exigencia de TOTP, gestión de grupos) exclusivamente a cuentas con rol Admin.

#### Scenario: Usuario no-Admin no puede acceder a la gestión de usuarios

- **WHEN** un usuario con rol Técnico o Funcional intenta acceder a un endpoint o vista de gestión de usuarios o grupos
- **THEN** el sistema responde 403 y no ejecuta ninguna operación

### Requirement: Grupos y equipos

El sistema SHALL permitir al Admin crear grupos, asignarles un nombre, y agregar o quitar miembros. Los grupos creados aquí SHALL servir de base jerárquica para las cuotas de `d16-cuotas-liberaciones`, aunque la configuración de cuotas en sí no forma parte de este change.

#### Scenario: Admin crea un grupo y asigna miembros

- **WHEN** un Admin crea un grupo con nombre y agrega usuarios existentes como miembros
- **THEN** el sistema persiste el grupo y la membresía, disponibles para que un change posterior configure cuotas u otras políticas sobre ese grupo

#### Scenario: Admin quita un miembro de un grupo

- **WHEN** un Admin quita a un usuario de un grupo del que era miembro
- **THEN** el sistema actualiza la membresía y ese usuario deja de heredar configuración de ese grupo desde ese momento

### Requirement: Auditoría de toda mutación de identidad

El sistema SHALL registrar en el audit log append-only (`AuditEvent`) toda mutación sobre cuentas o grupos: alta, baja, suspensión, cambio de rol, reset de contraseña, revocación de sesiones, exigencia de TOTP, y alta/baja de miembros de grupo. Cada evento SHALL incluir el Admin que ejecutó la acción, la cuenta u objeto afectado, y el timestamp.

#### Scenario: Alta de usuario queda auditada

- **WHEN** un Admin da de alta una cuenta nueva
- **THEN** el sistema registra un `AuditEvent` con el Admin actor, la cuenta creada, el rol asignado y el timestamp, antes de confirmar el alta al Admin

#### Scenario: Cada tipo de mutación genera su propio evento

- **WHEN** ocurre cualquiera de: suspensión, cambio de rol, reset de contraseña, revocación de sesiones o exigencia de TOTP sobre una cuenta
- **THEN** el sistema registra un `AuditEvent` distinguible por tipo de mutación, de forma que el audit log permite reconstruir la secuencia completa de cambios sobre esa cuenta

