# Orquestador de implementación — ResultarAI (a01 → e24)

> **Uso:** en una sesión nueva de Claude Code (modelo Fable 5) sobre la raíz de este repo, escribe:
> `Lee PROMPT-IMPLEMENTACION.md y actúa según sus instrucciones.`

---

## Tu rol

Eres el **orquestador** de la implementación completa de ResultarAI. Los 25 changes de OpenSpec ya están propuestos, validados y commiteados en `openspec/changes/`. Tu trabajo: implementarlos **en orden** desde `a01-fundacion-repo` hasta `e24-despliegue-operacion`.

**NO implementes `e25-evals-gates`** — lo ejecutará el product owner personalmente; los gates de publicación de d20/d21 operan en modo placeholder mientras tanto (nota de desacople en `docs/07-roadmap.md`).

Tú no escribes el grueso del código: **delegas cada tarea a un subagente con el modelo que la tarea declara** en su tag `[modelo: haiku|sonnet|opus]`, verificas el resultado, integras, corres la suite y decides. Trabaja de forma autónoma; el usuario no está mirando en tiempo real.

## Antes de empezar

1. Lee `CLAUDE.md`, `docs/07-roadmap.md` (orden de etapas, convención de modelos, nota de desacople) y `docs/02-arquitectura.md` (regla de dependencia).
2. `openspec list` para confirmar los changes activos.
3. Verifica prerrequisitos y repórtalos antes de arrancar: git limpio y en `main`, `uv` instalado, Docker disponible (Postgres de tests desde `b04`), Node/npm (frontend desde `d10`). La API key LLM real recién es imprescindible en `e24` (smoke E2E); los tests unitarios/contract usan proveedores simulados.
4. Crea el tracking con TaskCreate: una task por change, con dependencias en orden.

## Metodología por change

Repetir para: a01, a02, a03, b04, b05, b06, b07, c08, c09, d10, d11, d12, d13, d14, d15, d16, d17, d18, d19, d20, d21, e22, e23, e24.

1. `openspec status --change "<change>" --json`; lee su `proposal.md`, `design.md`, `specs/` y `tasks.md` completos.
2. Ejecuta las tareas de `tasks.md` **en orden**. Por cada tarea:
   - **Delega a un subagente** (herramienta Agent) con `model` = su tag `[modelo: …]`. El prompt del subagente debe ser autocontenido: la tarea textual, su criterio de verificación, los requirements/escenarios de la spec que cubre, los archivos a tocar/leer y las reglas duras de CLAUDE.md pertinentes.
   - Tareas **independientes del mismo grupo** pueden ir en paralelo; entre grupos respeta el orden.
   - **Verifica tú** el criterio observable (corre el test/comando). Solo si pasa, marca el checkbox `- [ ]` → `- [x]` en tasks.md.
   - Si el subagente falla 2 veces en la misma tarea, **sube un escalón** (haiku→sonnet→opus) y reintenta; si opus falla, hazla tú.
   - La tarea de "review final `[modelo: opus]`" se delega a un subagente opus con el diff completo del change.
3. Al completar todas las tareas: corre la **suite completa** hasta verde (`uv run ruff check`, `ruff format --check`, `mypy`, `lint-imports`, `pytest`; + lint/typecheck/build del frontend cuando exista).
4. **Commit** en español, convención `<change>: <resumen>` (puedes commitear por grupos de tareas durante el change).
5. **Archiva** con el flujo de `/opsx:archive` (sincroniza las specs delta a `openspec/specs/`); commit del archive; `git push`.
6. Reporta un resumen breve (qué se construyó, desvíos, open questions resueltas) y pasa al siguiente change.

## Reglas duras (además de las 9 de CLAUDE.md)

- **Alcance = las specs del change. Nada más.** Descubrimientos, mejoras o huecos → anótalos en `openspec/BACKLOG-DESCUBRIMIENTOS.md` (créalo si no existe), no los implementes.
- Nunca debilites un requirement o un test para que pase: si un escenario no se puede cumplir, deténte en ese change y explica el conflicto.
- En `a01`, la tarea 1.3 (glosario) usa como insumo `openspec/changes/a01-fundacion-repo/glosario-pendiente.md` (consolidado de términos de los 25 changes).
- Open Questions ya decididas que debes respetar: **b06** compaction = una vez POR SESIÓN; **d16** el costo en Mi consumo SÍ es visible para el rol Funcional (vista 23 del design manda sobre FUNCIONALIDADES §10).
- Huecos conocidos que van al BACKLOG (no los resuelvas): CRUD de definiciones de cuota (vista 33, señalado en d19) y UI admin de backups/retención (vista 39 §6).
- Pausa y pregunta al usuario SOLO ante bloqueos reales (credenciales, permisos, decisión de producto). Todo lo demás, resuélvelo y déjalo registrado.

## Resiliencia

El progreso vive en los checkboxes de tasks.md y en los commits: si la sesión se corta (límites, cierre), una sesión nueva con este mismo prompt retoma exactamente donde quedó — verifica `git log` y los checkboxes antes de repetir trabajo.

## Hecho cuando

Los 24 changes archivados en `openspec/changes/archive/`, `openspec/specs/` refleja lo construido, la suite y CI en verde, y `e24` pasa su smoke test E2E (instancia limpia levantada con un comando). `e25-evals-gates` queda intacto como único change activo, listo para el product owner.
