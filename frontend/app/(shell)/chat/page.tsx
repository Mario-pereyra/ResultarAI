import { getTranslations } from "next-intl/server";
import { ChatContent } from "./chat-content";
import { buildChatLabels } from "./labels";

/**
 * Conversación nueva (vista 05): Server Component mínimo, sin sesión
 * todavía -- `ChatContent` crea la sesión (`agent_id: "default_chat"`) al
 * enviar el primer mensaje (patrón de `app/(shell)/administracion/page.tsx`:
 * este componente solo resuelve traducciones y delega el resto al client
 * component).
 */
export default async function ChatPage() {
  const t = await getTranslations("Chat");
  return <ChatContent initialSessionId={null} labels={buildChatLabels(t)} />;
}
