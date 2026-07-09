# Design — a01-fundacion-repo

## Context

Repo greenfield con documentación adoptada (`docs/`) y paquete de diseño normativo (`design/`), sin código. El pivote 2026-07-09 fija 25 changes en 5 etapas; este es el primero y habilita a todos los demás. Las convenciones ya están decididas en `docs/05-estructura-y-convenciones.md`; este change las materializa.

## Goals / Non-Goals

**Goals:**

- Esqueleto de paquetes + tooling + CI, con las fronteras de `docs/02-arquitectura.md` verificadas por máquina.
- ADRs 0007–0009 que formalizan las decisiones del pivote que aún no tienen registro.
- `docs/` coherente con el roadmap vigente (cero contradicciones MVP vs producto completo).

**Non-Goals:**

- Runtime, schemas, frontend, despliegue (changes posteriores).

## Decisions

1. **uv como gestor único** (ya decidido en docs/05). Alternativa poetry descartada: uv es el estándar 2026, más rápido y con lockfile determinista.
2. **Monorepo con frontend futuro en `frontend/`** (se scaffoldea en `d10`). Alternativa repo separado descartada: un solo repo simplifica el flujo OpenSpec, el versionado conjunto de contratos API↔UI y el trabajo de agentes en segundo plano. ADR-0007 lo registra.
3. **ADR-0008 (auth Python)**: sesiones server-side firmadas + Argon2id para contraseñas + TOTP (pyotp) sobre FastAPI, usando librería mantenida (evaluación en el ADR entre `fastapi-users` y capa propia delgada sobre `passlib`/`argon2-cffi` + `itsdangerous`); Better Auth (Node, del design/) queda descartada por stack. Regla dura: nunca criptografía artesanal.
4. **ADR-0009 (specs oficiales)**: skills = Agent Skills spec (agentskills.io, SKILL.md); tools = MCP spec revisión vigente (2025-11-25 al escribir; el change `c09` la fija). El Skill/Tool Manifest de docs/04 pasa a ser el **envoltorio de gobernanza** que referencia esos artefactos oficiales.
5. **CI en GitHub Actions** con jobs paralelos (lint/tipos/fronteras/tests) y cache de uv. Alternativa: runner local — descartada, el repo ya vive en GitHub.
6. **El esqueleto no incluye ni un solo módulo con lógica**: solo `__init__.py`, `py.typed`, un test de humo y placeholders de paquete. Evita que "fundación" se convierta en implementación encubierta sin spec.

## Risks / Trade-offs

- [Sobre-ingeniería temprana del tooling] → Mitigación: configuración mínima que pasa en verde; endurecer reglas específicas será tarea de los changes que aporten código real.
- [Docs desincronizados a futuro] → Mitigación: la regla de CLAUDE.md de actualizar "Estado actual" por etapa + la revisión final de cada change (tarea opus) incluye consistencia documental.
- [Elección de librería de auth pospuesta a ADR] → Mitigación: ADR-0008 se escribe en este change con decisión tomada, no "a investigar"; `d11` la implementa sin reabrir el debate.

## Open Questions

*(ninguna — las decisiones quedan tomadas en los ADRs de este change)*
