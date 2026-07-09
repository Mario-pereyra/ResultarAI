# prompt-registry — Delta Spec (d20-gobernanza-plataforma)

> Vista de diseño: `design/VISTAS/08-admin-gobernanza.md §8.1` (`34-admin-prompts`). Flujo E2E: `design/FLUJOS.md` Flujo F. Alcance: solo Admin.

## ADDED Requirements

### Requirement: Postgres es la fuente de verdad de runtime de los prompts

El Registro de Prompts SHALL almacenar en Postgres las versiones de system prompt de cada Agent y esa base SHALL ser la única fuente de verdad de runtime. El runtime NUNCA lee el prompt activo desde Git ni desde un editor externo (Langfuse), y ninguna versión se edita "en caliente".

#### Scenario: El runtime resuelve el prompt desde el registro

- **WHEN** el `default_chat` inicia un turno nuevo y necesita su system prompt
- **THEN** el sistema resuelve la versión marcada como activa en el Registro de Prompts en Postgres, no desde `prompts/` (Git) ni desde un servicio externo

#### Scenario: Edición manual fuera del registro no tiene efecto en runtime

- **WHEN** alguien modifica el snapshot espejo en `prompts/` o un prompt en una herramienta externa sin pasar por el registro
- **THEN** el runtime ignora ese cambio y sigue usando la versión activa del registro; el cambio externo no llega a ninguna sesión

### Requirement: Las versiones publicadas son inmutables

Una versión de prompt en estado `published` SHALL ser inmutable: su contenido, su id (`default_chat@N`) y su hash de contenido (sha256) no cambian nunca. Editar una versión publicada SHALL rechazarse; la única vía es crear un `draft` nuevo a partir de ella. El sistema SHALL permitir a lo sumo un `draft` por Agent a la vez.

#### Scenario: Intento de editar una versión publicada es rechazado

- **WHEN** el Admin intenta modificar el contenido de una versión en estado `published`
- **THEN** el sistema rechaza la edición y ofrece "Crear borrador desde esta versión", que genera un `draft` nuevo sin alterar la versión publicada

#### Scenario: Un solo borrador por agente

- **WHEN** existe ya un `draft` para un Agent y el Admin intenta crear un segundo
- **THEN** el sistema rechaza la creación y ofrece abrir el `draft` existente

### Requirement: Ciclo de vida draft → published → retired

Cada versión de prompt SHALL transitar por los estados `draft`, `published` y `retired`. Un `draft` NUNCA llega a runtime. Publicar mueve `draft → published`. Una versión `retired` SHALL no poder activarse; solo puede clonarse a un `draft` nuevo.

#### Scenario: Publicar promueve el borrador a versión inmutable numerada

- **WHEN** el Admin publica un `draft` que pasó el gate de publicación
- **THEN** el sistema lo mueve a `published`, le asigna número de versión y hash inmutables, y el tab de borrador desaparece

#### Scenario: Una versión retirada no puede activarse

- **WHEN** el Admin intenta activar una versión en estado `retired`
- **THEN** el sistema rechaza la activación y solo ofrece clonarla a un `draft`

### Requirement: Diff lado a lado entre versiones

El Registro de Prompts SHALL mostrar un diff línea a línea entre dos versiones (por defecto, el `draft` en edición contra la versión activa), con las líneas removidas y agregadas tintadas.

#### Scenario: Comparar borrador contra versión activa

- **WHEN** el Admin abre un `draft` teniendo una versión activa
- **THEN** el sistema muestra el diff lado a lado (activa a la izquierda, borrador a la derecha) resaltando líneas `+`/`−`

### Requirement: Activar una versión es un update de puntero sin deploy

Activar una versión SHALL ser un update del puntero de "versión activa" del Agent, sin deploy. Los turnos y sesiones nuevos SHALL tomar la versión recién activada; las sesiones en curso SHALL conservar su versión (stickiness — no se reescriben). Toda activación SHALL exigir motivo y quedar en el Audit Log.

#### Scenario: Los chats nuevos toman la versión activada, los en curso no

- **WHEN** el Admin activa `default_chat@13` mientras hay sesiones vivas sobre `default_chat@12`
- **THEN** las sesiones nuevas usan `@13`, las sesiones en curso siguen en `@12` hasta terminar, y la activación queda auditada con su motivo

#### Scenario: Activar exige motivo

- **WHEN** el Admin confirma la activación sin escribir un motivo
- **THEN** el sistema mantiene deshabilitada la confirmación hasta que haya texto de motivo

### Requirement: Rollback con un clic, auditado

El Registro de Prompts SHALL permitir volver a activar la versión previamente activa (rollback) con un clic, sin deploy, exigiendo motivo. El rollback SHALL registrarse en el Audit Log con el de→a (por ejemplo `@13 → @12`).

#### Scenario: Rollback restaura la versión anterior sin deploy

- **WHEN** tras activar `default_chat@13` el Admin ejecuta rollback
- **THEN** el puntero vuelve a `default_chat@12` sin deploy, los chats nuevos la toman, y el evento queda en el Audit Log con de→a y motivo

### Requirement: Espejo Git automático en cada publicación

Al publicar una versión, el sistema SHALL exportar automáticamente un snapshot de su contenido a `prompts/` (espejo Git) para code review y arqueología. Este espejo es de solo lectura para el runtime: Git deja de ser la fuente de runtime.

#### Scenario: Publicar deja un snapshot en prompts/

- **WHEN** el Admin publica `default_chat@13`
- **THEN** el sistema escribe un snapshot inmutable de `default_chat@13` en `prompts/` como espejo para code review, sin que ese archivo pase a ser fuente de runtime

### Requirement: Gate de publicación pluggable con modo placeholder y modo enforcing

La publicación SHALL pasar por un gate de publicación con contrato estable desde ya. El gate SHALL operar en dos modos según si `e25-evals-gates` está archivado:

- **Modo placeholder** (mientras no exista runner de evals): un score de evals ausente NO bloquea; el sistema muestra una **advertencia visible** de que se publica sin evals y permite publicar.
- **Modo enforcing** (con `e25` archivado): la publicación SHALL bloquearse si el score de la corrida asociada al hash del `draft` es < 80% o si hay ≥1 caso `safety` en rojo; con score ≥ 80% y sin `safety` en rojo, habilita publicar.

En ambos modos, editar el `draft` después de correr evals SHALL invalidar la corrida (el gate se evalúa contra el hash del contenido).

#### Scenario: Publicar sin evals en modo placeholder muestra advertencia y publica

- **WHEN** el runner de evals no está disponible (`e25` no archivado) y el Admin publica un `draft`
- **THEN** el sistema muestra una advertencia visible "se publica sin evals" y permite completar la publicación, que queda auditada con la marca de gate en placeholder

#### Scenario: Modo enforcing bloquea por score bajo o safety en rojo

- **WHEN** `e25` está archivado y la corrida del hash del `draft` tiene score 74% o algún caso `safety` en rojo
- **THEN** el sistema deshabilita "Publicar" y muestra junto al botón el motivo (score < 80% o caso `safety` fallado), no solo como tooltip

#### Scenario: Editar el borrador invalida la corrida de evals

- **WHEN** existe una corrida de evals verde para el hash actual y el Admin edita el contenido del `draft`
- **THEN** el estado del gate vuelve a "evals pendientes" porque el hash cambió, y publicar queda bloqueado hasta correr evals sobre el hash nuevo

### Requirement: Toda acción del registro queda auditada

Cada acción sobre el Registro de Prompts (`draft-create`, `draft-edit`, `publish`, `activate`, `rollback`) SHALL generar un evento en el Audit Log append-only con quién, cuándo, qué, de→a y motivo (obligatorio en `activate` y `rollback`). La auditoría NUNCA se edita ni se borra.

#### Scenario: La auditoría registra publicación y activación

- **WHEN** el Admin publica `default_chat@13` y luego la activa
- **THEN** el Audit Log contiene dos eventos (`publish` y `activate`) con usuario, fecha-hora, versión y motivo, ambos inmutables
