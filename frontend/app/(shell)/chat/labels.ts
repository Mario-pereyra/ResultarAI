import type { getTranslations } from "next-intl/server";
import type { ChatContentLabels } from "./chat-content";

type Translator = Awaited<ReturnType<typeof getTranslations>>;

/**
 * Agente con el que `chat/page.tsx` crea la sesión nueva al primer envío.
 * El selector de agente (`agent.starter_prompts`, catálogo completo) es
 * `d15` -- ver `openspec/BACKLOG-DESCUBRIMIENTOS.md`. Todavía no existe un
 * endpoint de catálogo que exponga `display_name` al frontend (solo
 * `manifests/agents/default_chat.yaml`, que no se lee desde acá), así que
 * el nombre mostrado en el composer ("Escribile a {agent}…", vista 05)
 * queda hardcodeado con el `name` literal del manifiesto hasta que `d15`
 * lo resuelva dinámicamente.
 */
const DEFAULT_CHAT_AGENT_ID = "default_chat";
const DEFAULT_CHAT_AGENT_DISPLAY_NAME = "Chat por Defecto";

/** Arma `ChatContentLabels` desde el namespace `Chat` de `messages/es.json`,
 * compartido por `chat/page.tsx` y `chat/[sessionId]/page.tsx`. */
export function buildChatLabels(t: Translator): ChatContentLabels {
  return {
    agentId: DEFAULT_CHAT_AGENT_ID,
    emptyGreeting: t("empty.greeting"),
    stoppedCaption: t("message.stopped"),
    streamingDoneAnnouncement: t("streaming.doneAnnouncement"),
    cursorAriaLabel: t("streaming.cursorAriaLabel"),
    composer: {
      placeholder: t("composer.placeholder", { agent: DEFAULT_CHAT_AGENT_DISPLAY_NAME }),
      send: t("composer.send"),
      sending: t("composer.sending"),
      hint: t("composer.hint"),
      textareaLabel: t("composer.textareaLabel"),
    },
    loading: t("session.loading"),
    loadError: t("session.loadError"),
    sendError: t("session.sendError"),
  };
}
