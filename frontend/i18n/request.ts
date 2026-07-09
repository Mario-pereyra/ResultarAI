import { getRequestConfig } from "next-intl/server";

/**
 * Instancia de un solo locale (es), sin routing por locale ni selector de
 * idioma (Decision 3, openspec/changes/d10-design-system-shell/design.md).
 * PT-BR llega en Etapa P; hasta entonces el locale es estático.
 */
const locale = "es";

export default getRequestConfig(async () => {
  return {
    locale,
    messages: (await import(`../messages/${locale}.json`)).default,
  };
});
