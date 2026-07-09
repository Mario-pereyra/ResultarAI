# Proposal — d10-design-system-shell

## Why

El pivote 2026-07-09 fija `design/` como fuente normativa de producto y UX y adopta Next.js + assistant-ui como frontend (ADR-0007 de `a01-fundacion-repo`). Hasta ahora ningún change de la Etapa D tiene dónde vivir: no existe scaffold de frontend, ni tokens de theming portados desde `design/mockups/tokens.css`, ni shell de aplicación. Este es el primer change de frontend (puede ejecutarse en paralelo con la Etapa B, ver `docs/07-roadmap.md`) y habilita a `d11`–`d21` a construir vistas sobre una base común: componentes, tema y navegación por capacidades de rol.

## What Changes

- Se crea `frontend/` en el monorepo: Next.js + TypeScript + assistant-ui (ADR-0007), con lint (ESLint) y typecheck (`tsc --noEmit`) propios, integrados a CI junto al pipeline Python existente de `a01-fundacion-repo`.
- Se portan los 4 sets de tokens de `design/mockups/tokens.css` (dark/light × default/totvs) a CSS custom properties reales bajo `html[data-theme][data-brand]`, más los tokens globales (tipografía, espaciado, radios, sombras, motion, z-index, breakpoints) de `design/DESIGN-SYSTEM.md` §3.
- Se implementan los componentes base del inventario de `design/DESIGN-SYSTEM.md` §8 necesarios para el shell y para que changes posteriores construyan vistas sin reinventar anatomía: botón, input/textarea/select, tabla densa, panel/card, tag/badge-rol, toast, modal, dropdown, tooltip, skeleton, empty-state — todos consumiendo solo tokens semánticos (cero hex hardcodeado).
- Se construye el shell de aplicación (`design/VISTAS/01-acceso-shell.md` Vista 3, `design/mockups/03-shell.html`): banner IA permanente no ocultable, sidebar con secciones filtradas por matriz de capacidades (la matriz en sí es config y llega en `d20-gobernanza-plataforma`; aquí el shell consume una matriz de ejemplo estática), topbar con identidad (avatar + badge de rol) y selector de tema personal, estado global `GATEWAY_OFFLINE`.
- Se externaliza el 100% de los textos de este change en catálogos i18n (ES con voseo), con layouts que reservan +25% de ancho para PT-BR (`design/DESIGN-SYSTEM.md` §12), sin activar PT-BR (Etapa P).
- Se construye una página styleguide interna (`/styleguide`, análoga a `design/mockups/00-styleguide.html`) que renderiza los 4 sets de tokens y cada componente base, usada como verificación visual y de contraste AA.

## Capabilities

### New Capabilities

- `design-system`: tokens (color, tipografía, espaciado, radios, motion, z-index, breakpoints), los 4 sets tema×brand, componentes base del inventario DS, contraste WCAG 2.1 AA.
- `app-shell`: shell de aplicación por capacidades de rol, banner IA permanente, estados globales accionables, selector de tema personal, identidad visible en header.
- `i18n-foundation`: externalización de textos, voseo, previsión de espacio para PT-BR.

### Modified Capabilities

*(ninguna — no existen specs previas de frontend)*

## No-objetivos

- Ninguna UI de login/primer acceso (Vistas 1–2 de `design/VISTAS/01-acceso-shell.md`; llega en `d11-identidad-acceso`).
- Ningún chat funcional ni streaming (`d13-chat-conversacion`).
- Ninguna vista funcional de sección (catálogo, workflows, aprobaciones, mi espacio, administración, gobernanza, builders): cada una es su propio slice de la Etapa D.
- Ninguna activación de PT-BR (Etapa P): aquí solo se reserva espacio y se externalizan textos en ES.
- No se define ni implementa la matriz de capacidades por rol como configuración editable (Admin) — eso es `d20-gobernanza-plataforma`; este change consume una matriz de ejemplo hardcodeada para poder mostrar el shell filtrando secciones.
- No se toca `resultarai/` (backend Python) más allá de lo ya existente; este change no agrega endpoints ni contratos de API.
- No se toca `design/` ni `docs/referencias/`.

## Bounded context afectado

Frontend (`frontend/`), bounded context nuevo introducido por ADR-0007. Es un deployable propio servido junto a la plataforma core (`docs/02-arquitectura.md`); en este change no consume ninguna API real de la plataforma (no existe todavía más allá de manifiestos y Policy Gate) — los datos de shell (rol, notificaciones pendientes, estado de gateway) se mockean localmente hasta que `b05`–`b07` y los slices de Etapa D expongan los endpoints correspondientes.

## Impact

- Repo completo (raíz): nuevo directorio `frontend/` (Next.js), actualización de `.github/workflows/ci.yml` (job de frontend) creado en `a01-fundacion-repo`.
- `design/DESIGN-SYSTEM.md` (fuente de tokens y componentes), `design/mockups/tokens.css` (fuente de verdad de valores), `design/VISTAS/01-acceso-shell.md` Vista 3 (fuente del shell), `design/FUNCIONALIDADES.md` §2 y §14 (alcance funcional y transversales).
- Ningún ADR nuevo: implementa la decisión ya tomada en ADR-0007 (`a01-fundacion-repo`).
