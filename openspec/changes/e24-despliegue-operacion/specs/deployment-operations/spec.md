# deployment-operations — Delta Spec (e24-despliegue-operacion)

> Fuentes normativas: `docs/07-roadmap.md` fila `e24` (Etapa E), `docs/02-arquitectura.md` (deployable 1 — plataforma core, ADR-0005), `docs/06-seguridad-gobernanza.md` (kill switch, incidentes), `design/FUNCIONALIDADES.md` §1 (Acceso e identidad — gateway no público) y §11 (Administración — salud del sistema, retención). Contratos consumidos sin modificar: `a02-core-manifiestos` (manifiestos de fábrica), `d11-identidad-acceso` (TOTP obligatorio Admin, fuerza bruta), `d14-attachments` (límites por tipo), `d19-admin-operacion` (vista de salud), `d20-gobernanza-plataforma` (configuración de instancia, kill-switch). Infraestructura de referencia: primera instancia sobre `RESULTARBO-SERVER` (Windows + WSL2/Docker) — `docs/referencias/contexto-resultar-soluciones.md`.

## ADDED Requirements

### Requirement: Levantamiento de instancia con un comando

El Docker Compose de instancia SHALL definir todos los servicios (plataforma backend, plataforma frontend, Postgres, Langfuse self-hosted con sus dependencias, Uptime Kuma) de forma que `docker compose up -d` sobre una máquina sin estado previo levante la instancia completa sin pasos manuales adicionales más allá de proveer el `.env` con los secretos requeridos.

#### Scenario: Instancia limpia se levanta con un comando y pasa el smoke test

- **WHEN** se ejecuta `docker compose up -d` sobre una máquina sin volúmenes ni contenedores previos de la instancia, con un `.env` completo
- **THEN** todos los servicios definidos alcanzan estado `healthy` según sus healthchecks y, al ejecutar el smoke test E2E contra esa instancia, todos sus pasos terminan en verde

#### Scenario: Segundo levantamiento con volúmenes existentes no vuelve a sembrar

- **WHEN** se ejecuta `docker compose up -d` sobre una instancia que ya tiene datos persistidos (la cuenta Admin ya creada)
- **THEN** el seed inicial detecta el estado existente, no recrea la cuenta Admin ni los manifiestos de fábrica, y deja el estado previo intacto

### Requirement: Exposición pública limitada al frontend/API

El Docker Compose SHALL publicar hacia el host, a través del reverse proxy, únicamente los puertos necesarios para servir el frontend Next.js y la API FastAPI. Ningún otro servicio de la instancia — Postgres, Langfuse, Uptime Kuma, ni el gateway LLM invocado por `adapters/llm_litellm` — SHALL publicar puertos hacia el host ni quedar alcanzable desde fuera de la red interna de Docker definida por el Compose.

#### Scenario: Postgres inaccesible desde fuera de la red interna

- **WHEN** se intenta conectar a Postgres desde fuera de la red interna Docker de la instancia (por ejemplo, desde otra máquina de la red del servidor apuntando al host)
- **THEN** la conexión falla porque el servicio Postgres no publica ningún puerto hacia el host; solo un contenedor dentro de la misma red interna puede alcanzarlo

#### Scenario: El gateway LLM tampoco publica puerto

- **WHEN** se enumeran los puertos publicados hacia el host por el Compose
- **THEN** el adapter de LiteLLM (o cualquier gateway LLM que use) no aparece entre los servicios con puerto publicado; solo el reverse proxy lo está

#### Scenario: Interfaces de administración de terceros alcanzables solo dentro de la red del operador

- **WHEN** el Admin sigue el enlace a Langfuse o a Uptime Kuma desde la vista de salud del sistema (`d19-admin-operacion`)
- **THEN** accede dentro de la red privada del servidor (o VPN del operador), sin que Langfuse o Uptime Kuma publiquen un puerto directamente accesible desde internet

### Requirement: Healthchecks por servicio

Cada servicio definido en el Compose SHALL declarar un healthcheck propio (endpoint HTTP o comando) con intervalo, timeout y reintentos configurados. Los servicios con dependencias SHALL declarar `depends_on` con `condition: service_healthy`, de forma que no arranquen contra una dependencia que aún no está lista.

#### Scenario: Un servicio no sano bloquea el arranque de sus dependientes

- **WHEN** Postgres no alcanza estado `healthy` dentro del timeout configurado
- **THEN** la plataforma backend no arranca (permanece en espera) y `docker compose ps` muestra Postgres como no saludable, sin que el backend intente conectar contra una base no lista

#### Scenario: Todos los servicios sanos

- **WHEN** todos los healthchecks pasan
- **THEN** `docker compose ps` reporta cada servicio como `healthy` y el smoke test puede ejecutarse

### Requirement: Volúmenes persistentes para BD y adjuntos

El Compose SHALL declarar volúmenes Docker nombrados y persistentes, independientes entre sí, para los datos de Postgres y para el `storage_path` de adjuntos (`b04-persistencia-postgres`), de forma que detener y recrear los contenedores (`docker compose down` sin `-v`, seguido de `up`) preserve sesiones, mensajes, audit log y binarios de adjuntos.

#### Scenario: Recrear contenedores preserva los datos

- **WHEN** se ejecuta `docker compose down` (sin `-v`) seguido de `docker compose up -d`
- **THEN** las sesiones, mensajes, audit log y adjuntos previos siguen presentes tras el nuevo arranque

#### Scenario: Volumen de adjuntos separado del volumen de Postgres

- **WHEN** se inspeccionan los volúmenes declarados por el Compose
- **THEN** el volumen de datos de Postgres y el volumen de binarios de adjuntos son volúmenes independientes, cada uno respaldable por separado

### Requirement: Configuración por entorno vía `.env`

El repo SHALL incluir un `.env.example` documentado, con una entrada por cada variable que el Compose y sus servicios referencian (credenciales de Postgres, secreto de firma de sesión, claves de proveedores LLM para LiteLLM, credenciales de Langfuse, dominio y configuración de TLS), sin ningún secreto real. El `.env` con secretos reales SHALL quedar excluido del control de versiones.

#### Scenario: `.env.example` cubre todas las variables requeridas

- **WHEN** se compara `.env.example` contra las variables que el Compose y sus servicios referencian
- **THEN** cada variable usada tiene una entrada documentada en `.env.example`, con un valor de ejemplo no sensible o un placeholder explícito

#### Scenario: `.env` real nunca se commitea

- **WHEN** se crea el `.env` real a partir del ejemplo y se ejecuta `git status`
- **THEN** `.gitignore` excluye `.env`, y ningún script ni workflow de este change requiere que exista en el repo

### Requirement: Configuración de instancia como seed inicial

El seed inicial SHALL cargar los valores por defecto de configuración de instancia (branding, retención de adjuntos, límites de attachments, idioma default, umbral de aviso de cuota, TTL de tarjetas HITL — contrato de `d20-gobernanza-plataforma`) desde un archivo de seed versionado en el árbol de despliegue, de forma que una instancia recién levantada arranque con valores operativos razonables sin intervención manual del Admin antes del primer login.

#### Scenario: Instancia recién levantada tiene configuración de instancia poblada

- **WHEN** se completa el seed inicial sobre una instancia limpia
- **THEN** la configuración de instancia en DB (branding, retención, límites, umbral de cuota, TTL de HITL) tiene los valores del seed, consultables desde la consola de gobernanza (`d20`) sin que el Admin deba completarlos a mano

### Requirement: Cuenta Admin inicial con TOTP forzado en primer login

El seed inicial SHALL crear exactamente una cuenta con rol Admin y contraseña temporal, de forma que su primer login dispare el wizard de primer acceso con enrolamiento TOTP obligatorio (contrato de `d11-identidad-acceso`), sin permitir acceso a ninguna capacidad de Admin hasta completarlo.

#### Scenario: Primer login de la cuenta Admin sembrada exige TOTP

- **WHEN** la cuenta Admin sembrada por el seed inicial completa su primer login con la contraseña temporal
- **THEN** el sistema fuerza el wizard de primer acceso con enrolamiento TOTP antes de permitir cualquier otra vista, igual que cualquier otra cuenta Admin (`d11`)

#### Scenario: La contraseña temporal nunca queda en un canal persistente inseguro

- **WHEN** se ejecuta el seed inicial
- **THEN** la contraseña temporal de la cuenta Admin se entrega por un único canal documentado (salida de consola del script de seed, no un archivo ni un log persistente) y el hash almacenado es Argon2id, nunca texto plano

### Requirement: Manifiestos de fábrica cargados y validados en el seed

El seed inicial SHALL cargar los manifiestos de fábrica (`default_chat`, skill/tool/policy/routing/eval de ejemplo — contrato de `a02-core-manifiestos`) y SHALL ejecutar la validación fail-fast antes de considerar la instancia lista; un manifiesto de fábrica inválido SHALL abortar el seed con el mismo comportamiento que el arranque fail-fast de `a02`.

#### Scenario: Manifiestos de fábrica válidos permiten completar el seed

- **WHEN** el seed inicial valida los manifiestos de fábrica
- **THEN** todos pasan la validación de `a02` y el seed continúa hasta dejar la instancia lista para el smoke test

#### Scenario: Un manifiesto de fábrica corrupto aborta el seed

- **WHEN** uno de los manifiestos de fábrica incluidos en la imagen viola su schema
- **THEN** el seed aborta antes de dejar la instancia en servicio, señalando el manifiesto culpable

### Requirement: Contenido de ejemplo activo tras el seed

El seed inicial SHALL dejar activos y visibles en catálogo el skill de ejemplo, el MCP server de ejemplo y el workflow de ejemplo de fábrica, de forma que el smoke test E2E pueda ejercitarlos sin pasos de activación manual adicionales.

#### Scenario: Contenido de ejemplo visible sin pasos manuales

- **WHEN** la cuenta Admin sembrada completa el wizard de primer acceso y abre el catálogo
- **THEN** el skill de ejemplo, el MCP server de ejemplo y el workflow de ejemplo aparecen activos, sin necesidad de publicarlos ni activarlos manualmente antes del smoke test

### Requirement: Backup diario de Postgres y del volumen de adjuntos

El sistema SHALL ejecutar un dump diario de Postgres y un respaldo del volumen de adjuntos, ambos hacia un destino configurable distinto del volumen que respaldan, con retención configurable (número de copias o días a conservar) que purgue automáticamente los backups vencidos.

#### Scenario: El dump diario corre y se retiene según la política configurada

- **WHEN** transcurre el intervalo diario configurado
- **THEN** el sistema genera un nuevo dump de Postgres y un nuevo respaldo del volumen de adjuntos, purgando las copias que exceden la retención configurada

#### Scenario: El destino del backup es independiente del volumen respaldado

- **WHEN** se inspecciona la configuración de backup
- **THEN** el destino de los dumps y respaldos no es el mismo volumen que Postgres o los adjuntos usan en producción, de forma que perder ese volumen no destruye también sus backups

### Requirement: Restauración documentada y probada

El repo SHALL incluir un procedimiento de restauración paso a paso (restaurar el dump de Postgres y el volumen de adjuntos sobre una instancia nueva o limpia). Una tarea de verificación SHALL ejecutar ese procedimiento contra un backup real al menos una vez, confirmando que la instancia restaurada queda funcional.

#### Scenario: Restore de backup deja la instancia funcional

- **WHEN** se restaura un backup de Postgres y de adjuntos sobre una instancia limpia siguiendo el procedimiento documentado
- **THEN** la instancia restaurada permite login con las cuentas previamente existentes, y las sesiones, mensajes y adjuntos del backup son consultables tal como estaban al momento del dump

#### Scenario: Restore parcial se documenta como degradado, no como falla silenciosa

- **WHEN** se restaura únicamente el dump de Postgres sin el volumen de adjuntos correspondiente
- **THEN** el procedimiento documentado señala explícitamente que los adjuntos referenciados por `storage_path` no estarán disponibles, sin que la instancia falle al arrancar

### Requirement: Rate limiting en login y API

El reverse proxy o el backend SHALL aplicar rate limiting configurable sobre el endpoint de login (coherente con la protección contra fuerza bruta de `d11-identidad-acceso`) y sobre la API en general (por IP o por sesión), rechazando con código `429` las peticiones que excedan el umbral.

#### Scenario: Exceso de peticiones de login desde un origen se limita

- **WHEN** un origen supera el umbral de peticiones de login configurado en la ventana de tiempo definida
- **THEN** las peticiones adicionales de ese origen reciben `429` antes de llegar a la lógica de verificación de contraseña

#### Scenario: Rate limit de API general no bloquea uso normal

- **WHEN** un usuario autenticado usa el chat con un patrón de tráfico normal
- **THEN** permanece por debajo del umbral configurado y ninguna de sus peticiones recibe `429`

### Requirement: Security headers y TLS vía reverse proxy

El reverse proxy SHALL terminar TLS con un certificado válido y SHALL agregar cabeceras de seguridad estándar (`Strict-Transport-Security`, `X-Content-Type-Options`, protección de framing vía `X-Frame-Options` o `frame-ancestors` de CSP, `Content-Security-Policy` acorde al frontend Next.js) a toda respuesta servida al navegador.

#### Scenario: Respuesta HTTP incluye las cabeceras de seguridad configuradas

- **WHEN** un cliente solicita cualquier ruta del frontend o de la API a través del reverse proxy
- **THEN** la respuesta incluye `Strict-Transport-Security`, `X-Content-Type-Options: nosniff` y una `Content-Security-Policy` (o headers equivalentes) definidos por la configuración del reverse proxy

#### Scenario: Tráfico HTTP se redirige a HTTPS

- **WHEN** llega una petición por HTTP plano al reverse proxy
- **THEN** el reverse proxy responde con una redirección a HTTPS, sin servir contenido por el canal sin cifrar

### Requirement: Límites de tamaño de request coherentes con d14

El reverse proxy y el backend SHALL configurar un límite máximo de tamaño de request coherente con la matriz de límites por tipo de adjunto de `d14-attachments` (máximo por tipo de archivo y máximo 5 adjuntos por mensaje), de forma que una subida legítima dentro de esos límites nunca sea rechazada por el límite de infraestructura antes de llegar a la validación de la aplicación, y que una request que exceda ampliamente esos límites se rechace en el borde sin consumir recursos del backend.

#### Scenario: Una subida dentro de los límites de d14 no es rechazada por infraestructura

- **WHEN** se sube un adjunto multipart cuyo tamaño total (incluyendo overhead de multipart y hasta 5 archivos, respetando el límite mayor por tipo definido en `d14`) está dentro de los límites configurados
- **THEN** el reverse proxy y el backend aceptan la request y la entregan a la validación de aplicación de `d14`, sin rechazarla por límite de infraestructura

#### Scenario: Una request que excede ampliamente el límite se corta en el borde

- **WHEN** llega una request cuyo tamaño supera el límite de infraestructura configurado (con margen sobre el máximo legítimo de `d14`)
- **THEN** el reverse proxy la rechaza con un error de tamaño excedido antes de que llegue al backend

### Requirement: Usuario no-root en contenedores propios

Toda imagen de contenedor construida por este change (backend, frontend) SHALL ejecutar su proceso principal con un usuario no-root definido en el Dockerfile.

#### Scenario: El proceso del backend corre como usuario no-root

- **WHEN** se inspecciona el usuario del proceso principal dentro del contenedor de backend en ejecución
- **THEN** el usuario no es `root` (uid 0)

#### Scenario: El proceso del frontend corre como usuario no-root

- **WHEN** se inspecciona el usuario del proceso principal dentro del contenedor de frontend en ejecución
- **THEN** el usuario no es `root` (uid 0)

### Requirement: Imágenes de terceros pinneadas por digest

El Compose SHALL referenciar cada imagen de terceros (Postgres, Langfuse y sus dependencias, Uptime Kuma, reverse proxy) por su digest de contenido (`imagen@sha256:...`), no solo por tag mutable, de forma que un `docker compose pull` no traiga una imagen distinta a la validada sin un cambio explícito en el repo.

#### Scenario: Cada imagen de terceros declara su digest

- **WHEN** se revisa el archivo de Compose
- **THEN** cada servicio de terceros referencia su imagen con `@sha256:...` además del tag legible, y actualizar la versión requiere un commit que cambie ese digest

### Requirement: Smoke test E2E de instancia completa

El repo SHALL incluir un script de smoke test que, contra una instancia levantada de cero con el Compose de este change, ejecute en orden y verifique: login de la cuenta Admin sembrada (incluyendo el enrolamiento TOTP forzado), alta de un usuario nuevo desde la consola de administración, un turno de chat con `default_chat` que responde, un adjunto de ejemplo que se sube y procesa hasta estado `ready`, una tool del MCP server de ejemplo invocada vía skill que pasa por el Policy Gate y queda auditada, una tarjeta de aprobación HITL que aparece para una acción de riesgo del ejemplo, y una ejecución del workflow de ejemplo que corre hasta su resultado. El script SHALL terminar con exit code distinto de 0 si cualquier paso falla, señalando cuál.

#### Scenario: Instancia limpia pasa el smoke test completo

- **WHEN** se ejecuta el script de smoke test contra una instancia recién levantada con el seed inicial completo
- **THEN** los siete pasos (login+TOTP, alta de usuario, chat, adjunto, tool vía skill con Policy Gate, tarjeta HITL, workflow) terminan en verde y el script sale con exit code 0

#### Scenario: Un paso falla y el smoke test señala cuál

- **WHEN** uno de los pasos del smoke test falla (por ejemplo, el turno de chat no obtiene respuesta dentro del timeout configurado)
- **THEN** el script termina con exit code distinto de 0, identificando el paso que falló, sin marcar los pasos siguientes como ejecutados

### Requirement: Smoke test ejecutable en CI contra Compose

El smoke test SHALL poder ejecutarse opcionalmente en CI levantando el mismo Docker Compose de este change (o un subconjunto suficiente con proveedores LLM simulados), sin depender de credenciales de producción ni de una instancia real ya existente.

#### Scenario: CI ejecuta el smoke test contra un Compose efímero

- **WHEN** el job opcional de smoke test corre en CI
- **THEN** levanta el Compose de la instancia con configuración de prueba (incluyendo un proveedor LLM simulado si no hay credenciales reales disponibles), ejecuta el smoke test completo, y destruye el entorno efímero al finalizar independientemente del resultado

### Requirement: Runbook de incidentes con kill-switch como primer recurso

El repo SHALL incluir un runbook de incidentes que indique, como primer paso ante un comportamiento anómalo de un agente, skill o tool, usar el kill-switch de `d20-gobernanza-plataforma` antes que cualquier otra acción de mitigación, junto con dónde mirar para diagnosticar (vista de salud del sistema de `d19-admin-operacion`, Langfuse, Uptime Kuma), el procedimiento de restauración de este mismo change, y los contactos de escalamiento.

#### Scenario: El runbook prioriza el kill-switch

- **WHEN** un operador consulta el runbook ante un incidente de un agente que responde con datos incorrectos o de otro tenant
- **THEN** el primer paso documentado es apagar el agente o la tool afectada por kill-switch (`d20`), antes de investigar la causa raíz

#### Scenario: El runbook enlaza las fuentes de diagnóstico

- **WHEN** un operador sigue el runbook para diagnosticar un incidente
- **THEN** encuentra referencias directas a la vista de salud del sistema (`d19`), a Langfuse y a Uptime Kuma, sin tener que buscarlas fuera del runbook

#### Scenario: El runbook incluye contactos de escalamiento

- **WHEN** un operador no puede resolver el incidente con los pasos documentados
- **THEN** el runbook indica a quién escalar y por qué canal, sin dejar el paso siguiente implícito
