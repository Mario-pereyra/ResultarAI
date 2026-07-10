# usage-agreement — Delta Spec (d11-identidad-acceso)

## ADDED Requirements

### Requirement: Aceptación auditada del acuerdo de uso en el primer login

El sistema SHALL presentar el acuerdo de uso vigente como parte del wizard de primer acceso, con un checkbox de aceptación que SHALL permanecer sin marcar por defecto. El sistema SHALL bloquear el avance del wizard mientras el checkbox no esté marcado.

#### Scenario: Checkbox sin marcar bloquea el avance

- **WHEN** un usuario llega al paso del acuerdo de uso del wizard sin marcar el checkbox de aceptación
- **THEN** el botón "Aceptar y entrar" permanece deshabilitado y el sistema no permite continuar al shell

#### Scenario: Aceptación marcada habilita el avance

- **WHEN** el usuario marca el checkbox "Leí y acepto el acuerdo de uso" y confirma
- **THEN** el sistema registra la aceptación y permite continuar al paso siguiente del wizard (o al shell, si es el último paso)

### Requirement: Registro auditado de la aceptación

El sistema SHALL registrar en el audit log append-only (`AuditEvent`), para cada aceptación del acuerdo de uso, el usuario, la versión del texto aceptada y el timestamp exacto.

#### Scenario: Aceptación queda registrada con usuario, versión y timestamp

- **WHEN** un usuario acepta el acuerdo de uso
- **THEN** el sistema registra un `AuditEvent` con el identificador del usuario (derivado de la sesión, nunca del body), la versión del texto vigente en ese momento, y el timestamp de la aceptación

### Requirement: Versionado del texto del acuerdo

El sistema SHALL asociar cada aceptación a una versión identificable del texto del acuerdo de uso, y SHALL exponer cuál es la versión vigente en todo momento.

#### Scenario: Cada aceptación queda ligada a una versión concreta

- **WHEN** el sistema registra una aceptación
- **THEN** el `AuditEvent` referencia el identificador de versión del texto vigente al momento de la aceptación, no solo la fecha

### Requirement: Re-aceptación forzada ante cambio del texto

El sistema SHALL forzar la re-aceptación del acuerdo de uso a todo usuario cuya última aceptación registrada corresponda a una versión anterior a la vigente, en su próximo acceso.

#### Scenario: Cambio de versión marca a los usuarios existentes para re-aceptar

- **WHEN** se publica una nueva versión del texto del acuerdo de uso
- **THEN** todo usuario cuya aceptación registrada sea de una versión anterior queda marcado para re-aceptación en su siguiente acceso

#### Scenario: Usuario con aceptación desactualizada es interceptado en su próximo acceso

- **WHEN** un usuario con sesión válida pero aceptación de una versión anterior del acuerdo intenta acceder al shell
- **THEN** el sistema lo redirige al paso de acuerdo de uso (reutilizando el paso correspondiente del wizard) antes de permitir el acceso a cualquier otra vista

### Requirement: Bloqueo de acceso sin aceptación vigente

El sistema SHALL impedir el acceso a cualquier vista del shell distinta del propio paso de aceptación mientras un usuario no tenga registrada una aceptación de la versión vigente del acuerdo de uso.

#### Scenario: Sin aceptación vigente, solo el paso de acuerdo es accesible

- **WHEN** un usuario autenticado no tiene aceptación de la versión vigente del acuerdo de uso
- **THEN** toda ruta del shell distinta del paso de aceptación responde con una redirección al paso de acuerdo, sin exponer contenido de otras vistas
