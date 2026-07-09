# instance-config — Delta Spec (d20-gobernanza-plataforma)

> Vista de diseño: `design/VISTAS/08-admin-gobernanza.md §8.5` (`40-admin-instancia`). Política de instancia en `design/FUNCIONALIDADES.md §11` (Retención y políticas de instancia). Alcance: solo Admin.

## ADDED Requirements

### Requirement: Todo default operativo es configuración de instancia

El sistema SHALL tratar los valores por defecto operativos (branding, retención de adjuntos, límites de attachments, idioma default, umbrales de cuota, tiempo de vida de tarjetas HITL) como **configuración de instancia** persistida en DB, no como constantes de código. Cada cambio de configuración de instancia SHALL quedar en el Audit Log (quién, cuándo, de→a).

#### Scenario: Un default se lee de la configuración de instancia, no del código

- **WHEN** un módulo necesita un valor por defecto (por ejemplo la retención de adjuntos)
- **THEN** el sistema lo lee de la configuración de instancia en DB, y modificarlo desde la consola no requiere cambiar código

#### Scenario: Cambiar la configuración queda auditado

- **WHEN** el Admin guarda un cambio de configuración de instancia
- **THEN** el cambio se persiste y queda en el Audit Log con usuario, fecha-hora y de→a

### Requirement: Branding de instancia (brand, logo, nombre)

El sistema SHALL permitir configurar el branding de la instancia: nombre de instancia, logo (versión clara y oscura, o una marcada "sirve para ambos") y brand (`default` o `totvs`). El brand SHALL ser configuración de instancia (no preferencia personal); los temas claro/oscuro personales de cada usuario SHALL conservarse al cambiar el brand. El cambio SHALL aplicar a todos los usuarios al recargar.

#### Scenario: Cambiar el brand conserva los temas personales

- **WHEN** el Admin cambia el brand de `default` a `totvs` y guarda
- **THEN** el brand aplica a todos los usuarios al recargar, mientras cada usuario conserva su preferencia personal de tema claro/oscuro

#### Scenario: El logo exige versión clara y oscura

- **WHEN** el Admin sube un logo
- **THEN** el sistema exige una versión clara y una oscura (o una sola marcada "sirve para ambos") y muestra el preview del shell en dark y light

### Requirement: Retención de adjuntos y límites de attachments configurables

El sistema SHALL permitir configurar la retención de adjuntos (días) y los límites de attachments (tamaño y cantidad) como configuración de instancia. Estos valores SHALL gobernar el comportamiento del pipeline de attachments (`d14`) sin deploy.

#### Scenario: Ajustar la retención de adjuntos

- **WHEN** el Admin cambia la retención de adjuntos de 90 a 30 días y guarda
- **THEN** el nuevo valor rige la retención sin deploy y queda auditado

### Requirement: Idioma default, umbral de cuota y TTL de tarjetas HITL

El sistema SHALL permitir configurar el idioma default de la instancia, el umbral de aviso de cuota (por defecto 80%) y el tiempo de vida (TTL) de las tarjetas HITL. El idioma default SHALL aplicar solo a usuarios nuevos o sin preferencia. El umbral de cuota SHALL ser consumido por el motor de cuotas (`d16`) y el TTL por las tarjetas HITL (`d17`).

#### Scenario: El idioma default solo afecta a usuarios sin preferencia

- **WHEN** el Admin cambia el idioma default de la instancia
- **THEN** el cambio aplica a usuarios nuevos o sin preferencia, sin sobreescribir la preferencia de idioma de los usuarios existentes

#### Scenario: El umbral de cuota configurado gobierna el aviso

- **WHEN** el Admin fija el umbral de aviso de cuota en 90%
- **THEN** el motor de cuotas (`d16`) emite el aviso al 90% en vez del 80% por defecto, sin deploy

### Requirement: Regional y datos de licenciatario

El sistema SHALL permitir configurar los datos regionales (zona horaria IANA, formato de moneda) y de licenciatario (razón social, NIT, contacto) de la instancia. El `instancia-id` SHALL mostrarse de solo lectura.

#### Scenario: Configurar zona horaria y ver instancia-id de solo lectura

- **WHEN** el Admin abre la configuración regional y de licenciatario
- **THEN** puede editar zona horaria, moneda y datos del licenciatario, mientras el `instancia-id` se muestra de solo lectura y copiable
