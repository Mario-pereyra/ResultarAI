import userEvent from "@testing-library/user-event";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SessionProvider, type SessionContextValue } from "@/lib/session-context";
import { ChatContent, type ChatContentLabels } from "./chat-content";

/**
 * Test de componente de la tarea 3.5 (sugerencias de inicio): en una sesión
 * nueva sin mensajes, click en una sugerencia deja el texto en el composer
 * con foco, sin enviar ningún turno ni crear la sesión (`ensureSession` NUNCA
 * se invoca desde acá -- eso queda para cuando el usuario confirme el envío).
 *
 * Tareas 4.2/4.3/4.4 (capa de telemetría Técnico/Admin, vista 06) agregan
 * las describe blocks de más abajo -- todas necesitan `<SessionProvider>`
 * porque `ChatContent` ahora lee `useSession().user.role` para decidir la
 * visibilidad del taxímetro (tarea 4.2).
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
  taximeter: {
    label: "Sesión",
    srLabelPrefix: "Costo de sesión:",
    degradedTooltip: "costo estimado, telemetría diferida",
  },
  telemetry: {
    cacheHit: "HIT",
    cacheMiss: "MISS",
    cacheWrite: "WRITE",
    cacheHitAriaLabelPrefix: "cache hit,",
    cacheHitAriaLabelSuffix: "tokens cacheados",
    cacheMissAriaLabelPrefix: "cache miss,",
    cacheMissAriaLabelSuffix: "tokens sin cache",
    cacheWriteAriaLabelPrefix: "prefijo escrito al cache,",
    cacheWriteAriaLabelSuffix: "tokens",
    cacheHitTooltip: "prefijo servido desde cache: ahorro ~90% en esos tokens",
    cacheMissTooltip: "tokens procesados sin cache (primera vez)",
    cacheWriteTooltip: "prefijo escrito al cache para los próximos turnos",
    viewTrace: "ver traza",
    viewTraceAriaLabel: "Ver traza de este turno en Langfuse",
  },
};

const STARTER_PROMPTS = ["Ayudame a redactar un resumen ejecutivo", "Dame ideas para esta semana"];

afterEach(() => {
  vi.unstubAllGlobals();
});

function sessionFor(role: SessionContextValue["user"]["role"]): SessionContextValue {
  return {
    user: { name: "lucia", role },
    gateway: { status: "ok" },
    pendingApprovals: 0,
    unreadNotifications: 0,
    capabilities: [],
  };
}

function renderChatContent(
  role: SessionContextValue["user"]["role"],
  initialSessionId: string | null,
) {
  return render(
    <SessionProvider value={sessionFor(role)}>
      <ChatContent initialSessionId={initialSessionId} labels={LABELS} />
    </SessionProvider>,
  );
}

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
    renderChatContent("funcional", null);

    expect(await screen.findByRole("button", { name: STARTER_PROMPTS[0] })).toBeTruthy();
    expect(screen.getByRole("button", { name: STARTER_PROMPTS[1] })).toBeTruthy();
  });

  it("click en una sugerencia precarga el composer con foco, sin enviar turno ni crear sesión", async () => {
    const user = userEvent.setup();
    const fetchMock = stubAgentFetch();
    renderChatContent("funcional", null);

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

/**
 * `turn_metadata` tal como lo arma `layer_turn_metadata` (`telemetry.py`,
 * tarea 4.1 del backend): `is_alternate_model`/`compacted`/`escalation`
 * SIEMPRE presentes; `telemetry` solo si se pasa (Técnico/Admin) -- para
 * Funcional la clave queda ausente, nunca `null`.
 */
function assistantTurnMetadata(telemetry?: Record<string, unknown>): Record<string, unknown> {
  return {
    is_alternate_model: false,
    compacted: false,
    escalation: null,
    ...(telemetry ? { telemetry } : {}),
  };
}

function sessionDetailFor(
  assistantTelemetry: [Record<string, unknown> | undefined, Record<string, unknown> | undefined],
): unknown {
  return {
    id: "session-1",
    agent_id: "default_chat",
    title: "Conversación",
    model_profile: "deepseek-v4-flash",
    forked_from_id: null,
    escalated_session_ids: [],
    active_leaf_id: "a2",
    in_progress_turn: null,
    messages: [
      {
        id: "u1",
        parent_id: null,
        role: "user",
        content: "Pregunta 1",
        status: "complete",
        created_at: "2026-07-10T14:00:00Z",
        turn_metadata: null,
      },
      {
        id: "a1",
        parent_id: "u1",
        role: "assistant",
        content: "Respuesta 1",
        status: "complete",
        created_at: "2026-07-10T14:00:03Z",
        turn_metadata: assistantTurnMetadata(assistantTelemetry[0]),
      },
      {
        id: "u2",
        parent_id: "a1",
        role: "user",
        content: "Pregunta 2",
        status: "complete",
        created_at: "2026-07-10T14:01:00Z",
        turn_metadata: null,
      },
      {
        id: "a2",
        parent_id: "u2",
        role: "assistant",
        content: "Respuesta 2",
        status: "complete",
        created_at: "2026-07-10T14:01:05Z",
        turn_metadata: assistantTurnMetadata(assistantTelemetry[1]),
      },
    ],
  };
}

const TURN_1_TELEMETRY = {
  cost_usd: 0.01,
  model_profile_id: "deepseek-v4-flash",
  primary_model_profile_id: "deepseek-v4-flash",
  fallback_reason: null,
  latency_ms: 2000,
  cache_hit_tokens: 41200,
  cache_miss_tokens: 1800,
  cache_write_tokens: null,
  trace_id: "trace-1",
};

const TURN_2_TELEMETRY = {
  cost_usd: 0.02,
  model_profile_id: "deepseek-v4-flash",
  primary_model_profile_id: "deepseek-v4-flash",
  fallback_reason: null,
  latency_ms: 3000,
  cache_hit_tokens: 12400,
  cache_miss_tokens: 900,
  cache_write_tokens: null,
  trace_id: "trace-2",
};

/** Simula la telemetría tal como la arma el backend para Técnico: mismo
 * turno, pero sin `trace_id` (`layer_turn_metadata` nunca lo agrega salvo
 * rol admin, ver `resultarai/app/use_cases/chat/telemetry.py`). */
function withoutTraceId(telemetry: Record<string, unknown>): Record<string, unknown> {
  const copy = { ...telemetry };
  delete copy.trace_id;
  return copy;
}

function stubSessionFetch(sessionDetail: unknown) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    if (url === "/api/agents/default_chat") {
      return new Response(
        JSON.stringify({
          id: "default_chat",
          name: "Chat por Defecto",
          starter_prompts: [],
          escalation_enabled: true,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }
    if (url === "/api/sessions/session-1" && (!init?.method || init.method === "GET")) {
      return new Response(JSON.stringify(sessionDetail), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    throw new Error(`fetch inesperado en este test: ${url}`);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("ChatContent — taxímetro: suma acumulada de dos turnos (tarea 4.2)", () => {
  it("Admin: el taxímetro suma cost_usd de los dos turnos, con costo y chips por fila", async () => {
    stubSessionFetch(sessionDetailFor([TURN_1_TELEMETRY, TURN_2_TELEMETRY]));
    renderChatContent("admin", "session-1");

    await screen.findByText("Respuesta 2");

    // Taxímetro: 0,01 + 0,02 = 0,03 acumulado (requirement de la tarea).
    expect(screen.getByRole("status", { name: /Costo de sesión/ })).toBeTruthy();
    expect(screen.getByText("USD 0,0300")).toBeTruthy();
    expect(screen.getByText("56,3k tok")).toBeTruthy();

    // Fila de telemetría por turno: costo y chips individuales de CADA turno.
    expect(screen.getByText("USD 0,0100")).toBeTruthy();
    expect(screen.getByText("USD 0,0200")).toBeTruthy();
    expect(screen.getByText("HIT · 41,2k")).toBeTruthy();
    expect(screen.getByText("MISS · 1,8k")).toBeTruthy();
    expect(screen.getByText("HIT · 12,4k")).toBeTruthy();
    expect(screen.getByText("MISS · 900")).toBeTruthy();
    expect(screen.getAllByText("deepseek-v4-flash")).toHaveLength(2);
  });

  it("Funcional: ni taxímetro ni filas de telemetría (ausencia total)", async () => {
    stubSessionFetch(sessionDetailFor([undefined, undefined]));
    renderChatContent("funcional", "session-1");

    await screen.findByText("Respuesta 2");

    expect(screen.queryByRole("status", { name: /Costo de sesión/ })).toBeNull();
    expect(screen.queryByText("USD 0,0300")).toBeNull();
    expect(screen.queryByText("USD 0,0100")).toBeNull();
    expect(screen.queryByText(/^HIT/)).toBeNull();
    expect(screen.queryByText("deepseek-v4-flash")).toBeNull();
  });
});

describe('ChatContent — enlace "ver traza" solo para Admin (tarea 4.3)', () => {
  it('Admin: el mismo turno con trace_id muestra el enlace "ver traza"', async () => {
    stubSessionFetch(sessionDetailFor([TURN_1_TELEMETRY, TURN_2_TELEMETRY]));
    renderChatContent("admin", "session-1");

    await screen.findByText("Respuesta 2");
    expect(screen.getAllByText("ver traza")).toHaveLength(2);
  });

  it('Técnico: el mismo turno, sin trace_id en su telemetría -- el enlace "ver traza" está ausente', async () => {
    // Igual que arriba, pero sin `trace_id`: así llega el `telemetry` real de
    // Técnico desde el backend (`layer_turn_metadata` nunca lo agrega salvo
    // rol admin, ver `resultarai/app/use_cases/chat/telemetry.py`).
    stubSessionFetch(
      sessionDetailFor([withoutTraceId(TURN_1_TELEMETRY), withoutTraceId(TURN_2_TELEMETRY)]),
    );
    renderChatContent("tecnico", "session-1");

    await screen.findByText("Respuesta 2");
    // El resto de la telemetría SÍ se ve -- solo falta "ver traza".
    expect(screen.getByText("USD 0,0100")).toBeTruthy();
    expect(screen.queryByText("ver traza")).toBeNull();
    expect(screen.queryByRole("link", { name: LABELS.telemetry.viewTraceAriaLabel })).toBeNull();
  });
});

describe("ChatContent — estado degradado del taxímetro, solo Admin (tarea 4.4)", () => {
  it("Admin: con la traza no disponible, el taxímetro antepone «~» y anuncia el tooltip de costo estimado", async () => {
    stubSessionFetch(sessionDetailFor([withoutTraceId(TURN_1_TELEMETRY), TURN_2_TELEMETRY]));
    renderChatContent("admin", "session-1");

    await screen.findByText("Respuesta 2");

    expect(screen.getByText("~USD 0,0300")).toBeTruthy();
    const status = screen.getByRole("status", { name: /Costo de sesión/ });
    expect(status.getAttribute("data-tip")).toBe(LABELS.taximeter.degradedTooltip);
    expect(status.getAttribute("aria-label")).toContain(LABELS.taximeter.degradedTooltip);
  });

  it("Técnico: la misma traza no disponible NO activa el «~» ni el tooltip de traza en el taxímetro (solo Admin)", async () => {
    stubSessionFetch(
      sessionDetailFor([withoutTraceId(TURN_1_TELEMETRY), withoutTraceId(TURN_2_TELEMETRY)]),
    );
    renderChatContent("tecnico", "session-1");

    await screen.findByText("Respuesta 2");

    // El taxímetro sigue visible (Técnico SÍ ve telemetría), pero sin el
    // degradado -- ese estado es exclusivo de Admin (tasks.md, tarea 4.4).
    expect(screen.getByText("USD 0,0300")).toBeTruthy();
    expect(screen.queryByText("~USD 0,0300")).toBeNull();
    const status = screen.getByRole("status", { name: /Costo de sesión/ });
    expect(status.getAttribute("data-tip")).toBeNull();
  });
});
