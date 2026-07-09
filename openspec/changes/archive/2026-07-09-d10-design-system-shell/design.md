## Context

Primer change de frontend del monorepo. No existe todavía `frontend/` ni ningún artefacto de Next.js/assistant-ui (ADR-0007, decidido en el design de `a01-fundacion-repo`, formalizado como ADR real cuando `a01` se implemente). `design/` es la fuente normativa: `design/mockups/tokens.css` (1148 líneas, CSS real y funcional, no solo documentación) ya define los 4 sets de tokens y las clases base de cada componente (`.btn`, `.input`, `.table`, `.modal`, `.hitl-card`, etc.) con anatomía, estados y accesibilidad completos. `design/DESIGN-SYSTEM.md` documenta el *porqué* y las reglas de uso; `design/VISTAS/01-acceso-shell.md` Vista 3 especifica el shell con datos, estados y diferencias por rol. No existe backend de sesiones/roles todavía (`d11-identidad-acceso` es posterior): el shell necesita un mecanismo de datos de rol/identidad mockeable hoy y reemplazable sin tocar componentes cuando `d11` aporte sesiones reales.

## Goals / Non-Goals

**Goals:**

- Scaffold de `frontend/` con Next.js + TypeScript + assistant-ui como dependencia (ADR-0007), lint y typecheck propios integrados a CI.
- Tokens y componentes base con trazabilidad 1:1 a `design/mockups/tokens.css` (mínima reinvención, máxima fidelidad).
- Shell funcional (sin backend real) que demuestra el filtrado por capacidades de rol con datos de ejemplo.
- Punto de extensión estable para que `d11`–`d21` construyan vistas sin tocar el shell ni los componentes base.

**Non-Goals:**

- Sesiones reales, autenticación, backend de la plataforma (`d11` y Etapa B).
- Chat, streaming, assistant-ui en uso real (`d13`).
- Configuración de la matriz de capacidades como dato editable (`d20`).

## Decisions

1. **CSS: portar `tokens.css` casi verbatim como hoja de estilos global, componentes React como envoltorios finos sobre las clases ya definidas** (`.btn`, `.input`, `.table`, `.modal`, `.panel`, `.tag`, `.toast`, etc.), en vez de reimplementar los estilos con CSS-in-JS o Tailwind. Alternativa Tailwind descartada: reescribir 1148 líneas de CSS ya validado (con matriz de contraste calculada) a utilidades introduce riesgo de desviación silenciosa de los valores exactos; los componentes React solo agregan semántica HTML, ARIA y comportamiento (trampa de foco, `aria-live`, etc.) sobre las clases existentes. Alternativa CSS Modules por componente descartada por ahora: duplicaría selectores que `tokens.css` ya resuelve de forma centralizada; se reconsiderará si el árbol de componentes crece lo suficiente como para necesitar scoping.
2. **Gestor de paquetes del frontend: npm** (lockfile `package-lock.json`). Alternativa pnpm descartada por ahora: el monorepo tiene un solo paquete de frontend (no hay todavía workspaces que justifiquen pnpm); se revisará si `frontend/` se subdivide en paquetes.
3. **i18n: `next-intl`** (soporta App Router, Server Components, ICU MessageFormat con plurales nativos). Alternativas `react-intl` (sin soporte de Server Components) y `lingui` (mayor superficie de build tooling) descartadas por ahora.
4. **Verificación de contraste AA: script Node/TS (`scripts/check-contrast.ts`) que calcula ratios WCAG sobre los pares de `design/DESIGN-SYSTEM.md` §5.3 para las 4 combinaciones**, ejecutado en CI. Alternativa: verificación manual únicamente vía styleguide — descartada porque no es reproducible en CI ni bloquea regresiones.
5. **Styleguide interno en vez de Storybook**: página `/styleguide` (ruta de desarrollo, no expuesta en producción) que replica `design/mockups/00-styleguide.html` con el mini-switcher de tema/brand. Alternativa Storybook descartada por ahora: agrega un toolchain completo (builder, addons, CI job propio) para un inventario de ~11 componentes; se reconsiderará cuando el catálogo de componentes crezca con los slices de la Etapa D.
6. **Datos de rol/identidad del shell: `SessionContext` mockeable** — un React Context con la forma `{ user: { name, role }, gateway: { status }, pendingApprovals: number, capabilities: string[] }`, poblado en este change por un provider de desarrollo con datos ficticios (roles Admin/Técnico/Funcional intercambiables desde el styleguide o una query param de desarrollo). `d11-identidad-acceso` reemplaza el provider por uno que lee la sesión real sin cambiar la forma del contexto ni los componentes que lo consumen.
7. **Matriz de capacidades: mapa estático `capabilities.ts`** con la tabla "Diferencias por rol" de `design/VISTAS/01-acceso-shell.md` Vista 3, tipado como `Record<Role, Section[]>`. `d20-gobernanza-plataforma` reemplaza la fuente por configuración de instancia sin cambiar la interfaz de consumo del sidebar (mismo tipo `Section[]` resuelto, distinto origen de datos).
8. **CI**: nuevo job `frontend` en `.github/workflows/ci.yml` (creado por `a01-fundacion-repo`) que corre `npm ci`, `npm run lint`, `npm run typecheck`, `npm run build` y el script de contraste, en paralelo a los jobs Python existentes.

## Risks / Trade-offs

- [Fidelidad de portado de `tokens.css`] → Mitigación: el script de contraste (decisión 4) verifica los valores efectivos en runtime, no solo que el archivo se copió; cualquier desviación de valor falla en CI.
- [`SessionContext` mock queda "pegado" y `d11` lo hereda sin reemplazar] → Mitigación: la tarea de cierre de este change deja documentado en el propio código (comentario + README de `frontend/`) que el provider es temporal y cuál es el contrato que `d11` debe preservar.
- [Divergencia entre componentes React y clases de `tokens.css` con el tiempo] → Mitigación: los componentes no definen CSS propio fuera de las clases existentes; cualquier estilo nuevo necesario se agrega primero a `tokens.css`-equivalente del frontend, nunca inline.
- [Next-intl añade curva de aprendizaje para changes futuros] → Mitigación: este change documenta el patrón de catálogo (una carpeta `messages/es.json` con claves por sección) que los slices siguientes solo extienden.

## Migration Plan

1. Scaffold `frontend/` (Next.js + TS) y CI del frontend antes de portar tokens (para que el pipeline valide desde el primer commit).
2. Portar tokens globales y los 4 sets de tema×brand; verificar con el script de contraste.
3. Construir componentes base envolviendo las clases de `tokens.css`.
4. Construir el shell (`SessionContext` mock + `capabilities.ts` + sidebar/topbar/banner).
5. Construir `/styleguide` como verificación visual final.

No hay rollback especial: el change no toca `resultarai/` (backend) ni datos existentes; revertir es eliminar `frontend/` y el job de CI.

## Open Questions

*(ninguna — las decisiones quedan tomadas arriba; `d11` y `d20` documentarán el reemplazo de los mocks cuando lleguen)*
