## ADDED Requirements

### Requirement: Listado de sesiones propias con metadatos

El endpoint de listado de sesiones SHALL retornar únicamente las sesiones cuyo propietario es el usuario autenticado de la petición (el `userId` se deriva de la sesión de identidad, nunca de un parámetro), con al menos: agente asociado, título automático, fecha de última actividad, cantidad de mensajes y si la sesión tiene ramas.

#### Scenario: El listado excluye sesiones de otros usuarios

- **WHEN** un usuario autenticado solicita el listado de sus sesiones
- **THEN** el sistema retorna solo las sesiones cuyo propietario es ese usuario, ordenadas por última actividad descendente

#### Scenario: Título automático generado del primer intercambio

- **WHEN** se crea una sesión y se completa su primer turno
- **THEN** el sistema genera un título automático a partir de ese primer intercambio, editable por el usuario y que no se vuelve a regenerar tras una edición manual

### Requirement: Indicador de ramas por sesión

El listado y el detalle de una sesión SHALL exponer un contador de ramas (`branch_count`) que refleja la cantidad de puntos de bifurcación de la sesión (`design/VISTAS/02-chat.md` vista 12), sin listar las ramas como sesiones separadas.

#### Scenario: Sesión con ediciones o regeneraciones muestra su contador de ramas

- **WHEN** una sesión tiene al menos una edición de mensaje o una regeneración de respuesta
- **THEN** el listado de sesiones muestra esa sesión una sola vez con `branch_count` mayor a uno

### Requirement: Historial completo de una sesión con su árbol de ramas

El endpoint de detalle de sesión SHALL retornar el árbol completo de mensajes de la sesión (todas las ramas, con `parent_id` de cada mensaje), permitiendo reconstruir cualquier rama y su selector de versiones, sin ocultar ni omitir ramas descartadas.

#### Scenario: El detalle incluye ramas no activas

- **WHEN** se solicita el historial de una sesión que tiene una rama descartada (por ejemplo, tras "Seguir con Flash" o una edición anterior)
- **THEN** la respuesta incluye también los mensajes de esa rama, navegable aunque no sea la rama activa por defecto

### Requirement: Búsqueda por texto en historial de sesiones

El sistema SHALL exponer una búsqueda server-side sobre el título y el contenido de los mensajes de las sesiones propias del usuario, retornando coincidencias con el término resaltable en el resultado.

#### Scenario: Buscar por un término presente en un mensaje

- **WHEN** el usuario busca un término que aparece en el contenido de un mensaje de alguna de sus sesiones
- **THEN** el sistema retorna esa sesión entre los resultados, identificando el término encontrado

#### Scenario: Búsqueda sin resultados

- **WHEN** el término buscado no aparece en ningún título ni mensaje de las sesiones del usuario
- **THEN** el sistema retorna una lista vacía sin error

### Requirement: Reanudar sesión en su última rama activa

Al abrir una sesión existente desde el historial, el sistema SHALL cargar la sesión posicionada en su última rama activa, sin duplicar turnos si el stream de un mensaje seguía en curso en otra pestaña o dispositivo.

#### Scenario: Retomar una sesión abre la última rama activa

- **WHEN** el usuario abre una sesión existente desde el listado
- **THEN** el sistema carga el historial posicionado en la última rama activa de esa sesión

#### Scenario: Reconciliación sin duplicar turnos entre pestañas

- **WHEN** un turno seguía en streaming en otra pestaña y el usuario vuelve a abrir la misma sesión
- **THEN** el sistema reconcilia el estado sin crear un turno duplicado, mostrando el turno una sola vez con su estado más reciente
