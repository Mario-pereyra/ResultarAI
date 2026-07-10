import { getTranslations } from "next-intl/server";
import { ChatContent } from "../chat-content";
import { buildChatLabels } from "../labels";

/**
 * Conversación nueva (vista 05): Server Component mínimo, sin sesión
 * todavía -- `ChatContent` crea la sesión (`agent_id: "default_chat"`) al
 * enviar el primer mensaje (patrón de `app/(shell)/administracion/page.tsx`:
 * este componente solo resuelve traducciones y delega el resto al client
 * component).
 *
 * Movido de `chat/page.tsx` (tarea 7.1, historial vista 12): `/chat` ahora
 * es el LISTADO (`../page.tsx` + `../history-content.tsx`) -- este es el
 * destino del botón "Nueva consulta" de ahí, y sigue siendo el mismo
 * componente que `../[sessionId]/page.tsx` reutiliza para una sesión ya
 * existente (ver el docstring de `ChatContent` para el porqué de un único
 * componente para ambas rutas).
 */
export default async function ChatNewPage() {
  const t = await getTranslations("Chat");
  return <ChatContent initialSessionId={null} labels={buildChatLabels(t)} />;
}
