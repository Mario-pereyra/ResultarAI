# Proposal — a01-fundacion-repo

## Why

El pivote 2026-07-09 (producto completo "de fábrica", `docs/07-roadmap.md`) exige un repo ejecutable donde las fronteras arquitectónicas se verifiquen por máquina desde el primer commit: sin esqueleto de paquetes, tooling de calidad y CI, ningún change posterior puede implementarse con seguridad. Además, cuatro documentos adoptados aún describen el enfoque MVP anterior y contradicen el roadmap vigente.

## What Changes

- Se crea la estructura de paquetes Python (`resultarai/` con `core/`, `adapters/`, `app/`, `manifests/`, `tests/`) según `docs/05-estructura-y-convenciones.md`, gestionada con uv.
- Se configura el tooling de calidad: ruff, mypy estricto, pytest e import-linter con los 3 contratos de frontera (core sin frameworks; app→adapters→core; independencia entre adapters).
- Se crea el pipeline de CI (GitHub Actions) que ejecuta lint + tipos + fronteras + tests en cada push/PR, y pre-commit para el ciclo local.
- Se escriben 3 ADRs del pivote: ADR-0007 (frontend Next.js + assistant-ui), ADR-0008 (stack de autenticación Python), ADR-0009 (adopción de specs oficiales Agent Skills y MCP).
- Se sincronizan `docs/01-vision.md`, `docs/02-arquitectura.md`, `docs/03-glosario-dominio.md` y `docs/04-manifiestos.md` con el pivote (producto completo, frontend, skills/tools por spec oficial), y `CLAUDE.md` (comandos reales).

## Capabilities

### New Capabilities

- `repo-scaffolding`: estructura de paquetes, tooling de calidad (uv, ruff, mypy, pytest, import-linter, pre-commit) y CI que verifica las fronteras arquitectónicas en cada cambio.

### Modified Capabilities

*(ninguna — no existen specs previas)*

## No-objetivos

- Ningún código de runtime (ni schemas de manifiestos —`a02`—, ni Policy Gate —`a03`—, ni adapters).
- Ningún scaffold del frontend (llega en `d10-design-system-shell`; aquí solo se decide el stack por ADR).
- Ninguna configuración de despliegue (Docker/Compose llega en `e24-despliegue-operacion`).
- No se toca `design/` ni `docs/referencias/`.

## Bounded context afectado

Transversal de esqueleto: crea las carpetas de `core/`, `adapters/`, `app/`, `manifests/` y `tests/` sin lógica dentro. No pertenece a un bounded context funcional.

## Impact

- Repo completo (raíz): `pyproject.toml`, `.github/workflows/`, `.pre-commit-config.yaml`, árbol `resultarai/`.
- `docs/` (sincronización) y `docs/adr/` (0007–0009).
- Referencia del blueprint: §2.4.4 Priorización P0 "Agentic Scaffolding Framework" (la fundación habilita esa prioridad sin implementarla aún).
