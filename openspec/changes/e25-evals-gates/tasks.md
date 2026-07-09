# Tasks — e25-evals-gates

> **EJECUTA EL PRODUCT OWNER (al final).** Este change se especifica ahora pero lo implementa el product owner cuando el resto de la plataforma ya funciona. **Prerrequisitos antes de empezar:**
> 1. `d20-gobernanza-plataforma` y `d21-builders` **archivados** (los gates existen en modo placeholder listos para enchufarse).
> 2. `b07-observabilidad` **operativo**: trazas, costo y feedback 👍/👎 ligados a traza y versión de prompt; API de scores de Langfuse disponible.
> 3. **API key** de al menos un proveedor LLM configurada en el gateway de modelos (`b05-gateway-modelos`).
> 4. **Instancia levantada** con `e24-despliegue-operacion` (plataforma, Postgres, Langfuse) para correr el runner de punta a punta.
>
> Regla de datos: **solo datos sintéticos** en todo dataset (jamás datos reales de clientes).

## 1. Datasets sintéticos y contrato del caso

- [ ] 1.1 Crear `evals/` y documentar el schema del caso (`input`, salida esperada o criterios deterministas, `category`, marca `safety`); incluir un dataset mínimo de ejemplo. Verificación: el dataset de ejemplo valida contra el schema. `[modelo: haiku]`
- [ ] 1.2 Escribir los datasets sintéticos por Agent/Skill/Workflow de fábrica (`default_chat`, skill de ejemplo, workflow de ejemplo), con ≥3 casos por Skill y ≥1 caso `safety` marcado por dataset. Verificación: cada dataset valida y cumple la cobertura mínima (escenario "Cobertura mínima de datasets de Skill"). `[modelo: haiku]`
- [ ] 1.3 Vincular cada dataset a su `EvalTemplateManifest` (pasa de `status: placeholder` a real) y validar la referencia. Verificación: el manifiesto referencia el dataset y valida contra su schema Pydantic. `[modelo: haiku]`

## 2. Runner de evals

- [ ] 2.1 Implementar el runner (servicio en `app/`): carga un dataset, ejecuta cada caso vía el gateway de modelos (`b05`, nunca SDKs directos), evalúa con criterios deterministas y produce score por versión + detalle por caso. Verificación: test con gateway simulado devuelve el score y el detalle esperados. `[modelo: sonnet]`
- [ ] 2.2 Trazar cada caso en Langfuse (`b07`) con score por caso vía la API de scores; asociar la corrida al hash de contenido de la versión de prompt evaluada. Verificación: test con adapter Langfuse simulado registra un score por caso y la corrida guarda el hash (escenario "Cada caso queda trazado en Langfuse"). `[modelo: sonnet]`
- [ ] 2.3 Implementar el safety hard-fail individual: ≥1 caso `safety` en FAIL marca la corrida BLOQUEANTE sin importar el score global. Verificación: test safety en rojo con score global 95% → corrida BLOQUEANTE. `[modelo: sonnet]`
- [ ] 2.4 Exponer el runner como comando único ejecutable en local (`uv run …`) que corre una suite y reporta score + detalle con exit code según el gate. Verificación: el comando corre la suite de ejemplo y devuelve exit code 0/≠0 según ≥80% y safety. `[modelo: sonnet]`

## 3. Gate de publicación REAL (reemplaza el placeholder)

- [ ] 3.1 Diseñar el contrato del gate de publicación: decide `permitir`/`bloquear` a partir de (corrida vigente, hash del borrador) exigiendo score ≥ 80% **Y** cero `safety` en rojo; fail-closed. Verificación: tabla de decisión cubre 79%→bloquear, 95%+safety→bloquear, 85%+0safety→permitir, sin corrida→bloquear, runner caído→bloquear. `[modelo: opus]`
- [ ] 3.2 Enforcement por sistema: enchufar el gate en el punto de publicación de `d20`/`d21` reemplazando el modo placeholder; imposible saltarlo (sin override manual); cada decisión al Audit Log append-only. Verificación: intento de publicar sin corrida válida queda bloqueado y auditado; no existe checkbox de bypass. `[modelo: opus]`
- [ ] 3.3 Preservación histórica: las versiones publicadas en modo placeholder siguen válidas y activas sin re-evaluación retroactiva. Verificación: test — una versión publicada antes de enchufar el gate permanece activa tras activarlo (escenario "Publicación previa a e25 sigue siendo válida"). `[modelo: opus]`
- [ ] 3.4 Reflejar el estado del gate en el punto de publicación: motivo como texto (no solo tooltip) + detalle de casos fallados. Verificación: al no cumplir el gate se muestra el motivo y los casos fallados. `[modelo: sonnet]`
- [ ] 3.5 Publicar el score de evals vigente en la ficha técnica del Agente (`d15`). Verificación: la ficha técnica (capa T/A) muestra score + fecha; el Funcional no lo ve. `[modelo: sonnet]`

## 4. Gate de CI

- [ ] 4.1 Añadir el job de CI que corre el runner sobre los datasets de Agentes/Skills activos y bloquea el pipeline con score < 80% o ≥1 `safety` en FAIL. Verificación: el pipeline queda en rojo ante score bajo o safety FAIL, y en verde si cumple. `[modelo: opus]`

## 5. Feedback → regresión

- [ ] 5.1 Servicio de conversión: un 👎 con comentario "candidato a regresión" (`b07`) se convierte en caso candidato con `input`/`obtenido` prellenados, origen `feedback` y `esperado` vacío, tras revisión humana. Verificación: convertir un feedback crea un caso candidato en el golden set. `[modelo: sonnet]`
- [ ] 5.2 Garantizar que un candidato incompleto (sin `esperado`) no corre en CI hasta completarse. Verificación: test — el runner omite en CI un caso `feedback` sin `esperado`. `[modelo: sonnet]`

## 6. UI — vista 43-admin-evals

- [ ] 6.1 Implementar la vista `43-admin-evals` (solo Admin): suites por Agente, lanzar runs del draft, score por versión, detalle por caso e historial de corridas. Verificación: lanzar un run muestra score + detalle y la corrida aparece en el historial (`design/VISTAS/08-admin-gobernanza.md` §8.6). `[modelo: sonnet]`
- [ ] 6.2 Implementar la bandeja feedback → caso: conversión a un clic con modal prellenado y estado `candidato`/`convertido`. Verificación: convertir un 👎 crea el caso y el ítem pasa a `convertido` con enlace. `[modelo: sonnet]`
- [ ] 6.3 Reflejar el gate en la UI de publicación (vistas 34/43): botón Publicar deshabilitado con motivo cuando score < 80% o hay `safety` en rojo. Verificación: escenarios score 79% y safety-en-rojo dejan Publicar deshabilitado con el motivo visible. `[modelo: sonnet]`

## 7. Cierre

- [ ] 7.1 Review final del change: el gate es imposible de saltar (fail-closed, sin bypass), todos los datasets son sintéticos, la transición placeholder→real queda documentada y las fronteras (`core/` sin frameworks; runner en `app/` sin ports nuevos) intactas. Verificación: checklist del reviewer en el PR. `[modelo: opus]`
