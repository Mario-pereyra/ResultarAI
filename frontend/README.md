# ResultarAI — Frontend

Scaffold de Next.js (App Router) + TypeScript del frontend de ResultarAI (ADR-0007, `docs/adr/0007-frontend-nextjs-assistant-ui.md`), construido en el change `openspec/changes/d10-design-system-shell`. Deployable propio, servido junto a la plataforma core (`docs/02-arquitectura.md`); por ahora no consume ninguna API real de la plataforma.

## Comandos

```bash
npm install       # instalar dependencias (lockfile: package-lock.json)
npm run dev        # servidor de desarrollo (Turbopack)
npm run lint        # ESLint (next/core-web-vitals + typescript-eslint), flat config
npm run typecheck   # tsc --noEmit (strict)
npm run test        # Vitest (modo run, no watch)
npm run build       # build de producción
npm run start        # sirve el build de producción
```

## Estructura de carpetas

| Ruta | Contenido |
|---|---|
| `app/` | App Router: layout raíz (provider de i18n), página raíz, componentes co-ubicados con sus tests (`*.test.tsx`) |
| `i18n/request.ts` | Configuración de next-intl: locale único `es`, sin routing por locale |
| `messages/es.json` | Catálogo de mensajes ES, con una clave de nivel superior por sección/página (namespace) |
| `public/` | Assets estáticos servidos en `/` |
| `scripts/` | Scripts de build/verificación del frontend (ej. `scripts/check-contrast.ts`, sección 7 de `d10-design-system-shell`) |
| `vitest.config.ts`, `vitest.setup.ts` | Configuración de Vitest + Testing Library (entorno `jsdom`) |

## Patrón i18n (next-intl)

- Un solo locale de instancia (`es`, con voseo). No hay selector de idioma ni routing por locale (Decision 3 de `openspec/changes/d10-design-system-shell/design.md`); el selector y la activación de PT-BR llegan en la Etapa P.
- Catálogo: `messages/es.json`, con un namespace de nivel superior por sección/página (patrón que `d11`–`d21` deben seguir), por ejemplo:
  ```json
  {
    "App": { "title": "...", "description": "..." },
    "HomePage": { "title": "...", "greeting": "..." }
  }
  ```
- En Server Components (async), usar `getTranslations("Namespace")` de `next-intl/server`. En Client Components, usar `useTranslations("Namespace")` de `next-intl`. Cada vista nueva agrega su propio namespace; no reutilizar ni anidar namespaces de otras vistas.
- Reglas obligatorias para todo texto de UI (`specs/i18n-foundation/spec.md`): nunca hardcodeado en JSX, siempre en voseo, sin concatenar fragmentos de oración (usar placeholders nombrados: `{usuario} aprobó la escritura`), plurales con sintaxis ICU, y fechas/números vía `Intl.DateTimeFormat`/`Intl.NumberFormat` con locale `es-BO`.

## assistant-ui (ADR-0007)

`@assistant-ui/react` está instalado como dependencia **sin uso funcional todavía**. Es la librería de componentes de chat (streaming, threads, tool calls colapsables) sobre la que se construye el chat gobernado (Default Chat) de ResultarAI. Se activa recién en `d13-chat-conversacion`; hasta entonces solo está en `package.json` para fijar la versión y validar que resuelve sin conflictos:

```bash
npm ls @assistant-ui/react
```

## Testing

Vitest + `@testing-library/react` + `@testing-library/user-event`, entorno `jsdom`. Los tests se co-ubican junto al código (`*.test.tsx`).

Los Server Components `async` (como `app/page.tsx`, que llama `getTranslations`) no se testean directamente con Testing Library/Vitest: dependen del runtime de Next.js (AsyncLocalStorage del plugin de next-intl) para resolver el catálogo, algo que no está disponible fuera de un render real de Next.js. Por eso la UI se extrae a un componente presentacional sin `async` ni llamadas de servidor (ej. `app/home-content.tsx`), que sí se testea directamente (`app/home-content.test.tsx`). Este patrón se repite para las vistas que agreguen `d11`–`d21`.

## Tokens, fuentes y tema (tareas 3.3/3.4 de `d10-design-system-shell`)

- `styles/tokens.css` (portado 1:1 de `design/mockups/tokens.css` §2/§3, más una sección de utilidades al final) se importa globalmente en `app/layout.tsx`, antes de `app/globals.css`. `globals.css` es solo reset + base de documento: consume las custom properties de tokens (`var(--bg)`, `var(--font-body)`, etc.) pero nunca redefine sus valores.
- **Fuentes**: Chakra Petch, Saira y JetBrains Mono se cargan con `next/font/google` en `app/layout.tsx` (self-hosted, sin request a Google Fonts en runtime), cada una expuesta como CSS variable (`--font-chakra-petch`, `--font-saira`, `--font-jetbrains-mono`) aplicada como `className` en `<html>`. `styles/tokens.css` las consume como primer valor de `--font-display`/`--font-body`/`--font-mono` (con el nombre literal de Google Fonts como fallback del propio `var()`), así que ningún componente necesita saber que la fuente viene de `next/font`.
- **Contrato de tema/brand (para `5.4-selector-tema-brand` y cualquier código que lea/escriba el tema)**:
  - Cookie `theme`, valores `"dark"` | `"light"`. Sin cookie → `"dark"` (default de instancia).
  - `data-brand` está fijo en `"default"` en este change (no hay cookie de brand ni selector todavía); `5.4` debe sumar una cookie `brand` análoga con el mismo mecanismo si agrega selección de marca.
  - Todo se resuelve en `app/layout.tsx` (Server Component raíz) con `cookies()` de `next/headers`, estampando `<html data-theme={...} data-brand="default">` directamente en el HTML servido. **Cero** scripts inline de theming y **cero** `useEffect` para el estado inicial: el SSR ya lo resuelve, así que no hay flash de tema incorrecto (FOUC). Cualquier switcher de tema debe escribir la cookie (p. ej. vía Server Action o route handler) y dejar que una recarga/navegación vuelva a pasar por este mismo Server Component — no debe mutar `data-theme` desde el cliente con JS.

## Decisiones no obvias de este scaffold

- **Next.js 16.2.10 + React 19.2.4**: versiones estables más recientes disponibles en npm al crear el scaffold (2026-07-09).
- **TypeScript se mantiene en la línea `^5` (resuelto 5.9.3)** que fija `create-next-app` por defecto, no en la última mayor publicada en npm (`7.x`): `eslint-config-next`/`typescript-eslint` (v8.63.0) todavía targetean la línea 5.x de TypeScript; forzar 7.x arriesgaba romper el toolchain de lint sin beneficio para este change, que solo pedía Next.js/React en su versión más reciente.
- **`next lint` fue removido en Next.js 16** (`next build` ya no corre el linter automáticamente); el script `lint` invoca ESLint directo (`eslint.config.mjs`, flat config) generado por `create-next-app` con `eslint-config-next/core-web-vitals` + `eslint-config-next/typescript`.
- **Sin Tailwind** (`--no-tailwind`): el CSS real llega portado desde `design/mockups/tokens.css` en la sección "Tokens" de `d10-design-system-shell`; `app/globals.css` hoy es solo un reset mínimo.
- `SessionContext` y `capabilities.ts` (shell de aplicación) todavía no existen — llegan en la sección 5 de `d10-design-system-shell`; este README se actualizará entonces con el contrato temporal que deben preservar `d11-identidad-acceso` y `d20-gobernanza-plataforma` (ver `design.md`, decisiones 6 y 7).
