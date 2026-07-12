import userEvent from "@testing-library/user-event";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createControlledReader, mockSseResponse, sseFrame } from "@/lib/chat/test-support/sse-mock";
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

// `push` estable entre renders (un `vi.fn()` inline daría una instancia nueva
// por render, imposible de aseverar): tarea 5.3 necesita comprobar la
// navegación a la sesión escalada.
const { pushMock } = vi.hoisted(() => ({ pushMock: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: vi.fn(),
    push: pushMock,
  }),
}));

const LABELS: ChatContentLabels = {
  agentId: "default_chat",
  defaultAgentName: "Chat por Defecto",
  header: {
    sessionMenuLabel: "Menú de la sesión",
  },
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
    attach: "Adjuntar archivo",
    attachmentsListLabel: "Archivos adjuntos",
    removeAttachment: "Quitar adjunto {file}",
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
  alternateModel: {
    label: "modelo alterno",
    funcionalExplanation:
      "Esta respuesta la generó un modelo alternativo porque el habitual no estaba disponible. La calidad puede variar.",
    profilePrefix: "Perfil:",
    reasonPrefix: "Motivo:",
  },
  toolCall: {
    parametersLabel: "Parámetros",
    latencyLabel: "Latencia:",
  },
  versionSelector: {
    versionAriaLabel: "versión {n} de {m}",
    previousVersion: "Versión anterior",
    nextVersion: "Versión siguiente",
  },
  escalation: {
    title: "Este caso amerita el modelo Pro",
    consequence: "Se abre una conversación nueva con el contexto de esta.",
    targetProfileLabel: "Perfil de destino:",
    confirm: "Continuar con Pro",
    dismiss: "Seguir con Flash",
    doneLink: "Continuaste esta consulta en Pro — abrir conversación",
    dismissedNote: "Decidiste seguir con Flash",
  },
  escalationOriginLink: "Esta conversación continúa una consulta anterior — abrir",
  messageEdit: {
    action: "Editar mensaje (crea una rama nueva)",
    textareaLabel: "Editar mensaje",
    cancel: "Cancelar",
    confirm: "Crear rama",
    reprocessWarningOne: "Crear una rama acá reprocesa {n} mensaje",
    reprocessWarningOther: "Crear una rama acá reprocesa {n} mensajes",
  },
  compactionIndicator: "Resumimos el historial de esta conversación.",
  gatewayOffline: {
    title: "El servicio de IA no está disponible",
    technicalWhy: "El proveedor no responde; reintento automático",
    funcionalWhy: "El asistente no está disponible en este momento",
    supportCodePrefix: "código para soporte:",
    retryNow: "Reintentar ahora",
    retryingIn: "Reintentando en {n} s",
  },
  quota: {
    title: "Alcanzaste tu cuota mensual",
    technicalWhy: "Tu límite de uso mensual se alcanzó.",
    funcionalWhy: "Alcanzaste tu límite de uso de este mes",
    supportCodePrefix: "código para soporte:",
    requestRelease: "Solicitar liberación",
    requestSent: "Solicitud enviada",
    requestSentNote: "Te avisamos cuando un admin la resuelva.",
  },
  quotaComposerDisabledReason: "Alcanzaste tu cuota mensual. Solicitá una liberación para seguir escribiendo.",
  agentDisabledComposerReason:
    "Este agente ya no está disponible. Podés leer la conversación, pero no continuarla.",
  attachments: {
    errors: {
      unsupportedType: "No podemos procesar archivos {extension}. Extraé el archivo que necesitás y subilo directamente.",
      falsifiedType: "El contenido del archivo no coincide con su extensión ({extension}). Por seguridad no se puede adjuntar.",
      withMacros:
        'Los archivos con macros ({extension}) no están permitidos. Guardalo desde Excel como "Libro de Excel (.xlsx)" y volvé a subirlo.',
      tooLarge: "El archivo supera el límite de {limitMb} MB para {fileType}. Si solo necesitás algunas hojas, copialas a un archivo nuevo.",
      pdfProtected: "Este PDF está protegido con contraseña y no se puede leer. Quitale la protección y volvé a subirlo.",
      imageNotSupported:
        "Este agente todavía no puede ver imágenes. Si es una captura de un error, pegá el texto del mensaje directamente en el chat; si es un reporte, exportalo a PDF o Excel.",
      wordLegacy: "El formato .doc (Word 97-2003) no está soportado. Abrilo en Word y guardalo como .docx.",
      tooManyAttachments: "Máximo {limit} archivos por mensaje. Quitá alguno o enviá en dos mensajes.",
      credentialsDetected:
        "Este archivo contiene lo que parece una contraseña o clave de acceso ({detail}). Por política no puede enviarse a la IA. Quitá las credenciales del archivo y volvé a subirlo.",
      piiDetected: "Detectamos posibles datos personales en este archivo ({detail}). Recordá la política: solo datos de prueba hacia la IA.",
      embeddedInstruction:
        "Este documento contiene texto que parece dirigido a la IA ({detail}). El agente lo tratará solo como contenido del documento. Revisalo si no lo esperabas.",
      genericError: "No pudimos procesar este archivo (puede estar dañado). Probá guardarlo de nuevo desde la aplicación original.",
    },
    fileTypes: {
      excel: "Excel",
      csv: "CSV/TSV",
      pdf: "PDF",
      docx: "Word",
      text: "texto o Markdown",
      code: "código",
      log: "logs",
    },
  },
};

const STARTER_PROMPTS = ["Ayudame a redactar un resumen ejecutivo", "Dame ideas para esta semana"];

afterEach(() => {
  vi.unstubAllGlobals();
  pushMock.mockClear();
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

/**
 * Mismo stub que `stubSessionFetch`, pero `GET /api/agents/default_chat`
 * responde 404 (`get_agent_endpoint`: agente no catalogado o no invocable) --
 * la señal de "sesión con agente deshabilitado" de la tarea 7.3.
 */
function stubSessionFetchWithDisabledAgent(sessionDetail: unknown) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    if (url === "/api/agents/default_chat") {
      return new Response(JSON.stringify({ detail: "Agente no encontrado o no disponible." }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      });
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

describe("ChatContent — sesión con agente deshabilitado (tarea 7.3, historial vista 12)", () => {
  it("agente deshabilitado: los mensajes persistidos siguen visibles y el composer queda deshabilitado con motivo", async () => {
    stubSessionFetchWithDisabledAgent(sessionDetailFor([undefined, undefined]));
    renderChatContent("funcional", "session-1");

    // La sesión se puede LEER: el árbol de mensajes ya persistido no depende
    // de si el agente sigue siendo invocable.
    await screen.findByText("Respuesta 2");
    expect(screen.getByText("Pregunta 1")).toBeTruthy();

    // El composer queda deshabilitado con el motivo inline (mismo patrón que
    // QUOTA, tarea 6.2) -- nunca se pierde la posibilidad de leer el resto.
    const textarea = screen.getByLabelText("Mensaje") as HTMLTextAreaElement;
    expect(textarea.disabled).toBe(true);
    expect(screen.getByText(LABELS.agentDisabledComposerReason)).toBeTruthy();
  });

  it("agente disponible (control): el composer sigue activo sin ningún motivo inline", async () => {
    stubSessionFetch(sessionDetailFor([undefined, undefined]));
    renderChatContent("funcional", "session-1");

    await screen.findByText("Respuesta 2");
    const textarea = screen.getByLabelText("Mensaje") as HTMLTextAreaElement;
    expect(textarea.disabled).toBe(false);
    expect(screen.queryByText(LABELS.agentDisabledComposerReason)).toBeNull();
  });
});

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

/**
 * Tarea 5.3 (integración de la tarjeta de escalación en `ChatContent`): el
 * GATE por `escalation_enabled`, la persistencia tras recarga y la navegación
 * a la sesión escalada. La aparición de la tarjeta se ejercita por la vía de
 * RECARGA (el detalle de sesión trae `turn_metadata.escalation` poblado), que
 * pasa por el MISMO gate y el mismo `renderEscalation` que el flujo vivo por
 * SSE -- sin necesidad de simular el stream acá (el flujo vivo lo cubren las
 * pruebas de `EscalationCard` y `use-turn-stream`).
 */
const ESCALATION_META = {
  is_alternate_model: false,
  compacted: false,
  escalation: { reason: "Tu consulta cruza varias localizaciones.", target_profile: "deepseek-v4-pro" },
};

function escalationSessionDetail(escalatedSessionIds: string[]): unknown {
  return {
    id: "session-1",
    agent_id: "default_chat",
    title: "Conversación",
    model_profile: "deepseek-v4-flash",
    forked_from_id: null,
    escalated_session_ids: escalatedSessionIds,
    active_leaf_id: "a1",
    in_progress_turn: null,
    messages: [
      {
        id: "u1",
        parent_id: null,
        role: "user",
        content: "Pregunta compleja",
        status: "complete",
        created_at: "2026-07-10T14:00:00Z",
        turn_metadata: null,
      },
      {
        id: "a1",
        parent_id: "u1",
        role: "assistant",
        content: "Respuesta parcial",
        status: "complete",
        created_at: "2026-07-10T14:00:03Z",
        turn_metadata: ESCALATION_META,
      },
    ],
  };
}

/** Stub que responde el agente (con `escalation_enabled` parametrizable), el
 * detalle de la sesión y el `POST /escalate` (201, sesión de destino nueva). */
function stubEscalationFetch(options: {
  escalationEnabled: boolean;
  detail: unknown;
}) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    if (url === "/api/agents/default_chat") {
      return new Response(
        JSON.stringify({
          id: "default_chat",
          name: "Chat por Defecto",
          starter_prompts: [],
          escalation_enabled: options.escalationEnabled,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }
    if (url === "/api/sessions/session-1" && (!init?.method || init.method === "GET")) {
      return new Response(JSON.stringify(options.detail), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    if (url === "/api/sessions/session-1/escalate" && init?.method === "POST") {
      return new Response(
        JSON.stringify({
          escalated_session_id: "session-2",
          origin_session_id: "session-1",
          model_profile: "deepseek-v4-pro",
          seeded_message_id: "seed-1",
          created: true,
          origin_session_title: "Conversación",
          escalated_session_title: "Conversación (Pro)",
        }),
        { status: 201, headers: { "Content-Type": "application/json" } },
      );
    }
    throw new Error(`fetch inesperado en este test: ${url} (${init?.method ?? "GET"})`);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("ChatContent — tarjeta de escalación: GATE por escalation_enabled (tarea 5.3)", () => {
  it("escalación deshabilitada: la tarjeta NO existe en el DOM aunque el turno traiga el evento", async () => {
    stubEscalationFetch({ escalationEnabled: false, detail: escalationSessionDetail([]) });
    renderChatContent("funcional", "session-1");

    // La conversación carga normalmente...
    await screen.findByText("Respuesta parcial");
    // ...pero la tarjeta nunca se monta: ni CTA, ni razón, ni título.
    expect(screen.queryByRole("button", { name: LABELS.escalation.confirm })).toBeNull();
    expect(screen.queryByRole("button", { name: LABELS.escalation.dismiss })).toBeNull();
    expect(screen.queryByText(LABELS.escalation.title)).toBeNull();
  });

  it("escalación habilitada: la tarjeta se monta tras la respuesta del turno que la disparó", async () => {
    stubEscalationFetch({ escalationEnabled: true, detail: escalationSessionDetail([]) });
    renderChatContent("funcional", "session-1");

    expect(await screen.findByRole("button", { name: LABELS.escalation.confirm })).toBeTruthy();
    expect(screen.getByRole("button", { name: LABELS.escalation.dismiss })).toBeTruthy();
    expect(screen.getByText(ESCALATION_META.escalation.reason)).toBeTruthy();
    expect(screen.getByText("deepseek-v4-pro")).toBeTruthy();
  });
});

describe("ChatContent — tarjeta de escalación: confirmar navega a la sesión nueva (tarea 5.3)", () => {
  it('"Continuar con Pro" hace UNA sola llamada a /escalate y navega a /chat/{id}, con nota-enlace', async () => {
    const user = userEvent.setup();
    const fetchMock = stubEscalationFetch({
      escalationEnabled: true,
      detail: escalationSessionDetail([]),
    });
    renderChatContent("funcional", "session-1");

    const confirm = await screen.findByRole("button", { name: LABELS.escalation.confirm });
    await user.click(confirm);

    // Navega a la sesión escalada devuelta por el backend.
    expect(pushMock).toHaveBeenCalledWith("/chat/session-2");
    // Deja la nota-enlace en la sesión origen (estado escalado).
    expect(await screen.findByText(LABELS.escalation.doneLink)).toBeTruthy();

    // Exactamente UNA llamada a /escalate, con el origin_message_id del turno.
    const escalateCalls = fetchMock.mock.calls.filter(
      ([input]) => String(input) === "/api/sessions/session-1/escalate",
    );
    expect(escalateCalls).toHaveLength(1);
    const body = JSON.parse((escalateCalls[0][1] as RequestInit).body as string);
    expect(body).toEqual({ origin_message_id: "u1" });
  });

  it("doble clic rápido en «Continuar con Pro»: una sola llamada a /escalate", async () => {
    const fetchMock = stubEscalationFetch({
      escalationEnabled: true,
      detail: escalationSessionDetail([]),
    });
    renderChatContent("funcional", "session-1");

    const confirm = await screen.findByRole("button", { name: LABELS.escalation.confirm });
    // Dos disparos SINCRÓNICOS (antes de cualquier re-render): el guard de
    // re-entrada, no el `disabled`, es lo que garantiza una sola llamada.
    fireEvent.click(confirm);
    fireEvent.click(confirm);

    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/chat/session-2"));
    const escalateCalls = fetchMock.mock.calls.filter(
      ([input]) => String(input) === "/api/sessions/session-1/escalate",
    );
    expect(escalateCalls).toHaveLength(1);
  });
});

describe("ChatContent — tarjeta de escalación: persistencia tras recarga (tarea 5.3)", () => {
  it("sesión ya escalada: la tarjeta arranca en estado escalado (nota-enlace), no en reposo", async () => {
    stubEscalationFetch({
      escalationEnabled: true,
      detail: escalationSessionDetail(["session-2"]),
    });
    renderChatContent("funcional", "session-1");

    // Nota-enlace directamente, sin los botones de reposo.
    expect(await screen.findByText(LABELS.escalation.doneLink)).toBeTruthy();
    expect(screen.queryByRole("button", { name: LABELS.escalation.confirm })).toBeNull();
  });

  it("sesión escalada (destino): muestra la nota-enlace de VUELTA al origen", async () => {
    const detail = escalationSessionDetail([]);
    (detail as { forked_from_id: string | null }).forked_from_id = "session-origin";
    stubEscalationFetch({ escalationEnabled: true, detail });
    renderChatContent("funcional", "session-1");

    const back = await screen.findByRole("button", { name: LABELS.escalationOriginLink });
    await userEvent.setup().click(back);
    expect(pushMock).toHaveBeenCalledWith("/chat/session-origin");
  });
});

/**
 * Tarea 5.4 (selector de versiones de ramas, vista 09 / Flujo G): al cargar una
 * sesión con ramas, el detalle trae TODAS las versiones como lista plana con
 * `parent_id` + `active_leaf_id`; el selector "‹ N/M ›" aparece junto al mensaje
 * ramificado y alternar re-renderiza SOLO la porción posterior de la rama
 * seleccionada, con scroll anclado al mensaje ramificado y conservando la rama no
 * seleccionada intacta.
 */

/** Metadatos de turno del agente (Funcional: sin `telemetry`, mismo shape que
 * `layer_turn_metadata`) reutilizando el helper de arriba. */
function branchedSessionDetail(): unknown {
  return {
    id: "session-1",
    agent_id: "default_chat",
    title: "Conversación con ramas",
    model_profile: "deepseek-v4-flash",
    forked_from_id: null,
    escalated_session_ids: [],
    // La rama activa es la editada (`a2b`), así el default muestra la rama B.
    active_leaf_id: "a2b",
    in_progress_turn: null,
    // u1 ── a1 ─┬─ u2a ── a2a (rama A)
    //           └─ u2b ── a2b (rama B, editada = activa)
    messages: [
      { id: "u1", parent_id: null, role: "user", content: "Hola", status: "complete", created_at: "2026-07-10T14:00:00Z", turn_metadata: null },
      { id: "a1", parent_id: "u1", role: "assistant", content: "Respuesta inicial", status: "complete", created_at: "2026-07-10T14:00:03Z", turn_metadata: assistantTurnMetadata() },
      { id: "u2a", parent_id: "a1", role: "user", content: "Pregunta A", status: "complete", created_at: "2026-07-10T14:01:00Z", turn_metadata: null },
      { id: "a2a", parent_id: "u2a", role: "assistant", content: "rama A", status: "complete", created_at: "2026-07-10T14:01:05Z", turn_metadata: assistantTurnMetadata() },
      { id: "u2b", parent_id: "a1", role: "user", content: "Pregunta B", status: "complete", created_at: "2026-07-10T14:02:00Z", turn_metadata: null },
      { id: "a2b", parent_id: "u2b", role: "assistant", content: "rama B", status: "complete", created_at: "2026-07-10T14:02:05Z", turn_metadata: assistantTurnMetadata() },
    ],
  };
}

/** Instala un mock de `scrollIntoView` (jsdom no lo implementa) que registra el
 * `data-message-id` del elemento sobre el que se llamó. Devuelve el array de ids
 * y un restaurador para no contaminar otros tests. */
function trackScrollIntoView(): { scrolledIds: (string | null)[]; restore: () => void } {
  const scrolledIds: (string | null)[] = [];
  const original = Element.prototype.scrollIntoView;
  Element.prototype.scrollIntoView = vi.fn(function (this: HTMLElement) {
    scrolledIds.push(this.getAttribute("data-message-id"));
  });
  return {
    scrolledIds,
    restore: () => {
      Element.prototype.scrollIntoView = original;
    },
  };
}

describe("ChatContent — selector de versiones de ramas (tarea 5.4)", () => {
  it("alterna entre dos ramas dos veces conservando el contenido EXACTO de cada una, con scroll anclado y sin re-montar el prefijo", async () => {
    const user = userEvent.setup();
    stubSessionFetch(branchedSessionDetail());
    const { container } = renderChatContent("funcional", "session-1");

    // Default: rama activa = la editada (rama B), selector "2/2" en el mensaje
    // ramificado; la rama A no está en el DOM (no se mezcla ni se pierde: vive
    // en el árbol, no renderizada).
    await screen.findByText("rama B");
    expect(screen.getByText("2/2")).toBeTruthy();
    expect(screen.queryByText("rama A")).toBeNull();

    // Prefijo previo al punto de bifurcación: se captura su nodo para probar que
    // NO se re-monta al alternar (clave estable por message id).
    const u1Before = container.querySelector('[data-message-id="u1"]');
    const a1Before = container.querySelector('[data-message-id="a1"]');
    expect(u1Before).not.toBeNull();

    const { scrolledIds, restore } = trackScrollIntoView();
    try {
      // 1) B -> A (flecha ‹): se muestran EXACTAMENTE los mensajes posteriores de
      //    la rama A; la rama B desaparece del DOM (queda intacta en memoria).
      await user.click(screen.getByRole("button", { name: "Versión anterior" }));
      await screen.findByText("rama A");
      expect(screen.getByText("Pregunta A")).toBeTruthy();
      expect(screen.queryByText("rama B")).toBeNull();
      expect(screen.queryByText("Pregunta B")).toBeNull();
      expect(screen.getByText("1/2")).toBeTruthy();
      // Scroll anclado al mensaje ramificado recién seleccionado (u2a).
      expect(scrolledIds.at(-1)).toBe("u2a");
      // Prefijo NO re-montado: mismo nodo del DOM.
      expect(container.querySelector('[data-message-id="u1"]')).toBe(u1Before);
      expect(container.querySelector('[data-message-id="a1"]')).toBe(a1Before);

      // 2) A -> B (flecha ›): vuelve la rama B con su contenido exacto.
      await user.click(screen.getByRole("button", { name: "Versión siguiente" }));
      await screen.findByText("rama B");
      expect(screen.queryByText("rama A")).toBeNull();
      expect(screen.getByText("2/2")).toBeTruthy();
      expect(scrolledIds.at(-1)).toBe("u2b");

      // 3) B -> A de nuevo: el contenido de la rama A sigue EXACTO (no se corrompió).
      await user.click(screen.getByRole("button", { name: "Versión anterior" }));
      await screen.findByText("rama A");
      expect(screen.queryByText("rama B")).toBeNull();
      expect(screen.getByText("1/2")).toBeTruthy();

      // 4) A -> B: cierra el segundo ciclo; ambas ramas conservaron su contenido.
      await user.click(screen.getByRole("button", { name: "Versión siguiente" }));
      await screen.findByText("rama B");
      expect(screen.queryByText("rama A")).toBeNull();
      expect(screen.getByText("2/2")).toBeTruthy();

      // El prefijo nunca se re-montó en todo el ciclo.
      expect(container.querySelector('[data-message-id="u1"]')).toBe(u1Before);
    } finally {
      restore();
    }
  });

  it("editar por primera vez: el detalle post-edición trae 2 versiones y el selector aparece con «2/2» en el mensaje editado", async () => {
    // Shape real de una sesión tras la primera edición (el `POST` con
    // `edits_message_id` creó un hermano): el mensaje editado y su original
    // comparten `parent_id null`; la rama activa es la editada.
    const detail = {
      id: "session-1",
      agent_id: "default_chat",
      title: "Conversación",
      model_profile: "deepseek-v4-flash",
      forked_from_id: null,
      escalated_session_ids: [],
      active_leaf_id: "a-edit",
      in_progress_turn: null,
      messages: [
        { id: "u-orig", parent_id: null, role: "user", content: "Pregunta con error", status: "complete", created_at: "2026-07-10T14:00:00Z", turn_metadata: null },
        { id: "a-orig", parent_id: "u-orig", role: "assistant", content: "Respuesta al original", status: "complete", created_at: "2026-07-10T14:00:03Z", turn_metadata: assistantTurnMetadata() },
        { id: "u-edit", parent_id: null, role: "user", content: "Pregunta corregida", status: "complete", created_at: "2026-07-10T14:05:00Z", turn_metadata: null },
        { id: "a-edit", parent_id: "u-edit", role: "assistant", content: "Respuesta a la corrección", status: "complete", created_at: "2026-07-10T14:05:03Z", turn_metadata: assistantTurnMetadata() },
      ],
    };
    stubSessionFetch(detail);
    renderChatContent("funcional", "session-1");

    // Por default se ve la versión editada (2/2) y su respuesta.
    await screen.findByText("Respuesta a la corrección");
    expect(screen.getByText("Pregunta corregida")).toBeTruthy();
    expect(screen.getByText("2/2")).toBeTruthy();
    // El selector es operable: "‹" vuelve a la versión original.
    expect(screen.getByRole("group", { name: "versión 2 de 2" })).toBeTruthy();
  });

  it("raíz editada (parent_id null con 2 versiones): alternar cambia toda la conversación", async () => {
    const user = userEvent.setup();
    const detail = {
      id: "session-1",
      agent_id: "default_chat",
      title: "Conversación",
      model_profile: "deepseek-v4-flash",
      forked_from_id: null,
      escalated_session_ids: [],
      active_leaf_id: "ab",
      in_progress_turn: null,
      messages: [
        { id: "ra", parent_id: null, role: "user", content: "Pregunta raíz A", status: "complete", created_at: "2026-07-10T14:00:00Z", turn_metadata: null },
        { id: "aa", parent_id: "ra", role: "assistant", content: "raíz respuesta A", status: "complete", created_at: "2026-07-10T14:00:03Z", turn_metadata: assistantTurnMetadata() },
        { id: "rb", parent_id: null, role: "user", content: "Pregunta raíz B", status: "complete", created_at: "2026-07-10T14:05:00Z", turn_metadata: null },
        { id: "ab", parent_id: "rb", role: "assistant", content: "raíz respuesta B", status: "complete", created_at: "2026-07-10T14:05:03Z", turn_metadata: assistantTurnMetadata() },
      ],
    };
    stubSessionFetch(detail);
    renderChatContent("funcional", "session-1");

    // Default = raíz activa (B).
    await screen.findByText("raíz respuesta B");
    expect(screen.getByText("2/2")).toBeTruthy();
    expect(screen.queryByText("raíz respuesta A")).toBeNull();

    const { restore } = trackScrollIntoView();
    try {
      // Alternar a la raíz A cambia TODA la conversación (raíz + respuesta).
      await user.click(screen.getByRole("button", { name: "Versión anterior" }));
      await screen.findByText("raíz respuesta A");
      expect(screen.getByText("Pregunta raíz A")).toBeTruthy();
      expect(screen.queryByText("raíz respuesta B")).toBeNull();
      expect(screen.getByText("1/2")).toBeTruthy();
    } finally {
      restore();
    }
  });
});

/**
 * Tarea 5.5 (edición de mensaje -> rama nueva): 7 mensajes en cadena lineal
 * (sin ramas todavía) -- editar el PRIMERO ("Pregunta 1") tiene 6 mensajes
 * posteriores en la rama visible (aviso "reprocesa 6 mensajes" visible,
 * requirement "Aviso suave de regeneración costosa al editar lejos");
 * editar el ÚLTIMO ("Pregunta 4") no tiene ninguno (sin aviso).
 */
const EDIT_TREE_DETAIL = {
  id: "session-1",
  agent_id: "default_chat",
  title: "Conversación",
  model_profile: "deepseek-v4-flash",
  forked_from_id: null,
  escalated_session_ids: [],
  active_leaf_id: "u4",
  in_progress_turn: null,
  messages: [
    { id: "u1", parent_id: null, role: "user", content: "Pregunta 1", status: "complete", created_at: "2026-07-10T14:00:00Z", turn_metadata: null },
    { id: "a1", parent_id: "u1", role: "assistant", content: "Respuesta 1", status: "complete", created_at: "2026-07-10T14:00:03Z", turn_metadata: assistantTurnMetadata() },
    { id: "u2", parent_id: "a1", role: "user", content: "Pregunta 2", status: "complete", created_at: "2026-07-10T14:01:00Z", turn_metadata: null },
    { id: "a2", parent_id: "u2", role: "assistant", content: "Respuesta 2", status: "complete", created_at: "2026-07-10T14:01:03Z", turn_metadata: assistantTurnMetadata() },
    { id: "u3", parent_id: "a2", role: "user", content: "Pregunta 3", status: "complete", created_at: "2026-07-10T14:02:00Z", turn_metadata: null },
    { id: "a3", parent_id: "u3", role: "assistant", content: "Respuesta 3", status: "complete", created_at: "2026-07-10T14:02:03Z", turn_metadata: assistantTurnMetadata() },
    { id: "u4", parent_id: "a3", role: "user", content: "Pregunta 4", status: "complete", created_at: "2026-07-10T14:03:00Z", turn_metadata: null },
  ],
};

/** Stub que responde el agente, el detalle de la sesión (SIEMPRE el mismo
 * `detail` -- alcanza para probar la edición en vivo, la tarea 5.4 ya cubre
 * la resolución del árbol tras recargar) y el `POST .../messages/stream`
 * (SSE controlado a mano, mismo patrón que `message-column.test.tsx`). */
function stubEditFetch(detail: unknown) {
  const reader = createControlledReader();
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
      return new Response(JSON.stringify(detail), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    if (url === "/api/sessions/session-1/messages/stream" && init?.method === "POST") {
      return mockSseResponse(reader.reader, {
        headers: { "X-Turn-Id": "turn-edit-1", "X-User-Message-Id": "u1-edit" },
      });
    }
    throw new Error(`fetch inesperado en este test: ${url} (${init?.method ?? "GET"})`);
  });
  vi.stubGlobal("fetch", fetchMock);
  return { fetchMock, reader };
}

describe("ChatContent — edición de mensaje (tarea 5.5)", () => {
  it("textarea precargado, aviso «reprocesa 6 mensajes», atenuación del resto y confirmar llama sendTurn con edits_message_id correcto", async () => {
    const user = userEvent.setup();
    const { fetchMock, reader } = stubEditFetch(EDIT_TREE_DETAIL);
    const { container } = renderChatContent("funcional", "session-1");

    await screen.findByText("Pregunta 4");

    // El primer botón "Editar" en el DOM corresponde a "Pregunta 1" (u1, el
    // primer mensaje del camino visible).
    const editButtons = screen.getAllByRole("button", {
      name: "Editar mensaje (crea una rama nueva)",
    });
    await user.click(editButtons[0]);

    // Textarea precargado con el texto ORIGINAL del mensaje.
    const textarea = screen.getByLabelText("Editar mensaje") as HTMLTextAreaElement;
    expect(textarea.value).toBe("Pregunta 1");

    // Aviso visible (N=6, ≥3) y NO bloquea "Crear rama".
    expect(screen.getByText("Crear una rama acá reprocesa 6 mensajes")).toBeTruthy();
    const confirmBtn = screen.getByRole("button", { name: "Crear rama" }) as HTMLButtonElement;
    expect(confirmBtn.disabled).toBe(false);

    // El resto del hilo (todo lo posterior a "Pregunta 1") queda atenuado;
    // el mensaje en edición NUNCA se atenúa.
    const items = Array.from(container.querySelectorAll<HTMLLIElement>("li[data-message-id]"));
    expect(items).toHaveLength(7);
    expect(items[0].classList.contains("is-dimmed")).toBe(false);
    for (const item of items.slice(1)) {
      expect(item.classList.contains("is-dimmed")).toBe(true);
      expect(item.getAttribute("aria-hidden")).toBe("true");
    }

    // Confirmar -> el mismo `sendTurn` del envío normal, con
    // `edits_message_id` apuntando al mensaje editado (decisión 4 de
    // `design.md`).
    await user.click(confirmBtn);
    await waitFor(() => {
      const streamCall = fetchMock.mock.calls.find(
        ([callUrl]) =>
          (typeof callUrl === "string" ? callUrl : callUrl.toString()) ===
          "/api/sessions/session-1/messages/stream",
      );
      expect(streamCall).toBeTruthy();
    });
    const [, streamInit] = fetchMock.mock.calls.find(
      ([callUrl]) =>
        (typeof callUrl === "string" ? callUrl : callUrl.toString()) ===
        "/api/sessions/session-1/messages/stream",
    )!;
    expect(JSON.parse(streamInit!.body as string)).toEqual({
      text: "Pregunta 1",
      edits_message_id: "u1",
    });

    // Cierra el turno para no dejar la conexión colgada -- el cierre dispara
    // la recarga de la sesión (ver el efecto de "pliegue", rama
    // `editTurnRef.current`), que sale de la edición: se espera esa señal
    // observable para no dejar trabajo asincrónico pendiente tras el test.
    reader.push(
      sseFrame(1, "done", {
        turn_id: "turn-edit-1",
        user_message_id: "u1-edit",
        assistant_message_id: "a1-edit",
        reprocessed_count: 6,
        stopped: false,
        is_alternate_model: false,
        compacted: false,
        escalation: null,
      }),
    );
    reader.close();
    await waitFor(() => expect(screen.queryByLabelText("Editar mensaje")).toBeNull());
  });

  it("editar el último mensaje de la conversación: sin aviso de re-proceso", async () => {
    const user = userEvent.setup();
    stubEditFetch(EDIT_TREE_DETAIL);
    renderChatContent("funcional", "session-1");
    await screen.findByText("Pregunta 4");

    const editButtons = screen.getAllByRole("button", {
      name: "Editar mensaje (crea una rama nueva)",
    });
    // El ÚLTIMO botón corresponde a "Pregunta 4" (u4, el último del camino).
    await user.click(editButtons[editButtons.length - 1]);

    expect((screen.getByLabelText("Editar mensaje") as HTMLTextAreaElement).value).toBe(
      "Pregunta 4",
    );
    expect(screen.queryByText(/reprocesa/)).toBeNull();
  });

  it("cancelar restaura la burbuja de lectura sin llamadas de red adicionales", async () => {
    const user = userEvent.setup();
    const { fetchMock } = stubEditFetch(EDIT_TREE_DETAIL);
    renderChatContent("funcional", "session-1");
    await screen.findByText("Pregunta 4");

    const callsBeforeEdit = fetchMock.mock.calls.length;
    const editButtons = screen.getAllByRole("button", {
      name: "Editar mensaje (crea una rama nueva)",
    });
    await user.click(editButtons[0]);
    await user.type(screen.getByLabelText("Editar mensaje"), " (cambiado)");
    await user.click(screen.getByRole("button", { name: "Cancelar" }));

    // Vuelve la burbuja de lectura con el texto ORIGINAL -- el cambio
    // tipeado se descarta, nunca se persiste.
    expect(screen.getByText("Pregunta 1")).toBeTruthy();
    expect(screen.queryByLabelText("Editar mensaje")).toBeNull();
    // Cancelar NUNCA llama a ningún endpoint.
    expect(fetchMock.mock.calls.length).toBe(callsBeforeEdit);
  });
});

/**
 * Tareas 6.1/6.2 (tarjetas de error accionables, vista 10 -- subconjunto
 * `GATEWAY_OFFLINE`/`QUOTA`). La redacción por rol (tarea 6.3) se ejercita a
 * fondo en `components/chat/error-card.test.tsx` (los 3 roles × los 2
 * códigos, sobre el componente compartido que AMBAS tarjetas usan para
 * decidir esa redacción) -- acá se cubre el flujo end-to-end: clasificación
 * real del error del hook (`use-turn-stream.ts`), reintento con backoff sin
 * duplicar el mensaje del usuario, y el bloqueo del composer por cuota.
 */
const EMPTY_SESSION_DETAIL = {
  id: "session-1",
  agent_id: "default_chat",
  title: null,
  model_profile: "deepseek-v4-flash",
  forked_from_id: null,
  escalated_session_ids: [],
  active_leaf_id: null,
  in_progress_turn: null,
  messages: [],
};

/** Stub que responde el agente, el detalle de una sesión vacía y SIEMPRE
 * `status` en el POST del turno (`.../messages/stream`) -- el doble de
 * `fetch` que fuerza la clasificación de `classifyTurnError` (ver su
 * docstring). Cuenta las llamadas al endpoint de stream aparte porque
 * varias tareas del mismo test necesitan distinguirlas de la carga de
 * sesión/agente. */
function stubTurnErrorFetch(status: number) {
  const reader = createControlledReader();
  let streamCalls = 0;
  const bodies: string[] = [];
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
      return new Response(JSON.stringify(EMPTY_SESSION_DETAIL), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    if (url === "/api/sessions/session-1/messages/stream" && init?.method === "POST") {
      streamCalls += 1;
      bodies.push(JSON.parse(init.body as string).text as string);
      return mockSseResponse(reader.reader, { status });
    }
    throw new Error(`fetch inesperado en este test: ${url} (${init?.method ?? "GET"})`);
  });
  vi.stubGlobal("fetch", fetchMock);
  return { fetchMock, streamCalls: () => streamCalls, bodies };
}

describe("ChatContent — tarjeta GATEWAY_OFFLINE (tarea 6.1)", () => {
  // Timers falsos desde el arranque del test (no a mitad de camino): el
  // countdown arranca su `setInterval` apenas se monta `GatewayOfflineCard`
  // (justo después del primer fallo), así que si instaláramos
  // `vi.useFakeTimers()` recién ahí, ese intervalo ya habría quedado
  // agendado con el `setInterval` REAL -- Vitest solo intercepta llamadas a
  // temporizadores hechas DESPUÉS de instalar el mock. Por eso todo este
  // bloque usa `fireEvent` (no `userEvent`, que agenda sus propios
  // temporizadores reales internos) + `act`/`vi.advanceTimersByTimeAsync`
  // para asentar cada cadena async a mano.
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it(
    "503 muestra la tarjeta con countdown; a los 5 s reintenta UNA vez con el mismo texto sin " +
      "duplicar el mensaje del usuario; segundo fallo -> countdown de 15 s; «Reintentar ahora» " +
      "dispara de inmediato",
    async () => {
      const { streamCalls, bodies } = stubTurnErrorFetch(503);
      renderChatContent("tecnico", "session-1");

      // Deja resolver la carga de la sesión vacía y del agente (fetch mock
      // resuelto por Promise, sin `setTimeout` real de por medio, pero
      // `advanceTimersByTimeAsync` igual asienta la cadena de microtasks).
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });

      const textarea = screen.getByLabelText("Mensaje") as HTMLTextAreaElement;
      fireEvent.change(textarea, { target: { value: "Hola" } });
      await act(async () => {
        fireEvent.click(screen.getByRole("button", { name: "Enviar" }));
        await vi.advanceTimersByTimeAsync(0);
      });

      // Primer fallo: tarjeta GATEWAY_OFFLINE (Técnico ve el código mono
      // arriba) con countdown en el primer paso del backoff (5 s). El
      // mensaje del usuario sigue en el hilo, una sola vez.
      expect(screen.getByText("GATEWAY_OFFLINE", { selector: ".error-card__code" })).toBeTruthy();
      expect(screen.getByText("Reintentando en 5 s")).toBeTruthy();
      expect(screen.getAllByText("Hola")).toHaveLength(1);
      expect(streamCalls()).toBe(1);

      // El countdown llega a 0: dispara EXACTAMENTE un reintento (un
      // segundo POST al stream) con el MISMO texto -- el eco del usuario
      // sigue apareciendo una única vez (no se duplica).
      await act(async () => {
        await vi.advanceTimersByTimeAsync(5000);
      });
      expect(streamCalls()).toBe(2);
      expect(bodies).toEqual(["Hola", "Hola"]);
      expect(screen.getAllByText("Hola")).toHaveLength(1);

      // El segundo fallo consecutivo pasa al SIGUIENTE paso del backoff (15 s).
      expect(screen.getByText("Reintentando en 15 s")).toBeTruthy();

      // "Reintentar ahora" dispara un reintento de inmediato, sin esperar
      // el countdown.
      await act(async () => {
        fireEvent.click(screen.getByRole("button", { name: "Reintentar ahora" }));
        await vi.advanceTimersByTimeAsync(0);
      });
      expect(streamCalls()).toBe(3);
      expect(bodies).toEqual(["Hola", "Hola", "Hola"]);
    },
  );
});

describe("ChatContent — tarjeta QUOTA (tarea 6.2)", () => {
  it('402 al enviar un turno: tarjeta QUOTA visible, composer deshabilitado con motivo, botón «Solicitar liberación» presente', async () => {
    const user = userEvent.setup();
    const { streamCalls } = stubTurnErrorFetch(402);
    renderChatContent("funcional", "session-1");

    const textarea = await screen.findByLabelText("Mensaje");
    await user.type(textarea, "Hola");
    await user.click(screen.getByRole("button", { name: "Enviar" }));

    // Tarjeta QUOTA visible (rol Funcional: redacción sin jerga, código al
    // pie -- ver `error-card.test.tsx` para la cobertura exhaustiva de
    // redacción por rol).
    await screen.findByText(LABELS.quota.funcionalWhy);
    expect(screen.getByText(`${LABELS.quota.supportCodePrefix} QUOTA`)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Solicitar liberación" })).toBeTruthy();

    // El composer queda deshabilitado con el motivo inline (bloqueo, no
    // solo error de turno -- vista 10 §Interacciones).
    const composerTextarea = screen.getByLabelText("Mensaje") as HTMLTextAreaElement;
    expect(composerTextarea.disabled).toBe(true);
    expect(screen.getByText(LABELS.quotaComposerDisabledReason)).toBeTruthy();

    // Click en "Solicitar liberación" no rompe nada (noop documentado hacia
    // d16-cuotas-liberaciones): sin llamada de red adicional, colapsa a la
    // nota "solicitud enviada".
    const callsBeforeRequest = streamCalls();
    await user.click(screen.getByRole("button", { name: "Solicitar liberación" }));
    expect(screen.getByText("Solicitud enviada")).toBeTruthy();
    expect(streamCalls()).toBe(callsBeforeRequest);
  });
});
