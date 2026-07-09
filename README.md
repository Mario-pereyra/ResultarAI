# ResultarAI

Plataforma interna de IA de **Resultar Soluciones** (partner oficial de TOTVS en Bolivia): un chat gobernado con agentes, skills y tools que consultan sistemas de la empresa y de sus clientes —empezando por el ERP Protheus— de forma segura, auditable y sin acceso directo a bases de datos.

**Estado:** fase de diseño (greenfield, sin código todavía). La arquitectura ya está decidida y documentada.

## Documentación

| Documento | Contenido |
|---|---|
| [docs/01-vision.md](docs/01-vision.md) | Qué es, para quién, alcance del MVP y no-objetivos |
| [docs/02-arquitectura.md](docs/02-arquitectura.md) | Arquitectura adoptada, bounded contexts y reglas de dependencia |
| [docs/07-roadmap.md](docs/07-roadmap.md) | Fases de construcción y su vínculo con OpenSpec |
| [docs/adr/](docs/adr/) | Decisiones de arquitectura con evidencia y fuentes |
| [CLAUDE.md](CLAUDE.md) | Guía operativa para agentes de código (Claude Code) |

El desglose de trabajo se gestiona con [OpenSpec](https://openspec.dev/) en `openspec/`.

Los documentos de referencia (blueprint arquitectónico v2.4 y contexto de la empresa) viven en [docs/referencias/](docs/referencias/).
