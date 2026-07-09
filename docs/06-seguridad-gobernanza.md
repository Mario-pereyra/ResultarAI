# 06 — Seguridad y Gobernanza

> Última actualización: 2026-07-09
> Base: blueprint capas 1 y 11, principios 2, 3, 7, 8 y 13. Términos: [03-glosario-dominio.md](03-glosario-dominio.md).

## Policy Gate

El componente de gobernanza central. **Función pura** en `core/policy`: recibe el contexto de la acción, devuelve una decisión. Sin I/O, sin estado oculto — trivialmente testeable y auditable.

```
Entrada  (ActionRequest):  usuario, tenant, agente, skill, tool,
                           operation_type (read/write), risk_level, entorno
Salida   (PolicyDecision): allow | deny | escalate_hitl  +  razón + política aplicada
```

Reglas:

1. **Deny-by-default.** Lo que ninguna Policy permite explícitamente, está bloqueado.
2. Se evalúa **en cada paso** (runtime authorization per step, blueprint patrón), no solo al inicio de la sesión.
3. Toda decisión —incluidas las permitidas— se registra en el audit log.
4. Cuando exista necesidad de políticas más formales, el `PolicyPort` permite reemplazar la implementación por OPA/Cedar sin tocar el resto.

## Niveles de riesgo y HITL proporcional

| Nivel | Ejemplos | Tratamiento |
|---|---|---|
| **low** | Lectura de datos no sensibles (parámetro SX6, datos de un cliente) | Allow si la policy lo permite |
| **medium** | Lecturas masivas, datos comerciales agregados | Allow + límites (`max_rows`, paginación, resumen) |
| **high** | Datos personales/sensibles, cruces entre tenants | `escalate_hitl`: aprobación humana previa |
| **critical** | Cualquier escritura al ERP | Fuera del MVP. Cuando llegue: MsExecAuto + HITL obligatorio + plan validado |

## Audit log (event sourcing acotado)

Registro **append-only e inmutable** de eventos de auditoría — el único lugar del sistema donde se adopta event sourcing, deliberadamente acotado a una tabla ([02-arquitectura.md](02-arquitectura.md)).

Cada `AuditEvent` registra: timestamp, usuario, tenant, agente, skill, tool, parámetros (resumidos/enmascarados), decisión del Policy Gate, política aplicada, resultado (resumen), costo y trace_id de Langfuse. Prohibido: UPDATE o DELETE sobre esta tabla; correcciones = evento nuevo que referencia al anterior.

## Data boundaries y aislamiento por tenant

1. **Qué puede salir a modelos externos:** prompts e instrucciones, sí; datos del ERP recuperados por una skill, solo los campos que la tool devuelve tras `mask_sensitive_fields`. Secretos y credenciales, nunca (ni en prompts ni en logs ni en memoria).
2. **Aislamiento por tenant:** un usuario consultando el tenant Totalpec no puede recibir datos de Unión. El tenant es parámetro obligatorio de toda tool ERP y el Policy Gate valida la autorización usuario↔tenant.
3. **Caché aislada por tenant** (blueprint patrón "Cache Isolation by Tenant"): los prefijos cacheables no mezclan datos entre tenants.
4. **La ERP Safe Query API es la única puerta al ERP.** Sin SQL libre, sin acceso dinámico a tablas; allowlist de tablas/campos y plantillas parametrizadas del lado del servidor, junto al Protheus del cliente.

## Plan-then-Execute para skills ERP (obligatorio)

Toda skill que toque el ERP usa el graph template `plan_then_execute_graph`:

1. El LLM genera el **plan completo** (qué tools, con qué parámetros, en qué orden).
2. El Policy Gate valida **cada paso del plan** antes de ejecutar nada.
3. El ejecutor corre el plan aprobado **sin desviarse**; si un resultado exige replanificar, se genera un plan nuevo que vuelve a validarse.

Por qué: además de gobernanza, mitiga prompt injection — un documento o resultado malicioso no puede secuestrar la ejecución a mitad de camino, porque el plan ya está fijado y validado (fuentes en [ADR-0003](adr/0003-stack-langgraph-litellm-langfuse-mcp.md)).

## Estrategia de evals: placeholder por diseño

Adoptamos el principio 16 del blueprint: **evaluaciones preparadas, no necesariamente definidas.**

- Todo agente, skill y tool nace con su `EvalTemplateManifest` (status `placeholder`) — reservar el espacio es obligatorio; llenar el dataset, no.
- Las trazas de Langfuse del MVP son la materia prima: los casos reales de uso se convertirán en datasets de regresión.
- Cuando una skill entre en uso productivo regular, su eval pasa de `placeholder` a real y se vuelve gate de CI (Evaluation-as-Code, blueprint capa 12). Métricas previstas por manifiesto: `metrics_planned`.

## Incidentes y kill switch

- Desactivar una skill o tool = cambiar su manifiesto a `status: deprecated` y recargar registries (kill switch por alcance, sin apagar la plataforma).
- Incidente de datos (fuga, respuesta con datos de otro tenant): desactivar la skill afectada, preservar el audit log y las trazas, reconstruir la ejecución con el trace_id.
- `[se completa cuando exista código: procedimiento operativo de recarga y contactos]`
