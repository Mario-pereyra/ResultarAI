# Design — d21-builders

## Context

Cierre de la Etapa D: la plataforma ya gobierna prompts, flags, tools y matrices (`d20`), muestra el catálogo por rol (`d15`) y ejecuta Skills conformes a la spec Agent Skills (`c08`) con Tools MCP clasificadas (`c09`). Falta la superficie de **creación**: hoy un agente o una Skill nuevos exigen editar YAML y abrir un PR. `design/VISTAS/09-builders.md` (vistas 41 y 42) fija los dos builders solo-Admin, y `design/FUNCIONALIDADES.md` §13 agrega las propuestas guiadas de Técnicos y el sandbox self-service. El runner de evals (`e25-evals-gates`) lo ejecuta el product owner al final: los gates de este change nacen pluggables en modo placeholder (Nota de desacople, `docs/07-roadmap.md`).

## Goals / Non-Goals

**Goals:**

- Agent Builder que produce versiones de `AgentManifest` + versión de prompt en el Registro de Prompts (`d20`) sin poder violar ninguna regla dura por construcción (prefijo cache-safe intocable, toolset/skillset horneados por versión, HITL heredada no editable).
- Skills Builder que produce paquetes conformes a la spec Agent Skills + `SkillManifest`, con validación en vivo y gate de ≥3 casos de eval declarados (dataset para `e25`).
- Registro de skills consultable (Técnico solo lectura), propuestas guiadas de Técnicos con aprobación del Admin, y sandbox self-service sin escrituras con promoción sujeta al gate completo.

**Non-Goals:**

- Ejecutar o puntuar evals (`e25`), builder visual de workflows (excluido por el design), skills con escritura ERP (Etapa P), re-especificar el Registro de Prompts, las matrices o el kill-switch (`d20`).

## Decisions

1. **Los builders escriben en Postgres, no en Git; el YAML de `manifests/` queda como bootstrap + espejo.** Las versiones de agente y de skill creadas por los builders viven en Postgres (misma decisión que ADR-0011 para prompts: la DB es la fuente de runtime, sin deploy). Al publicar, el sistema exporta un snapshot (paquete `SKILL.md` a `manifests/skills/packages/<slug>/`; manifiesto YAML espejo) para code review y para que el loader de `c08` funcione sin cambios. Alternativa descartada: builders que commitean a Git vía bot — acopla la UX de un Admin a la latencia y permisos de Git y duplica el flujo de PR que el pivote quiso reservar para cambios de clasificación de riesgo.
2. **El prefijo cache-safe no forma parte del payload editable.** No es "un campo bloqueado en la UI": el contrato de la API de borradores simplemente no tiene un campo para el prefijo; la plataforma lo compone en runtime a partir de la identidad del agente. Así la garantía es estructural (imposible por construcción), no cosmética. Alternativa descartada: validar que el prefijo enviado coincida con el esperado — deja la puerta a drift y a bypasses.
3. **Un solo modelo de "borrador de versión" compartido por ambos builders** (estado, lock optimista de edición concurrente, autosave, un-borrador-por-entidad, `AuditEvent` por transición). Evita dos implementaciones divergentes de la misma máquina de estados; las diferencias (pasos del wizard, gates) son estrategia por tipo. El lock optimista con `EDIT_LOCKED` para el segundo Admin viene del design (vistas 41/42, estado Degradado).
4. **El gate del Agent Builder ES el gate pluggable de `d20`; el gate del Skills Builder es propio y de conteo.** Activar una versión de agente delega en el contrato placeholder/enforcing ya especificado en `prompt-registry` (`d20`) — un solo gate de score en la plataforma. El Skills Builder agrega un gate distinto e independiente del runner: ≥3 casos **declarados** (conteo verificable hoy, sin ejecutar nada); los casos quedan versionados con la skill como dataset que `e25` ejecutará. Alternativa descartada: esperar a `e25` para exigir casos — perdería la disciplina de "toda skill nace con evals declaradas" (principio 16 del blueprint).
5. **Propuestas de Técnicos = entidad `proposal` separada, no borradores con permisos débiles.** Una propuesta pendiente no es un `draft` del builder: vive en su propia tabla con template fijo + secciones editables + toolset filtrado por la matriz rol×tool (validado también en servidor). Aprobar la **convierte** en un borrador normal del builder (desde ahí, flujo Admin idéntico). Evita que un permiso mal configurado exponga borradores de Técnicos al runtime.
6. **Sandbox = mismo runtime con contexto `sandbox` y policy deny-de-escrituras, no un runtime aparte.** Las construcciones sandbox se ejecutan por el mismo Policy Gate y camino de ejecución que producción, con dos diferencias declarativas: el selector solo lista Tools `read` y ninguna Policy otorga `allow` de escritura en contexto sandbox (deny-by-default hace el resto). Visibilidad: solo el creador. Alternativa descartada: entorno clonado — costo operativo alto y divergencia de comportamiento que invalidaría la prueba.

## Risks / Trade-offs

- [Dos fuentes de manifiestos (YAML de fábrica + versiones en DB) pueden divergir] → Mitigación: precedencia única documentada (DB manda cuando existe una versión para esa entidad; el YAML solo siembra la instancia); el espejo Git se regenera en cada publicación y CI valida que el espejo parsea con los schemas de `a02`.
- [El modo placeholder permite publicar agentes sin ninguna evaluación] → Mitigación: decisión explícita del roadmap (Nota de desacople); la advertencia es visible y queda en el `AuditEvent`; `e25` cambia a enforcing sin tocar los builders (el gate es un contrato inyectado).
- [Los casos de eval declarados pueden ser triviales o de relleno para pasar el conteo] → Mitigación aceptada como límite del gate de conteo: la calidad de los casos la impone la revisión humana ahora y el runner + score de `e25` después (un caso trivial fallará o será inútil en enforcing).
- [Superficie de escritura amplia (builders + propuestas + sandbox) sobre entidades críticas] → Mitigación: todas las mutaciones pasan por casos de uso de `app/` con `AuditEvent` append-only; los invariantes duros (prefijo, HITL heredada, clasificación fija) no son campos del contrato, así que no hay nada que "proteger con validación": no existen en el payload.
- [Concurrencia de edición entre Admins] → Mitigación: lock optimista compartido (decisión 3) con estado solo-lectura y `EDIT_LOCKED`, según el design.

## Migration Plan

Sin migración de datos: las entidades nuevas (borradores, versiones, propuestas, construcciones sandbox) nacen vacías. Los manifiestos de fábrica existentes siguen operando como bootstrap; la primera edición de un agente de fábrica desde el builder crea su primera versión en DB. Rollback = desactivar las rutas de builders (feature flag de `d20`); nada del runtime existente depende de ellas.

## Open Questions

*(ninguna — el formato exacto del template fijo de propuestas y los textos de UI se toman de `design/VISTAS/09-builders.md` y `design/FUNCIONALIDADES.md` §13 durante la implementación)*
