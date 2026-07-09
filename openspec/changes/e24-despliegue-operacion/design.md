# Design — e24-despliegue-operacion

## Context

Los changes a01–e23 especifican el producto completo (plataforma core, deployable 1 de ADR-0005), pero ninguno define su empaquetado ni su operación. El principio "instancia por cliente" de `design/FUNCIONALIDADES.md` exige que levantar una instancia sea reproducible y aburrido. La primera instancia real corre en `RESULTARBO-SERVER` (Windows 11/Server con WSL2 + Docker, i7-12700H, 32 GB RAM, `docs/referencias/contexto-resultar-soluciones.md`): un solo host, sin nube, con RAM suficiente para plataforma + Postgres + Langfuse + Uptime Kuma pero sin margen para orquestadores pesados. Este change es el último de la Etapa E antes de `e25-evals-gates` y no introduce código de dominio: empaqueta, siembra, respalda, endurece y documenta.

## Goals / Non-Goals

**Goals:**

- Un `docker compose up -d` + `.env` levanta la instancia completa y el smoke test E2E pasa.
- Frontera de red verificable: solo el reverse proxy publica puertos; Postgres, Langfuse, Uptime Kuma y el gateway LLM viven en la red interna Docker (materializa "Gateway no público" de `design/FUNCIONALIDADES.md` §1).
- Seed inicial idempotente: cuenta Admin (TOTP forzado vía contrato `d11`), configuración de instancia (`d20`) y manifiestos de fábrica validados (`a02`) con contenido de ejemplo activo.
- Backup diario + restore probado de verdad (tarea con verificación de restore real, no solo doc).
- Runbook de incidentes que completa el placeholder operativo de `docs/06-seguridad-gobernanza.md` (kill-switch como primer recurso).

**Non-Goals:**

- Kubernetes, multi-nodo, HA horizontal, CDN.
- Despliegue de los satélites (ERP Safe Query API, Edge Connector) — Etapa P.
- CI/CD de release a instancias reales; solo el smoke test opcional en CI.
- Ningún cambio a `core/`, `adapters/` ni `app/`.

## Decisions

1. **Docker Compose como única herramienta de orquestación.** Alternativas: Kubernetes/k3s (sobredimensionado para un host único con 32 GB compartidos con otros servicios de Resultar; añade una superficie operativa que nadie del equipo domina) y systemd + contenedores sueltos (pierde `depends_on`/healthchecks declarativos). Compose corre nativo en WSL2/Docker Desktop y el archivo es el contrato legible de la instancia.
2. **Topología de red: una red interna + reverse proxy como único punto publicado.** El reverse proxy (Caddy o Nginx — la tarea de implementación elige y documenta; Caddy favorito por TLS automático y configuración mínima) termina TLS, aplica security headers, rate limits y límite de tamaño de request, y enruta al frontend Next.js y a la API FastAPI. Postgres, Langfuse, Uptime Kuma y LiteLLM no declaran `ports:`. Alternativa descartada: publicar Langfuse/Uptime Kuma con auth básica hacia internet — innecesario, el Admin accede por la red privada/VPN del servidor (los enlaces de la vista de salud de `d19` siguen funcionando dentro de esa red).
3. **Árbol de despliegue en `deploy/` en la raíz del repo**, fuera de `resultarai/`: `compose.yaml`, `Dockerfile.backend`, `Dockerfile.frontend`, configuración del reverse proxy, `seed/` (configuración de instancia inicial), `scripts/` (backup, restore, smoke test) y `runbook.md`. Mantiene la regla de dependencia intacta: infraestructura no es un bounded context y no vive dentro del paquete Python.
4. **Seed como comando idempotente del backend** (invocado por un servicio one-shot del Compose o manualmente): detecta estado existente y no re-siembra. Reutiliza la validación fail-fast de `a02` para los manifiestos de fábrica y el flujo de primer acceso de `d11` para el TOTP del Admin (el seed NO implementa TOTP: crea la cuenta con contraseña temporal y el contrato de `d11` hace el resto). La contraseña temporal sale solo por stdout del comando de seed. Alternativa descartada: fixtures SQL directas — se saltarían la validación de manifiestos y el hash Argon2id de la capa de aplicación.
5. **Backups con contenedor sidecar programado** (cron dentro de un contenedor con acceso a la red interna y a los volúmenes): `pg_dump` diario + tar del volumen de adjuntos hacia un bind mount del host fuera de los volúmenes Docker, con retención por conteo/días configurable por variables de entorno. Alternativa descartada: cron del host Windows — frágil a través de WSL2 y no versionable con el Compose. La restauración es un script separado y su prueba real es una tarea propia con verificación observable.
6. **Smoke test como script Python contra la API pública** (httpx + los mismos contratos que consume el frontend), no un test de browser: más estable, sin dependencia de Playwright, y ejercita exactamente la superficie publicada. El paso TOTP usa `pyotp` para generar el código a partir del secreto de enrolamiento devuelto por el flujo de `d11`. En CI corre contra un Compose efímero con un proveedor LLM simulado vía la configuración de perfiles de LiteLLM (`b05`), para no depender de credenciales reales.
7. **Imágenes pinneadas por digest y usuario no-root.** Los Dockerfiles propios crean un usuario dedicado; las imágenes de terceros se referencian `imagen:tag@sha256:...`. Actualizar = commit que cambia el digest (auditable por PR, coherente con la regla "clasificación fija por versión, cambiarla = PR" del proyecto).
8. **Los rate limits viven en el borde (reverse proxy) y complementan, no reemplazan, el bloqueo de cuenta de `d11`**: el proxy corta el volumen bruto por IP; la lógica `ACCOUNT_LOCKED` de `d11` gobierna la semántica por cuenta. Los límites de tamaño de request se calculan desde la matriz del ANEXO de attachments (`d14`): máximo legítimo = 50 MB (CSV) + overhead multipart; el límite del proxy se fija con margen documentado por encima y nunca por debajo.

## Risks / Trade-offs

- [Un solo host = un solo punto de falla] → Mitigación: backups diarios con restore probado y runbook con RTO explícito; HA queda fuera de alcance por decisión (proposal).
- [Recursos compartidos en RESULTARBO-SERVER (otros servicios/clientes en el mismo hierro)] → Mitigación: límites de memoria por servicio en el Compose y Uptime Kuma monitoreando la propia instancia; el dimensionamiento fino se ajusta en operación.
- [El smoke test depende de un proveedor LLM real en la instancia productiva] → Mitigación: en CI usa proveedor simulado; contra la instancia real usa el perfil de modelo más barato y el gasto queda trazado en Langfuse como cualquier turno.
- [Digest pinning vuelve tediosa la actualización de imágenes] → Mitigación: es deliberado — actualizar terceros debe ser un PR consciente; el runbook documenta el procedimiento.
- [Deriva entre `.env.example` y las variables realmente usadas] → Mitigación: escenario de spec que exige cobertura 1:1 y verificación en la tarea de cierre.
- [Restore documentado pero nunca ejercitado se pudre] → Mitigación: la tarea de backups exige un restore real verificado antes de cerrar el change; el runbook recomienda repetirlo periódicamente.

## Migration Plan

Greenfield operativo: no hay instancia previa que migrar. Orden de despliegue de la primera instancia: (1) preparar `.env` desde `.env.example`; (2) `docker compose up -d`; (3) el seed corre y entrega la contraseña temporal del Admin; (4) primer login Admin con enrolamiento TOTP; (5) smoke test contra la instancia; (6) habilitar el backup programado y ejecutar la prueba de restore. Rollback = `docker compose down` (sin `-v` preserva datos); el desastre total se recupera con el procedimiento de restauración.

## Open Questions

*(ninguna — la elección concreta de reverse proxy queda delegada a la tarea de implementación con la restricción de cumplir los requirements de TLS/headers/límites; no bloquea ninguna spec)*
