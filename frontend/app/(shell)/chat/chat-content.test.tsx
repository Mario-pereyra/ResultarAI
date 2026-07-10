import userEvent from "@testing-library/user-event";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ChatContent, type ChatContentLabels } from "./chat-content";

/**
 * Test de componente de la tarea 3.5 (sugerencias de inicio): en una sesión
 * nueva sin mensajes, click en una sugerencia deja el texto en el composer
 * con foco, sin enviar ningún turno ni crear la sesión (`ensureSession` NUNCA
 * se invoca desde acá -- eso queda para cuando el usuario confirme el envío).
 */

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: vi.fn(),
    push: vi.fn(),
  }),
}));

const LABELS: ChatContentLabels = {
  agentId: "default_chat",
  emptyGreeting: "¿En qué te puedo ayudar hoy?",
  stoppedCaption: "Detenida por vos",
  streamingDoneAnnouncement: "Respuesta completa",
  cursorAriaLabel: "El agente está escribiendo",
  activity: { consulting: "Consultando…" },
  newMessages: "↓ Nuevos mensajes",
  feedback: {
    like: "Me gusta",
    dislike: "No me gusta",
    prompt: "¿Querés agregar un comentario? (opcional)",
    commentLabel: "Comentario",
    send: "Enviar",
    skip: "Omitir",
    error: "No pudimos registrar tu voto. Probá de nuevo.",
  },
  composer: {
    placeholder: "Escribile a Chat por Defecto…",
    textareaLabel: "Mensaje",
    send: "Enviar",
    stop: "Detener",
    hint: "Enter envía · Shift+Enter salto de línea",
  },
  loading: "Cargando conversación…",
  loadError: "No pudimos cargar esta conversación.",
  sendError: "Se perdió la conexión con el turno y no se pudo reconectar.",
};

const STARTER_PROMPTS = ["Ayudame a redactar un resumen ejecutivo", "Dame ideas para esta semana"];

afterEach(() => {
  vi.unstubAllGlobals();
});

function stubAgentFetch() {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = typeof input === "string" ? input : input.toString();
    if (url === "/api/agents/default_chat") {
      return new Response(
        JSON.stringify({
          id: "default_chat",
          name: "Chat por Defecto",
          starter_prompts: STARTER_PROMPTS,
          escalation_enabled: true,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }
    throw new Error(`fetch inesperado en este test: ${url}`);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("ChatContent — sugerencias de inicio (tarea 3.5)", () => {
  it("muestra las sugerencias en una sesión nueva sin mensajes", async () => {
    stubAgentFetch();
    render(<ChatContent initialSessionId={null} labels={LABELS} />);

    expect(await screen.findByRole("button", { name: STARTER_PROMPTS[0] })).toBeTruthy();
    expect(screen.getByRole("button", { name: STARTER_PROMPTS[1] })).toBeTruthy();
  });

  it("click en una sugerencia precarga el composer con foco, sin enviar turno ni crear sesión", async () => {
    const user = userEvent.setup();
    const fetchMock = stubAgentFetch();
    render(<ChatContent initialSessionId={null} labels={LABELS} />);

    const suggestion = await screen.findByRole("button", { name: STARTER_PROMPTS[0] });
    await user.click(suggestion);

    const textarea = screen.getByLabelText("Mensaje") as HTMLTextAreaElement;
    expect(textarea.value).toBe(STARTER_PROMPTS[0]);
    expect(document.activeElement).toBe(textarea);

    // Único fetch disparado: la lectura del agente. Ningún `POST /api/sessions`
    // ni envío de turno se disparó por el solo click en la sugerencia.
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith("/api/agents/default_chat");

    // Las sugerencias siguen sin mensajes en la conversación (nada se envió).
    expect(screen.getByText(LABELS.emptyGreeting)).toBeTruthy();
  });
});
