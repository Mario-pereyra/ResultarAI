# ADR-0002 — DDD estratégico, sin DDD táctico completo

- **Estado:** aceptado (2026-07-09)

## Contexto

El usuario evaluó "DDD + hexagonal" como estilo. DDD táctico completo (aggregates, repositories abstractos, domain events, value objects por doquier) rinde cuando la lógica de negocio compleja vive dentro del código. En ResultarAI la lógica de negocio pesada vive en Protheus; la plataforma orquesta, valida políticas y traza.

## Decisión

Adoptar de DDD **solo la parte estratégica**:

1. **Lenguaje ubicuo** — los términos de [03-glosario-dominio.md](../03-glosario-dominio.md) son los únicos válidos en docs, specs, código y prompts.
2. **Bounded contexts como módulos** — la tabla de contexts de [02-arquitectura.md](../02-arquitectura.md) define las fronteras internas del monolito.

Los patrones tácticos se permiten **selectivamente y solo en el núcleo** (p. ej. los manifiestos como modelos Pydantic inmutables, el Policy Gate como servicio de dominio puro), nunca como plantilla obligatoria de todo el código.

## Alternativas consideradas

1. **DDD táctico completo en todos los módulos** — rechazada: ceremonia sin retorno en un dominio de orquestación; inmantenible para un equipo junior chico.
2. **Sin DDD alguno** — rechazada: sin lenguaje ubicuo ni fronteras nombradas, un codebase agentic degenera en sinónimos y módulos difusos; el costo de la parte estratégica es casi cero.

## Consecuencias

- (+) Vocabulario 1:1 entre blueprint, docs, specs de OpenSpec y código.
- (+) Fronteras de módulos con criterio de negocio, no técnicas arbitrarias.
- (−) Riesgo de que "selectivamente" degenere en inconsistencia → mitigado: introducir un patrón táctico nuevo requiere actualizar este ADR o crear uno nuevo.

## Fuentes

- Revisión sistemática sobre DDD (Journal of Systems and Software, 2025) — https://www.sciencedirect.com/science/article/pii/S0164121225002055 (preprint: https://arxiv.org/pdf/2310.01905)
- Estado de DDD 2025 (estratégico vigente, táctico opcional) — https://saventech.com/domain-driven-design-ddd-in-2025/
- Eric Evans, *Domain-Driven Design* (2003) — origen de los conceptos adoptados
