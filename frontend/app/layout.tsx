import type { Metadata } from "next";
import { cookies } from "next/headers";
import { Chakra_Petch, Saira, JetBrains_Mono } from "next/font/google";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getTranslations } from "next-intl/server";
import { THEME_COOKIE, resolveTheme } from "../lib/theme";
import "../styles/tokens.css";
import "../styles/components/index.css";
import "./globals.css";

/*
 * Estrategia de fuentes (tarea 3.3, d10-design-system-shell):
 * `next/font/google` autohospeda Chakra Petch (display), Saira (body) y
 * JetBrains Mono (mono) en build time — sin requests a fonts.googleapis.com
 * en runtime, sin layout shift por fuentes de fallback sin métricas — y
 * expone cada familia como CSS custom property vía `variable`. Esas
 * variables se aplican como className en <html> (abajo) y son el PRIMER
 * valor de --font-display/--font-body/--font-mono en styles/tokens.css, con
 * el nombre literal de Google Fonts ya portado como fallback del propio
 * var(): ver el comentario en tokens.css junto a esas tres declaraciones.
 * Pesos: los mismos que traía el `@import` del mockup original.
 */
const chakraPetch = Chakra_Petch({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  variable: "--font-chakra-petch",
  display: "swap",
});

const saira = Saira({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-saira",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "700"],
  variable: "--font-jetbrains-mono",
  display: "swap",
});

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("App");

  return {
    title: t("title"),
    description: t("description"),
  };
}

/*
 * Contrato de tema/brand (tarea 3.4, d10-design-system-shell — README.md
 * documenta este mismo contrato; reutilizado tal cual por la tarea 5.4):
 * - Cookie `theme`, valores "dark" | "light", persiste la preferencia
 *   personal de tema. Sin cookie -> "dark" (default de instancia: escenario
 *   "dark·default es el tema por defecto de la instancia",
 *   specs/design-system/spec.md). Constante/función en `lib/theme.ts` —
 *   `app/api/theme/route.ts` (switcher del shell, tarea 5.4) importa las
 *   mismas, nunca las reimplementa.
 * - `data-brand` queda fijo en "default" en este change: todavía no hay
 *   cookie de brand ni selector.
 * - Todo se resuelve en el servidor con `cookies()` de `next/headers`: cero
 *   scripts inline de theming y cero useEffect para el estado inicial — el
 *   HTML ya llega con data-theme/data-brand correctos, sin flash de tema
 *   incorrecto (FOUC).
 */

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const locale = await getLocale();
  const cookieStore = await cookies();
  const theme = resolveTheme(cookieStore.get(THEME_COOKIE)?.value);

  return (
    <html
      lang={locale}
      data-theme={theme}
      data-brand="default"
      className={`${chakraPetch.variable} ${saira.variable} ${jetbrainsMono.variable}`}
    >
      <body>
        <NextIntlClientProvider>{children}</NextIntlClientProvider>
      </body>
    </html>
  );
}
