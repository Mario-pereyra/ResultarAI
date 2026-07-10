import { getTranslations } from "next-intl/server";
import { HistoryContent } from "./history-content";
import { buildHistoryLabels } from "./history-labels";

/**
 * Historial de sesiones (tareas 7.1-7.4 de d13-chat-conversacion,
 * `design/VISTAS/02-chat.md` vista 12): punto de ENTRADA de la sección
 * "chat" del shell (`components/shell/sidebar.tsx`, `SECTION_HREF.chat:
 * "/chat"` -- sin cambios ahí, ya apuntaba acá). Antes `/chat` era la
 * conversación nueva; esa página se movió a `chat/nueva/page.tsx` (botón
 * "Nueva consulta" de `HistoryContent`) -- ver el docstring de
 * `HistoryContent` para el resto de la decisión de routing.
 *
 * Server Component mínimo (mismo patrón que el resto de `app/(shell)/*`):
 * solo resuelve traducciones y delega el fetch/estado al client component.
 */
export default async function ChatHistoryPage() {
  const t = await getTranslations("History");
  return <HistoryContent labels={buildHistoryLabels(t)} />;
}
