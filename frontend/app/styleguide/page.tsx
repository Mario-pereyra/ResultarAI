import { StyleguideContent } from "./styleguide-content";

/**
 * /styleguide — página interna de verificación visual (tarea 7.3,
 * d10-design-system-shell), equivalente a design/mockups/00-styleguide.html.
 *
 * Decisión: vive FUERA del grupo `(shell)` a propósito (`app/styleguide/`,
 * no `app/(shell)/styleguide/`). Dos motivos:
 * 1. El Requirement pide una ruta "no listada en el sidebar" — el sidebar
 *    ya solo renderiza las `Section` de `lib/capabilities.ts`, así que
 *    técnicamente ninguna ruta nueva "aparecería" ahí sola. Pero envolver
 *    esta página en `<ShellFrame>` agregaría un topbar/sidebar de
 *    producción DUPLICANDO exactamente lo que la página ya demuestra
 *    (buscador, switcher de tema, campana) — ruido visual que contradice
 *    el propósito de una página de referencia de componentes aislados
 *    (mismo espíritu que el mockup fuente, que es un documento standalone).
 * 2. El switcher de tema/marca de esta página manipula `data-theme`/
 *    `data-brand` LOCALMENTE en el cliente (sin escribir la cookie — ver
 *    styleguide-content.tsx) para poder mostrar las 4 combinaciones sin
 *    recargar; si viviera bajo el shell, el usuario esperaría que ese
 *    switcher fuera EL switcher real de tema del topbar (que sí persiste
 *    por cookie) — dos mecanismos de tema distintos en la misma vista
 *    confundirían cuál es cuál.
 *
 * `data-theme`/`data-brand` siguen viviendo en `<html>` (app/layout.tsx,
 * fuera del grupo (shell) también), así que el switcher cliente funciona
 * igual estando esta página dentro o fuera de (shell) — la decisión de
 * arriba es sobre chrome de producto, no sobre dónde vive el atributo.
 *
 * Es un Server Component trivial: toda la interactividad (switcher, toasts,
 * modal) vive en `StyleguideContent` ("use client"), que resuelve sus
 * textos con `useTranslations("Styleguide")` (patrón documentado en
 * frontend/README.md § i18n para Client Components) en vez de recibirlos
 * por props — a diferencia de `components/shell/*`, esta página no
 * necesita aislarse de next-intl en sus tests: los envuelve directamente
 * con `NextIntlClientProvider` (ver styleguide-content.test.tsx).
 */
export default function StyleguidePage() {
  return <StyleguideContent />;
}
