# ADR-0001 — Monolito modular con núcleo hexagonal (Ports & Adapters)

- **Estado:** aceptado (2026-07-09)
- **Decisores:** fábrica de software (proyecto interno Resultar)

## Contexto

ResultarAI es una plataforma de orquestación e integración de IA para un equipo chico (1-3 devs, perfil junior). El blueprint v2.4 define 13 capas conceptuales y componentes que podrían interpretarse como servicios independientes. Había que elegir el estilo arquitectónico del código antes de escribir la primera línea.

## Decisión

Un **monolito modular en Python** como deployable principal, con **núcleo hexagonal**: `core/` (manifiestos, registries, Policy Gate, routing, ports) no importa ningún framework; LangGraph, LiteLLM, Langfuse, MCP y Postgres se integran como adapters detrás de ports (`typing.Protocol`). La frontera se verifica con import-linter en CI.

## Alternativas consideradas

1. **Microservicios (una por capa/plano del blueprint)** — rechazada: complejidad distribuida impagable para el equipo; los beneficios aparecen con equipos >10 devs.
2. **Monolito clásico por capas técnicas (n-layer)** — rechazada: no protege el núcleo de los frameworks agentic, que son la dependencia más volátil del proyecto.
3. **Event-driven / CQRS / cell-based / swarm** — rechazadas por ahora: resuelven problemas de escala o desacople que este proyecto no tiene; event sourcing se adopta solo acotado al audit log (ver [06-seguridad-gobernanza.md](../06-seguridad-gobernanza.md)).

## Consecuencias

- (+) Un solo proceso que operar, depurar y desplegar; refactorizar fronteras internas es barato mientras el dominio se descubre.
- (+) El núcleo se testea sin mocks de red ni LLMs.
- (+) Cambiar de framework agentic o proveedor LLM = reemplazar un adapter.
- (−) Escalado independiente por módulo no disponible (irrelevante a esta escala).
- (−) Exige disciplina de fronteras → mitigado con import-linter como gate de CI.

## Fuentes

- Encuesta CNCF 2025: 42% de organizaciones consolidando microservicios; adopción de service mesh 18%→8% (2023→2025) — https://blog.bytebytego.com/p/monolith-vs-microservices-vs-modular
- Amazon Prime Video: retorno a monolito, −90% de costos en un servicio — https://www.javacodegeeks.com/2025/12/microservices-vs-modular-monoliths-in-2025-when-each-approach-wins.html
- Martin Fowler, "Monolith First" — https://martinfowler.com/bliki/MonolithFirst.html
- AWS Prescriptive Guidance, Hexagonal Architecture — https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/hexagonal-architecture.html
- Alistair Cockburn & Juan M. Garrido de Paz, *Hexagonal Architecture Explained* (2024)
