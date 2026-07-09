# Tasks — b05-gateway-modelos

## 1. Contrato del port y errores (core)

- [x] 1.1 Definir/extender en `resultarai/core/ports/` el schema de salida de `LLMPort` requerido por este change: texto de respuesta, perfil usado, `is_alternate_model` + perfil primario + motivo, contadores de cache hit/miss (o ausentes), costo calculado, evento de escalación (`needs_pro`). Verificación: `tests/core/test_llm_port_contract.py` valida presencia y tipos de cada campo, sin red ni frameworks. `[modelo: opus]`
- [ ] 1.2 Definir la jerarquía de errores tipados del port (p. ej. cascada agotada, perfil sin proveedor disponible) en `resultarai/core/ports/`. Verificación: `tests/core/test_llm_port_errors.py` instancia cada error y confirma que expone perfiles intentados y causa. `[modelo: opus]`

## 2. Perfiles de modelo y cascada (configuración)

- [ ] 2.1 Definir el schema Pydantic `ModelProfile` (id, proveedor, modelo, parámetros de invocación, tarifa cache hit, tarifa cache miss) en `resultarai/core/`. Verificación: `tests/core/test_model_profile_schema.py` cubre un perfil válido y casos inválidos (tarifa faltante, proveedor vacío). `[modelo: opus]`
- [ ] 2.2 Extender el schema del Agent Manifest (`a02-core-manifiestos`) con `fallback_cascade` (lista ordenada de ids de perfil) y `escalation.enabled` (bool, default true). Verificación: test de validación cruzada que falla si `fallback_cascade` referencia un perfil inexistente o inactivo. `[modelo: opus]`
- [ ] 2.3 Escribir configuración de ejemplo de perfiles de modelo (mínimo 2 perfiles) y una cascada de ejemplo asignada a `default_chat`. Verificación: la configuración valida contra el schema de 2.1 y 2.2 vía CLI de validación. `[modelo: haiku]`

## 3. Adapter LiteLLM — invocación, cascada y contadores

- [ ] 3.1 Implementar `resultarai/adapters/llm_litellm/client.py`: invoca LiteLLM para un perfil dado y traduce su respuesta al contrato de salida del port. Verificación: contract test con proveedor simulado (sin red real) que confirma el mapeo campo a campo. `[modelo: sonnet]`
- [ ] 3.2 Implementar la ejecución de la cascada de fallback (iterar perfiles en orden, capturar fallos, detener en el primer éxito, marcar `is_alternate_model`). Verificación: test que fuerza fallo del primer perfil simulado y confirma fallback correcto al segundo con metadato completo. `[modelo: sonnet]`
- [ ] 3.3 Implementar el error de cascada agotada cuando todos los perfiles configurados fallan en la misma invocación. Verificación: test que fuerza fallo de todos los perfiles simulados y confirma el tipo de excepción de 1.2 con el detalle de cada perfil. `[modelo: sonnet]`
- [ ] 3.4 Implementar la extracción y normalización de contadores de cache hit/miss desde el `usage` reportado por LiteLLM, cubriendo el caso de ausencia de esos campos. Verificación: dos tests (usage con contadores, usage sin contadores) confirman que el contrato de salida nunca reporta cero cuando el dato está ausente. `[modelo: sonnet]`
- [ ] 3.5 Implementar el cálculo de costo aplicando la tarifa hit del perfil a los tokens hit y la tarifa miss a los tokens miss. Verificación: test que compara el costo calculado contra un cálculo manual con tarifas de un perfil de prueba. `[modelo: sonnet]`

## 4. Marcador de escalación (anti prompt-injection)

- [ ] 4.1 Implementar la función de "texto elegible para escaneo": remueve todo bloque delimitado por `<adjunto id="...">...</adjunto>` (emparejado por `id`) del texto antes de buscar el marcador; ante un delimitador sin cerrar, excluye fail-closed todo lo que sigue. Verificación: tests con adjunto bien formado con el marcador embebido, delimitador sin cerrar, e intento de cierre falsificado (`</adjunto>` propio dentro del contenido). `[modelo: opus]`
- [ ] 4.2 Implementar la detección de `<<<NEEDS_PRO>>>` sobre el texto elegible resultante de 4.1 y la emisión del evento de escalación en el contrato de salida. Verificación: tests con el marcador presente fuera de adjuntos, ausente, y presente solo dentro de un adjunto (no debe disparar). `[modelo: opus]`
- [ ] 4.3 Conectar la detección con `escalation.enabled` del Agent Manifest (2.2): si está deshabilitado, la detección no se ejecuta para ese agente. Verificación: test con agente configurado deshabilitado (marcador presente pero sin evento) y agente habilitado (evento emitido). `[modelo: sonnet]`

## 5. Tests de contrato con proveedor simulado

- [ ] 5.1 Construir el doble de proveedor (`tests/contracts/llm_litellm/fake_provider.py`) parametrizable por perfil: éxito, error, timeout, usage con cache hit/miss, usage sin esos campos. Verificación: el doble reemplaza toda llamada real a LiteLLM en los tests de las secciones 3 y 4; ningún test de esta sección requiere red. `[modelo: sonnet]`
- [ ] 5.2 Escribir el contract test que recorre los escenarios de las specs `model-gateway`, `model-profiles` y `escalation-marker` contra el adapter completo. Verificación: `uv run pytest tests/contracts/llm_litellm/` en verde sin acceso a red. `[modelo: sonnet]`

## 6. Cierre

- [ ] 6.1 Actualizar `docs/03-glosario-dominio.md` con los términos nuevos introducidos por este change: Perfil de modelo (`ModelProfile`), Cascada de fallback, Modelo alterno, Marcador de escalación, Cache hit/miss. Verificación: cada término usado en proposal/specs/design de `b05-gateway-modelos` existe en el glosario con la misma grafía. `[modelo: haiku]`
- [ ] 6.2 Review final del change: contrato consistente entre `core/ports`, el adapter y las tres specs; ningún import de SDK de proveedor fuera de `adapters/llm_litellm`; cascada, contadores y marcador cubiertos por tests con proveedor simulado. Verificación: checklist del reviewer en el PR + `uv run lint-imports` en verde. `[modelo: opus]`
