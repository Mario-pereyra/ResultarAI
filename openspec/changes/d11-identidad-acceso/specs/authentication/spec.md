# authentication — Delta Spec (d11-identidad-acceso)

## ADDED Requirements

### Requirement: Login local con usuario y contraseña

El sistema SHALL autenticar usuarios contra un usuario y una contraseña almacenados localmente (sin SSO, sin LDAP). El sistema SHALL verificar la contraseña contra el hash Argon2id almacenado usando la librería mantenida decidida en ADR-0008; nunca contra texto plano ni una implementación criptográfica propia.

#### Scenario: Login exitoso

- **WHEN** un usuario envía usuario y contraseña correctos
- **THEN** el sistema crea una sesión server-side y responde con éxito

#### Scenario: Login fallido con contraseña incorrecta

- **WHEN** un usuario envía un usuario existente con contraseña incorrecta
- **THEN** el sistema responde con un error genérico de credenciales inválidas, sin indicar cuál de los dos campos falló

#### Scenario: Login fallido con usuario inexistente

- **WHEN** un usuario envía un nombre de usuario que no existe en el sistema
- **THEN** el sistema responde exactamente el mismo error genérico de credenciales inválidas que ante una contraseña incorrecta, sin revelar que la cuenta no existe

#### Scenario: Login de cuenta suspendida o deshabilitada

- **WHEN** un usuario con la cuenta suspendida por el Admin envía credenciales correctas
- **THEN** el sistema responde el mismo error genérico de credenciales inválidas, sin revelar que la cuenta está suspendida

### Requirement: Hash de contraseñas con Argon2id

El sistema SHALL almacenar contraseñas exclusivamente como hash Argon2id con parámetros de costo vigentes según las recomendaciones actuales (OWASP Password Storage Cheat Sheet), generados y verificados por la librería mantenida elegida en ADR-0008. El sistema SHALL prohibir cualquier esquema de hashing o comparación criptográfica implementado a mano.

#### Scenario: Alta o reset genera hash Argon2id vigente

- **WHEN** se crea una cuenta o se resetea una contraseña
- **THEN** el sistema deriva y almacena un hash Argon2id con los parámetros de costo configurados como vigentes, y nunca la contraseña en texto plano

#### Scenario: Verificación usa comparación segura de la librería

- **WHEN** el sistema verifica una contraseña ingresada contra el hash almacenado
- **THEN** usa la función de verificación de la librería Argon2id (comparación en tiempo constante), no una comparación de strings implementada por el proyecto

### Requirement: Protección contra fuerza bruta en login

El sistema SHALL aplicar rate limiting progresivo sobre los intentos de login fallidos, por cuenta y por origen, y SHALL bloquear temporalmente la cuenta tras exceder el umbral configurado.

#### Scenario: Intentos fallidos consecutivos bloquean la cuenta

- **WHEN** un origen acumula intentos de login fallidos consecutivos por encima del umbral configurado para una misma cuenta
- **THEN** el sistema responde con el código `ACCOUNT_LOCKED`, deshabilita nuevos intentos de esa cuenta durante la ventana de bloqueo configurada, y no ejecuta la verificación de contraseña mientras dure el bloqueo

#### Scenario: Bloqueo se libera por tiempo o por acción del Admin

- **WHEN** transcurre la ventana de bloqueo configurada, o el Admin revoca las sesiones y desbloquea la cuenta manualmente
- **THEN** la cuenta vuelve a aceptar intentos de login

#### Scenario: Intentos fallidos de TOTP cuentan para el mismo bloqueo

- **WHEN** un usuario en el paso de verificación TOTP falla el código repetidamente hasta el límite de reintentos configurado
- **THEN** el sistema aplica el mismo bloqueo `ACCOUNT_LOCKED` que ante fuerza bruta de contraseña

### Requirement: Sesión server-side firmada

El sistema SHALL emitir, tras un login exitoso, una sesión rastreada del lado del servidor (no solo un token stateless que el servidor no pueda invalidar), identificada por una cookie firmada con atributos `Secure`, `HttpOnly` y `SameSite` conforme a OWASP ASVS (gestión de sesiones).

#### Scenario: Cookie de sesión con atributos seguros

- **WHEN** el sistema emite la cookie de sesión tras un login exitoso
- **THEN** la cookie se emite con los atributos `Secure`, `HttpOnly` y `SameSite` configurados, y su valor no permite reconstruir ni falsificar la sesión sin la clave de firma del servidor

#### Scenario: Sesión inválida o no firmada correctamente es rechazada

- **WHEN** una petición llega con una cookie de sesión ausente, corrupta o cuya firma no valida
- **THEN** el sistema responde 401 y no resuelve ningún `userId` a partir de esa petición

### Requirement: userId siempre derivado de la sesión

El sistema SHALL derivar el `userId` de toda operación autenticada exclusivamente de la sesión validada en el servidor. El sistema SHALL ignorar cualquier `userId` u otro identificador de usuario que llegue en el cuerpo o los parámetros de la petición.

#### Scenario: Body con userId ajeno es ignorado

- **WHEN** una petición autenticada de la sesión del usuario "lucia" incluye en el body un campo `userId` correspondiente a otro usuario
- **THEN** el sistema ejecuta la operación usando el `userId` de la sesión de "lucia", ignora silenciosamente el valor del body, y no hay forma de que la petición actúe en nombre de otro usuario

### Requirement: Revocación de sesiones

El sistema SHALL permitir revocar una sesión individual (logout propio, o el Admin sobre una sesión específica) y revocar todas las sesiones activas de un usuario (el Admin, por ejemplo al suspender la cuenta o resetear la contraseña).

#### Scenario: Sesión revocada responde 401

- **WHEN** una sesión fue revocada (por logout, por el Admin, o por expiración) y llega una petición posterior usando esa misma sesión
- **THEN** el sistema responde 401 y no ejecuta la operación solicitada

#### Scenario: Revocación total termina todas las sesiones del usuario

- **WHEN** el Admin revoca todas las sesiones de un usuario
- **THEN** toda sesión activa de ese usuario, en cualquier dispositivo, deja de ser válida de forma inmediata

### Requirement: Expiración de sesión por inactividad

El sistema SHALL expirar automáticamente una sesión que no registre actividad durante el timeout de inactividad configurado.

#### Scenario: Sesión expira tras el timeout de inactividad

- **WHEN** transcurre el timeout de inactividad configurado sin peticiones autenticadas de una sesión
- **THEN** la siguiente petición con esa sesión responde 401 y el frontend redirige a login conservando la URL destino para el post-login

### Requirement: Cierre de sesión explícito

El sistema SHALL invalidar la sesión del lado del servidor de forma inmediata cuando el usuario hace logout explícito, no solo eliminar la cookie del lado del cliente.

#### Scenario: Logout invalida la sesión en el servidor

- **WHEN** un usuario autenticado ejecuta logout
- **THEN** el sistema marca esa sesión como revocada en el almacenamiento server-side y cualquier petición posterior con esa cookie responde 401

### Requirement: TOTP obligatorio para cuentas Admin

El sistema SHALL exigir un segundo factor TOTP a toda cuenta con rol Admin. Una cuenta Admin sin TOTP enrolado SHALL completar el enrolamiento antes de poder acceder a cualquier capacidad de Admin, sin opción de posponerlo.

#### Scenario: Login de Admin exige challenge TOTP

- **WHEN** una cuenta con rol Admin envía usuario y contraseña correctos y ya tiene TOTP enrolado
- **THEN** el sistema exige un segundo paso de verificación con el código TOTP antes de crear la sesión completa

#### Scenario: Admin sin TOTP enrolado no puede saltar el enrolamiento

- **WHEN** una cuenta Admin sin TOTP enrolado completa el login con usuario y contraseña
- **THEN** el sistema fuerza el paso de enrolamiento TOTP del wizard de primer acceso sin ofrecer la opción "configurar más tarde"

#### Scenario: Cambio de rol a Admin fuerza enrolamiento TOTP en el siguiente login

- **WHEN** el Admin cambia el rol de una cuenta existente de Técnico o Funcional a Admin
- **THEN** en el siguiente login de esa cuenta el sistema exige completar el enrolamiento TOTP antes de continuar

### Requirement: TOTP opcional para Técnico y Funcional

El sistema SHALL permitir a cuentas con rol Técnico o Funcional activar o desactivar TOTP desde su configuración personal, salvo que el Admin lo haya marcado como obligatorio para esa cuenta.

#### Scenario: Usuario Técnico o Funcional activa TOTP desde configuración personal

- **WHEN** un usuario con rol Técnico o Funcional activa TOTP desde su configuración personal
- **THEN** el sistema ejecuta el mismo flujo de enrolamiento guiado (QR + códigos de respaldo) y, desde ese momento, el login de esa cuenta exige el segundo paso TOTP

#### Scenario: Usuario Técnico o Funcional desactiva TOTP propio

- **WHEN** un usuario con rol Técnico o Funcional que no tiene TOTP marcado como obligatorio por el Admin desactiva TOTP desde su configuración personal
- **THEN** el sistema deja de exigir el segundo paso TOTP en logins futuros de esa cuenta

### Requirement: Enrolamiento guiado de TOTP con códigos de respaldo

El sistema SHALL guiar el enrolamiento de TOTP mostrando un código QR y una clave manual en Base32, y SHALL generar un conjunto de códigos de respaldo de un solo uso para el caso de pérdida del dispositivo TOTP.

#### Scenario: Enrolamiento genera QR, clave manual y códigos de respaldo

- **WHEN** un usuario inicia el enrolamiento de TOTP
- **THEN** el sistema muestra un código QR con el secreto `otpauth://`, la clave manual equivalente en Base32, y un conjunto de códigos de respaldo de un solo uso, y solo activa TOTP tras confirmar un código válido generado por la app del usuario

#### Scenario: Código de respaldo usado se invalida

- **WHEN** un usuario inicia sesión con un código de respaldo en lugar de un código TOTP
- **THEN** el sistema acepta ese código de respaldo una única vez y lo marca como usado, de forma que no puede reutilizarse en un login posterior

### Requirement: Cambio de contraseña propio

El sistema SHALL permitir a todo usuario autenticado cambiar su propia contraseña indicando la contraseña actual y la nueva, sujeta a la política de contraseñas vigente.

#### Scenario: Cambio de contraseña exitoso

- **WHEN** un usuario autenticado envía su contraseña actual correcta y una nueva contraseña que cumple la política vigente
- **THEN** el sistema actualiza el hash Argon2id almacenado y, por seguridad, revoca las demás sesiones activas del usuario salvo la que originó el cambio

#### Scenario: Cambio de contraseña rechazado por incumplir la política

- **WHEN** un usuario autenticado envía una nueva contraseña que no cumple la política vigente (longitud, complejidad) o es igual a la actual
- **THEN** el sistema rechaza el cambio y devuelve el detalle accionable de qué requisito falta, sin aplicar ninguna modificación

### Requirement: Primer acceso obligatorio

El sistema SHALL detectar el primer login de una cuenta (o un login posterior a un reset de contraseña) y SHALL forzar el wizard de primer acceso — cambio de contraseña, selección de idioma y tema, enrolamiento TOTP según el rol y aceptación del acuerdo de uso — antes de permitir el acceso a cualquier otra vista del shell. El sistema SHALL persistir el progreso de los pasos ya completados si el usuario cierra sesión antes de terminar el wizard.

#### Scenario: Primer login redirige obligatoriamente al wizard

- **WHEN** un usuario con contraseña temporal (alta nueva o reset) completa el login por primera vez
- **THEN** el sistema redirige al wizard de primer acceso y ninguna otra ruta del shell queda accesible hasta completarlo; la única salida disponible es el logout

#### Scenario: Wizard persiste idioma y tema seleccionados

- **WHEN** el usuario completa el paso de preferencias del wizard eligiendo idioma y tema
- **THEN** el sistema persiste esas preferencias en la cuenta y las aplica de inmediato al entrar al shell

#### Scenario: Progreso del wizard persiste entre sesiones

- **WHEN** un usuario cierra sesión (o la sesión expira) tras completar solo algunos pasos del wizard, y vuelve a iniciar sesión
- **THEN** el sistema retoma el wizard en el primer paso pendiente, sin repetir los pasos ya completados
