# Proposal — e24-despliegue-operacion

## Why

Todas las etapas A–E producen un producto especificado y probado en tests unitarios/de integración, pero ninguna define cómo una instancia real se levanta, se configura, se respalda y se opera el día después de un incidente. Sin este change, "instancia por cliente" (principio normativo de `design/`) queda como aspiración: no hay Docker Compose, no hay seed inicial reproducible, no hay backup probado ni runbook. `e24` cierra la Etapa E convirtiendo el producto especificado en una instancia operable de punta a punta, sobre la primera máquina real (RESULTARBO-SERVER, Windows con WSL2/Docker).

## What Changes

- Se crea el Docker Compose de instancia: plataforma (backend FastAPI + frontend Next.js), Postgres, Langfuse self-hosted y Uptime Kuma, en red interna Docker; solo el frontend/API se publica hacia afuera — el gateway LLM y Postgres nunca quedan alcanzables desde fuera de esa red interna.
- Se define la configuración por entorno: `.env.example` documentado en la raíz del árbol de despliegue, todos los secretos fuera del repo, y la configuración de instancia (`d20-gobernanza-plataforma`) como seed inicial versionado (branding, retención, límites, matrices por defecto).
- Se define el seed inicial de instancia: primera cuenta Admin con enrolamiento TOTP forzado en su primer login (contrato de `d11-identidad-acceso`), manifiestos de fábrica cargados y validados (contrato de `a02-core-manifiestos`) y el skill/tool/workflow de ejemplo activos y visibles en catálogo.
- Se define la estrategia de backups: dump diario de Postgres y respaldo del volumen de adjuntos, retención configurable, y un procedimiento de restauración documentado y verificado con una prueba real de restore (no solo documentado en teoría).
- Se define el hardening de la instancia: rate limits (login y API general), security headers, TLS vía reverse proxy, límites de tamaño de request coherentes con la matriz de adjuntos de `d14-attachments`, usuario no-root en todos los contenedores propios, e imágenes de terceros pinneadas por digest.
- Se define un smoke test E2E que levanta una instancia de cero (sin estado previo) y verifica la cadena completa: login Admin (con enrolamiento TOTP) → alta de usuario → turno de chat con `default_chat` que responde → adjunto que se procesa → una tool del server MCP de ejemplo invocada vía skill que pasa por el Policy Gate → tarjeta HITL que aparece → workflow de ejemplo que corre; ejecutable localmente y opcionalmente en CI contra el mismo Compose.
- Se define el runbook de incidentes: primeros pasos (kill-switch de `d20` como primer recurso), dónde mirar (vista de salud de `d19`, Langfuse, Uptime Kuma), procedimiento de restauración y contactos de escalamiento.

## Capabilities

### New Capabilities

- `deployment-operations`: Docker Compose de instancia, configuración por entorno, seed inicial (cuenta Admin + manifiestos de fábrica + contenido de ejemplo), backups con restore probado, hardening de red y de contenedores, smoke test E2E, y runbook de incidentes.

### Modified Capabilities

*(ninguna — no existen requirements previos de despliegue/operación; todos los contratos de otros changes se consumen como dependencia, no se modifican)*

## No-objetivos

- Sin Kubernetes ni ningún orquestador de contenedores más allá de Docker Compose.
- Sin arquitectura multi-nodo ni alta disponibilidad horizontal: una instancia = un host Docker.
- Sin CDN ni distribución de estáticos fuera del propio reverse proxy de la instancia.
- Sin despliegue de los satélites ERP Safe Query API ni Edge Connector Windows — llegan con Etapa P, cuando el product owner defina la personalización Protheus.
- Sin CI/CD de producción automatizado más allá de correr el smoke test en CI; no hay pipeline de release/deploy automático a `RESULTARBO-SERVER` ni a ninguna instancia real.

## Bounded context afectado

Transversal de infraestructura/operación: no pertenece a `scaffolding`, `orchestration`, `governance`, `tools`, `connectivity`, `gateway` ni `observability` (`docs/02-arquitectura.md`), sino a la física de despliegue del deployable 1 (plataforma core) definida en ADR-0005. Consume, sin modificar, los contratos de `d11` (autenticación/TOTP), `d14` (límites de adjuntos), `d19` (vista de salud), `d20` (configuración de instancia, feature flags, kill-switch) y `a02` (manifiestos de fábrica).

## Impact

- Árbol de despliegue en la raíz del repo (fuera de `resultarai/`): Docker Compose, Dockerfiles de plataforma, configuración de reverse proxy, scripts de backup/restore/smoke test y el runbook.
- `.env.example` y documentación de variables de entorno.
- Ningún código de `core/`, `adapters/` ni `app/` se modifica: este change empaqueta y opera lo que las etapas A–D ya especifican.
- Referencia de infraestructura real: primera instancia sobre `RESULTARBO-SERVER` (Windows + WSL2/Docker, i7-12700H, 32 GB RAM) — `docs/referencias/contexto-resultar-soluciones.md`.
