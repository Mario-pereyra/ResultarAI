import { getTranslations } from "next-intl/server";
import { ChatContent } from "../chat-content";
import { buildChatLabels } from "../labels";

/**
 * Sesión existente (vista 05): carga `GET /api/sessions/{id}` desde el
 * client component (`ChatContent`, mismo patrón que
 * `app/(shell)/administracion/admin-content.tsx` -- fetch en el cliente,
 * no en el servidor, para reutilizar un único componente con `chat/page.tsx`
 * sin duplicar el árbol de UI).
 */
export default async function ChatSessionPage({
  params,
}: {
  params: Promise<{ sessionId: string }>;
}) {
  const { sessionId } = await params;
  const t = await getTranslations("Chat");
  return <ChatContent initialSessionId={sessionId} labels={buildChatLabels(t)} />;
}
