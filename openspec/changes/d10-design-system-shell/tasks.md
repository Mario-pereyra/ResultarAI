## 1. Scaffold del frontend

- [x] 1.1 Crear `frontend/` con Next.js (App Router) + TypeScript: `package.json`, `tsconfig.json`, estructura mínima (`app/`, `public/`, `scripts/`). Verificación: `npm run dev` levanta una página en blanco sin errores de consola. `[modelo: sonnet]`
- [x] 1.2 Agregar `@assistant-ui/react` como dependencia (ADR-0007, sin uso funcional todavía — llega en `d13-chat-conversacion`) y documentarlo en `frontend/README.md`. Verificación: `npm ls @assistant-ui/react` resuelve sin conflictos de versión. `[modelo: haiku]`
- [x] 1.3 Configurar ESLint (`next/core-web-vitals` + `@typescript-eslint`) y `tsc --noEmit` como scripts `lint`/`typecheck` en `package.json`. Verificación: `npm run lint` y `npm run typecheck` terminan en verde sobre el scaffold vacío. `[modelo: sonnet]`
- [x] 1.4 Configurar `next-intl`: `messages/es.json` inicial + provider en el layout raíz. Verificación: la página raíz renderiza un texto de prueba resuelto desde el catálogo, no hardcodeado. `[modelo: sonnet]`

## 2. CI del frontend

- [ ] 2.1 Agregar job `frontend` a `.github/workflows/ci.yml` (creado por `a01-fundacion-repo`): `npm ci`, `npm run lint`, `npm run typecheck`, `npm run build`, en paralelo a los jobs Python existentes. Verificación: workflow en verde en GitHub sobre este PR. `[modelo: sonnet]`
- [ ] 2.2 Agregar cache de dependencias npm al job (`actions/setup-node` con `cache: npm`). Verificación: la segunda corrida del job muestra cache hit en el log de Actions. `[modelo: haiku]`

## 3. Tokens (design-system)

- [ ] 3.1 Portar los tokens globales (tipografía, espaciado, radios, sombras por variable, motion, z-index, breakpoints) de `design/mockups/tokens.css` §2 a la hoja de tokens del frontend, bajo `:root`. Verificación: escenario "Escala de espaciado completa" de `specs/design-system/spec.md`. `[modelo: haiku]`
- [ ] 3.2 Portar verbatim los 4 sets de tokens de color tema×brand (`design/mockups/tokens.css` §3.1–3.4). Verificación: escenario "Los 4 sets están completos" y "dark·default es el tema por defecto de la instancia". `[modelo: haiku]`
- [ ] 3.3 Cargar Chakra Petch, Saira y JetBrains Mono, y aplicar `tabular-nums` a las clases `.mono`/`.num`. Verificación: escenario "Columna numérica alineada". `[modelo: haiku]`
- [ ] 3.4 Importar la hoja de tokens globalmente en el layout raíz de Next.js; resolver `data-theme`/`data-brand` en SSR sin flash de tema incorrecto (FOUC). Verificación: recarga de página no muestra parpadeo de tema. `[modelo: sonnet]`

## 4. Componentes base (design-system)

- [ ] 4.1 Implementar botón (`.btn` primary/secondary/danger/ghost, tamaños sm/lg/block, estados default/hover/focus-visible/active/disabled/loading) como componente React con ARIA. Verificación: escenario "Botón primario con estado de carga". `[modelo: sonnet]`
- [ ] 4.2 Implementar input/textarea/select (`.field`/`.input`/`.textarea`/`.select`) con label asociado, hint, error y `aria-describedby`/`aria-invalid`. Verificación: test de accesibilidad (label↔control, error anunciado). `[modelo: sonnet]`
- [ ] 4.3 Implementar tabla de datos densa (`.table-wrap`/`.table`/`.table--dense`) con soporte de columnas numéricas mono. Verificación: escenario "Tabla densa con datos monoespaciados". `[modelo: sonnet]`
- [ ] 4.4 Implementar panel/card (`.panel`, variantes flush/raised) y tag/badge-rol (`.tag`, `.badge-rol`). Verificación: variantes de `design/DESIGN-SYSTEM.md` §8.5/§8.6 renderizadas en el styleguide. `[modelo: sonnet]`
- [ ] 4.5 Implementar toast (`.toast-stack`/`.toast`) con `aria-live` y auto-cierre configurable (persistente en warn/danger). Verificación: test de comportamiento — toast warn/danger no se auto-cierra. `[modelo: sonnet]`
- [ ] 4.6 Implementar modal (`.overlay`/`.modal`) con trampa de foco, cierre por `Esc` y retorno de foco al disparador. Verificación: escenario "Modal con trampa de foco". `[modelo: sonnet]`
- [ ] 4.7 Implementar dropdown genérico (base para menú de usuario y campana) con navegación por flechas y `Esc`. Verificación: test de teclado — flechas mueven el foco entre ítems, `Esc` cierra y devuelve foco. `[modelo: sonnet]`
- [ ] 4.8 Implementar tooltip (`[data-tip]`) accesible por hover y focus, y componentes skeleton/empty-state. Verificación: tooltip visible en `focus-visible` sin uso de mouse. `[modelo: sonnet]`
- [ ] 4.9 Agregar auditoría de colores hardcodeados (script que falla si aparece un hex/`rgb()`/`rgba()` fuera de la capa de tokens) al job de CI. Verificación: escenario "Auditoría estática sin hex hardcodeado" ejecuta en CI. `[modelo: sonnet]`

## 5. Shell de aplicación (app-shell)

- [ ] 5.1 Crear `SessionContext` mock (`user.role`, `gateway.status`, `pendingApprovals`, `capabilities`) con provider de desarrollo que permite alternar rol (p. ej. query param), documentado como contrato temporal para `d11-identidad-acceso` (design.md decisión 6). Verificación: alternar el rol desde el entorno de desarrollo cambia el shell renderizado. `[modelo: sonnet]`
- [ ] 5.2 Crear `capabilities.ts` con la matriz estática de secciones por rol (tabla "Diferencias por rol" de `design/VISTAS/01-acceso-shell.md` Vista 3), documentado como contrato temporal para `d20-gobernanza-plataforma`. Verificación: test unitario recorre los 3 roles y compara contra la tabla del design. `[modelo: sonnet]`
- [ ] 5.3 Construir sidebar: ítems fijos con orden de `design/mockups/03-shell.html`, filtrado por `capabilities.ts`, colapso a 64px persistido por usuario, badge de aprobaciones pendientes. Verificación: escenarios "Rol Funcional no ve secciones de Admin" y "Rol Admin ve todas las secciones". `[modelo: sonnet]`
- [ ] 5.4 Construir topbar: buscador con atajo `Ctrl/⌘+K`, switcher de tema persistido, campana (`.notif-bell`, placeholder visual — el backend de notificaciones llega en `d12-notificaciones`), menú de usuario con badge de rol. Verificación: escenarios "Badge de rol visible en el menú de usuario" y "Alternar tema persiste entre sesiones". `[modelo: sonnet]`
- [ ] 5.5 Construir banner IA (`.ai-banner`) permanente sin control de cierre, presente en todo layout autenticado, con versión acortada en móvil. Verificación: escenarios "Banner presente sin acción de cierre" y "Banner se acorta en móvil sin desaparecer". `[modelo: sonnet]`
- [ ] 5.6 Implementar estado global `GATEWAY_OFFLINE` (error-card con reintento) sin bloquear la navegación del shell, con redacción adaptada por rol. Verificación: escenarios "Gateway caído no bloquea el shell" y "Redacción del error se adapta al rol". `[modelo: sonnet]`
- [ ] 5.7 Implementar responsive del shell: sidebar → drawer `<768px` con trampa de foco, cierre por scrim/`Esc`/swipe, y skip-link "Saltar al contenido" como primer foco. Verificación: escenarios "Drawer con trampa de foco en móvil" y "Skip-link es el primer foco". `[modelo: sonnet]`

## 6. i18n fundacional (i18n-foundation)

- [ ] 6.1 Externalizar todos los textos del shell y de los componentes base a `messages/es.json`, redactados en voseo. Verificación: escenarios "Auditoría de strings hardcodeados" y "Textos del shell en voseo". `[modelo: haiku]`
- [ ] 6.2 Verificar layouts con textos un 25% más largos (fixture de prueba sobre botones/labels del shell) sin desbordes ni recortes. Verificación: escenario "Botón con texto 25% más largo no rompe el layout" (test visual/snapshot). `[modelo: sonnet]`
- [ ] 6.3 Configurar plurales ICU para el contador de notificaciones no leídas y formatos `Intl` es-BO para fecha/número en el styleguide. Verificación: escenarios "Contador de notificaciones no leídas" y "Formato de fecha en es-BO". `[modelo: sonnet]`

## 7. Verificación de accesibilidad AA y styleguide

- [ ] 7.1 Escribir `scripts/check-contrast.ts`: calcula ratios WCAG sobre los pares de `design/DESIGN-SYSTEM.md` §5.3 para las 4 combinaciones tema×brand y lo agrega al job de CI. Verificación: escenario "Verificación automatizada de contraste" en verde. `[modelo: sonnet]`
- [ ] 7.2 Verificar foco visible (`:focus-visible`, anillo 2px + offset) y orden de tabulación igual al orden visual en todos los componentes base. Verificación: escenario "Foco visible en todo interactivo". `[modelo: sonnet]`
- [ ] 7.3 Construir página `/styleguide` con mini-switcher de tema/brand (equivalente a `design/mockups/00-styleguide.html`) y demo de cada componente base. Verificación: escenario "Styleguide renderiza los 4 sets". `[modelo: sonnet]`

## 8. Cierre

- [ ] 8.1 Actualizar `CLAUDE.md` (Mapa del repo: agregar `frontend/`; Comandos: `npm run dev`/`lint`/`typecheck`/`build`) y `frontend/README.md` documentando el contrato temporal de `SessionContext`/`capabilities.ts` para `d11`/`d20`. Verificación: comandos copiables funcionan. `[modelo: haiku]`
- [ ] 8.2 Review final del change: componentes usan solo tokens semánticos (sin hex hardcodeado), los 24 escenarios de `specs/` están cubiertos, CI en verde, consistencia con `design/`. Verificación: checklist del reviewer en el PR. `[modelo: opus]`
