# conversation-persistence — Delta Spec (b04-persistencia-postgres)

## ADDED Requirements

### Requirement: Persistencia de sesiones y mensajes vía StatePort

El adapter `persistence_postgres` SHALL implementar `StatePort` de `a03` persistiendo sesiones y mensajes en Postgres dentro de **transacciones explícitas**. Cada mensaje SHALL almacenar como mínimo: clave primaria **UUIDv7**, `session_id`, `parent_id` (nullable en el mensaje raíz), rol, contenido, `model_profile` y marca temporal. El adapter SHALL traducir hacia Postgres sin exponer detalles del motor hacia `core/`.

#### Scenario: La sesión sobrevive a un reinicio

- **WHEN** se persiste una sesión con sus mensajes y luego el proceso de la plataforma core se reinicia
- **THEN** la sesión y todos sus mensajes se recuperan íntegros vía `StatePort`, con el mismo árbol de `parent_id`

#### Scenario: Los mensajes se ordenan por clave sin depender del reloj de aplicación

- **WHEN** se persisten varios mensajes de una misma rama y se consultan ordenados por su clave primaria
- **THEN** el orden por UUIDv7 coincide con el orden temporal de inserción, sin usar un timestamp provisto por la aplicación

### Requirement: Historia append-only (branch-never-rewrite)

Un mensaje persistido SHALL ser inmutable: la base NO permite reescribir su contenido ni borrarlo. Editar un mensaje o regenerar una respuesta SHALL crear un mensaje nuevo (una rama), preservando el original. La historia JAMÁS se reescribe (branch-never-rewrite, [design/FUNCIONALIDADES.md](../../../../design/FUNCIONALIDADES.md) §14).

#### Scenario: Se rechaza mutar el contenido de un mensaje

- **WHEN** se intenta un UPDATE del contenido de un mensaje ya persistido
- **THEN** la base lo rechaza y el contenido original permanece intacto

#### Scenario: Editar un mensaje crea una rama y conserva el original

- **WHEN** el usuario edita un mensaje propio
- **THEN** se inserta un mensaje nuevo con `parent_id` apuntando al padre del editado, la rama original sigue existiendo y ningún byte del mensaje original cambia

### Requirement: Ramas mediante parent_id y selector de versiones

El árbol de mensajes SHALL soportar múltiples hijos de un mismo `parent_id` (ramas hermanas), de modo que el selector de versiones ("versión 1/2", [design/FUNCIONALIDADES.md](../../../../design/FUNCIONALIDADES.md) §4) pueda enumerarlas en el punto de bifurcación.

#### Scenario: Regenerar una respuesta crea una rama hermana enumerable

- **WHEN** se regenera una respuesta desde un punto de la conversación
- **THEN** se crea una rama hermana con el mismo `parent_id` y ambas versiones quedan disponibles para el selector, sin perder la anterior

### Requirement: Las ramas comparten adjuntos y prefijo cacheable

Al crear una rama, la persistencia SHALL reutilizar las referencias a los adjuntos y su `inserted_text` byte-idénticos del prefijo común, preservando el prefijo cacheable entre ramas (ANEXO §5).

#### Scenario: Una rama reutiliza los adjuntos del prefijo común

- **WHEN** se crea una rama a partir de un mensaje que tenía adjuntos en su prefijo
- **THEN** la rama referencia los mismos registros de adjunto y la misma `inserted_text`, sin duplicarlos ni re-procesarlos

### Requirement: Stickiness de perfil de modelo por rama

Una sesión (y cada una de sus ramas) SHALL vivir en un solo `model_profile`. Cambiar de perfil de modelo SHALL exigir una rama o sesión nueva; nunca se mezclan perfiles dentro de una misma rama. La restricción SHALL estar codificada como constraint en la base, no solo en la aplicación.

#### Scenario: Se rechaza un mensaje con perfil de modelo distinto al de la rama

- **WHEN** se intenta insertar un mensaje con un `model_profile` distinto al de su rama
- **THEN** la base lo rechaza por constraint de stickiness

#### Scenario: Cambiar de modelo abre una rama nueva

- **WHEN** el usuario cambia de perfil de modelo
- **THEN** la persistencia crea una rama (o sesión) nueva con su propio `model_profile`, sin alterar la rama anterior

### Requirement: Marcador de compactación único e inmutable en frontera de turno

El modelo de sesión SHALL registrar la compactación de contexto como un marcador inmutable en frontera de turno, ocurriendo **a lo sumo una vez** por rama ([design/FUNCIONALIDADES.md](../../../../design/FUNCIONALIDADES.md) §4 y §14). El marcador NO SHALL reescribirse ni borrarse.

#### Scenario: La compactación se registra una sola vez

- **WHEN** una rama alcanza la frontera de turno de compactación y se registra su marcador
- **THEN** el marcador queda persistido de forma inmutable y un segundo intento de registrar compactación en la misma rama es rechazado (no se duplica ni sobrescribe)
