# 05 — Estructura del Repo y Convenciones

> Última actualización: 2026-07-09
> La regla de dependencia que gobierna esta estructura está en [02-arquitectura.md](02-arquitectura.md).

## Árbol de paquetes (plataforma core)

```
resultarai/
├── core/                        # El hexágono. Solo stdlib + Pydantic.
│   ├── manifests/               # Schemas Pydantic de los 6 manifiestos (ver 04)
│   ├── registries/              # AgentRegistry, SkillRegistry, ToolRegistry
│   ├── policy/                  # PolicyGate (función pura, deny-by-default)
│   ├── routing/                 # SkillRouter: reglas de decisión
│   └── ports/                   # Protocols: LLMPort, ToolPort, TracePort,
│                                #   PolicyPort, StatePort
├── adapters/
│   ├── llm_litellm/             # LLMPort → LiteLLM (cache profiles, canonicalización)
│   ├── runtime_langgraph/       # Graph templates; langgraph vive SOLO aquí
│   ├── tools_mcp/               # ToolPort → servidores MCP
│   ├── tools_openapi/           # ToolPort → ERP Safe Query API y REST interno
│   ├── tracing_langfuse/        # TracePort → Langfuse + OpenTelemetry
│   └── persistence_postgres/    # StatePort → Postgres (estado, audit log)
├── app/
│   ├── use_cases/               # Casos de uso: componen core + adapters
│   └── api/                     # FastAPI: transporte HTTP/WS, sin lógica
├── manifests/                   # YAML declarativos (ver 04)
│   ├── agents/  ├── skills/  ├── tools/
│   ├── policies/  ├── routing/  └── evals/
└── tests/
    ├── core/                    # Unit puros, sin mocks pesados
    └── contracts/               # Contract tests por adapter
```

Los satélites (`erp-safe-query-api/`, `edge-connector/`) tendrán su propia estructura cuando lleguen sus fases del [roadmap](07-roadmap.md).

## Responsabilidad por carpeta

| Carpeta | Responde a la pregunta | Prohibido |
|---|---|---|
| `core/` | ¿Qué existe, qué está permitido, a dónde va? | Importar frameworks o adapters; hacer I/O |
| `adapters/` | ¿Cómo se habla con X tecnología? | Decidir política o negocio; importar otros adapters |
| `app/` | ¿Cómo se compone todo para servir una petición? | Contener lógica que pertenezca a core |
| `manifests/` | ¿Qué agentes/skills/tools/políticas están declarados? | Contener código |

## Convenciones Python

- **Python 3.12+**, gestor de dependencias **uv**.
- **Typing estricto**: `mypy --strict` (o pyright) en CI; ports como `typing.Protocol`.
- **Pydantic v2** para schemas de manifiestos y modelos de datos.
- **ruff** para lint + format (reemplaza black/isort/flake8).
- Identificadores en inglés; docstrings breves en español solo cuando expliquen una restricción no evidente.

## Testing

- `tests/core/`: unit tests puros del núcleo (Policy Gate, router, validación de manifiestos). Sin mocks pesados: el núcleo no tiene I/O, se testea con datos.
- `tests/contracts/`: un contract test por adapter, verificando que cumple su port (puede usar dobles o servicios locales).
- Regla práctica: si un test de `core/` necesita un mock de red, el código está en la carpeta equivocada.

## import-linter (verificación de fronteras en CI)

```toml
# pyproject.toml
[tool.importlinter]
root_package = "resultarai"
# Requerido para poder prohibir módulos externos (langgraph, litellm, …)
include_external_packages = true

[[tool.importlinter.contracts]]
name = "El nucleo no conoce el mundo exterior"
type = "forbidden"
source_modules = ["resultarai.core"]
forbidden_modules = [
    "resultarai.adapters", "resultarai.app",
    "langgraph", "litellm", "langfuse", "fastapi", "httpx",
]

[[tool.importlinter.contracts]]
name = "Capas: app -> adapters -> core"
type = "layers"
layers = ["resultarai.app", "resultarai.adapters", "resultarai.core"]

[[tool.importlinter.contracts]]
name = "Adapters independientes entre si"
type = "independence"
modules = [
    "resultarai.adapters.llm_litellm",
    "resultarai.adapters.runtime_langgraph",
    "resultarai.adapters.tools_mcp",
    "resultarai.adapters.tools_openapi",
    "resultarai.adapters.tracing_langfuse",
    "resultarai.adapters.persistence_postgres",
]
```

## Setup de entorno

`[se completa cuando exista código — lo definirá el change OpenSpec scaffolding-esqueleto: uv sync, variables de entorno, docker compose para Postgres/Langfuse local, comandos de test/lint]`
