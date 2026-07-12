import userEvent from "@testing-library/user-event";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createChatApiDouble } from "@/lib/chat/test-support/api-double";
import { SessionProvider, type SessionContextValue } from "@/lib/session-context";
import { ChatContent, type ChatContentLabels } from "./chat-content";

/**
 * Test E2E del Flujo D (`design/FLUJOS.md` Flujo D, `design/VISTAS/02-chat.md`
 * vista 08), tarea 9.3 de d13-chat-conversacion: escalación manual a Pro.
 *
 * "E2E" acá (sin Playwright/browser-runner en el repo, ver
 * `openspec/changes/d13-chat-conversacion/design.md`) es un test de
 * INTEGRACIÓN de flujo completo a nivel de UI, con el mismo enfoque que
 * `e2e-flujo-b.test.tsx`: monta la página real (`ChatContent`, el componente
 * que `chat/nueva/page.tsx` y `chat/[sessionId]/page.tsx` renderizan) con sus
 * labels reales de `messages/es.json` (namespace `Chat`, copiados verbatim --
 * `getTranslations()` de next-intl es server-only y no se resuelve
 * sincrónicamente en Vitest/jsdom) y la maneja como un usuario contra
 * `createChatApiDouble` (`lib/chat/test-support/api-double.ts`), el doble de
 * alta fidelidad del contrato HTTP/SSE de `resultarai/app/api/chat.py`/
 * `chat_stream.py`.
 *
 * ── El marcador crudo `<<<NEEDS_PRO>>>` y la doble barrera de garantías ──
 *
 * GARANTÍA SERVER-SIDE (el marcador nunca viaja en el wire, ni siquiera
 * partido entre dos fragmentos, y se suprime incondicionalmente del texto):
 * ya está cubierta por `tests/app/chat/test_streaming.py` (tarea 1.4, casos
 * "marcador partido entre fragmentos consecutivos" y "supresión
 * incondicional del texto"). El doble de este harness ESPEJA a ese backend
 * ya-filtrado: `TurnHandle.pushFragment` documenta que su texto "ya se asume
 * filtrado del marcador" (igual que `chat_stream.py`, donde el marcador nunca
 * llega a `fragment.data`) -- el doble NO re-filtra, porque modela el punto
 * del pipeline DESPUÉS del filtro. Por eso inyectar el marcador crudo por
 * `pushFragment` no modela nada real (modelaría un backend roto que ya no
 * filtra), y este test deliberadamente NO lo hace: la superficie server-side
 * es responsabilidad de `test_streaming.py`.
 *
 * GARANTÍA CLIENT-SIDE (lo que ESTE test agrega): un espía envuelve
 * `double.fetch` y acumula TODO lo que el cliente efectivamente lee de cada
 * respuesta -- cada chunk SSE crudo (frames `fragment`/`escalation`/`done`) y
 * cada cuerpo JSON (`POST /sessions`, `GET /sessions/{id}`, `POST /escalate`,
 * `GET /agents/{id}`). Al final del recorrido completo se afirma que el
 * marcador `<<<NEEDS_PRO>>>` (y su forma desnuda `NEEDS_PRO`) NO aparece en
 * NINGÚN payload entregado al cliente, y que tampoco aparece en el DOM en
 * ningún punto (se re-chequea tras cada fase). La escalación llega SOLO como
 * evento estructurado (`event: escalation`, con `reason`/`target_profile`),
 * nunca como texto. El test está construido para FALLAR si el marcador
 * apareciera: el mismo detector que da positivo sobre un string de control
 * que sí lo contiene da negativo sobre el tráfico real (sanity-check al
 * final).
 */

const { pushMock, replaceMock } = vi.hoisted(() => ({
  pushMock: vi.fn(),
  replaceMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: replaceMock,
    push: pushMock,
  }),
}));

// Valores REALES de `messages/es.json` (namespace `Chat`), copiados verbatim
// -- mismo criterio que `e2e-flujo-b.test.tsx`/`chat-content.test.tsx`:
// `buildChatLabels` los resuelve vía `getTranslations()` de next-intl
// (server-only, no invocable sincrónicamente en Vitest/jsdom), así que se
// copian tal cual del catálogo en vez de inventar redacción nueva.
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
    attachmentStates: {
      uploading: "Subiendo… {percent}%",
      processing: "Procesando contenido…",
      readyTechAdmin: "Listo · {tokens} tokens",
      readyFunctional: "Listo · usa {percent}% del espacio del mensaje",
      readyTruncated: "Listo · incluye el {percent}% del archivo — tocá para ver qué verá el agente",
      warning: "Revisá antes de enviar",
      blocked: "Bloqueado — contiene credenciales",
      error: "No se pudo procesar",
    },
    attachmentPiiConfirmation: "Confirmo que son datos de prueba",
    attachmentPiiCancel: "Cancelar",
    attachmentPreviewAction: "Ver lo que verá el agente",
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
  compactionIndicator: "Resumimos el historial de esta conversación para que siga funcionando.",
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
  quotaComposerDisabledReason:
    "Alcanzaste tu cuota mensual. Solicitá una liberación para seguir escribiendo.",
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
    piiEntityLabels: {
      EMAIL_ADDRESS: { one: "email", other: "emails" },
      PHONE_NUMBER: { one: "número de teléfono", other: "números de teléfono" },
      BO_PHONE: { one: "número de teléfono", other: "números de teléfono" },
      PERSON: { one: "nombre de persona", other: "nombres de persona" },
      BO_CI: { one: "número de carnet", other: "números de carnet" },
      BO_NIT: { one: "NIT", other: "NIT" },
    },
  },
  attachmentPreview: {
    title: "Esto es exactamente lo que recibirá el agente",
    closeLabel: "Cerrar vista previa",
    footer: "Contenido extraído automáticamente — puede diferir del documento original.",
    loading: "Cargando vista previa…",
    error: "No pudimos cargar la vista previa de este adjunto. Probá de nuevo.",
    metricTechAdmin: "Listo · {tokens} tokens",
    metricFunctional: "Listo · usa {percent}% del espacio del mensaje",
    truncatedNotice:
      "Por el límite de espacio, el agente verá el {percent}% del archivo (se priorizaron las secciones relacionadas con tu consulta). Las partes omitidas están marcadas — podés pedirlas explícitamente en el chat.",
  },
};

function sessionFor(role: SessionContextValue["user"]["role"]): SessionContextValue {
  return {
    user: { name: "carla", role },
    gateway: { status: "ok" },
    pendingApprovals: 0,
    unreadNotifications: 0,
    capabilities: [],
  };
}

// ---------------------------------------------------------------------------
// Espía de payloads entregados al cliente
// ---------------------------------------------------------------------------

/** El marcador crudo de escalación (`b05` `escalation-marker`). NUNCA debe
 * viajar al cliente -- ni entero ni desnudo. */
const RAW_MARKER = "<<<NEEDS_PRO>>>";
const BARE_MARKER = "NEEDS_PRO";

interface CapturedPayload {
  /** Origen del payload, para diagnóstico si la aserción falla. */
  where: string;
  /** El texto EXACTO que el cliente leyó de la respuesta (chunk SSE crudo o
   * cuerpo JSON serializado). */
  body: string;
}

/**
 * Envuelve `innerFetch` (el `double.fetch`) con un espía que acumula TODO lo
 * que el cliente efectivamente LEE de cada respuesta, SIN alterar el paso de
 * datos:
 *
 * - Cuerpos JSON: se registran cuando el consumidor llama `res.json()` (el
 *   único momento en que ese payload "llega" al cliente). Se registra el
 *   resultado serializado, sin re-consumir el body (no se clona ni se lee dos
 *   veces -- solo se envuelve el método que el consumidor ya invoca).
 * - Streams SSE: cada chunk que el consumidor lee vía `body.getReader().read()`
 *   se decodifica y se registra (frame `fragment`/`escalation`/`done` crudo,
 *   texto incluido) antes de devolverlo intacto.
 *
 * Solo se registran RESPUESTAS (servidor -> cliente): el marcador "entregado
 * al cliente" es, por definición, tráfico de bajada. Los cuerpos de request
 * (cliente -> servidor) quedan fuera de alcance a propósito.
 */
function createPayloadSpy(innerFetch: typeof fetch) {
  const payloads: CapturedPayload[] = [];
  const record = (where: string, body: string) => {
    payloads.push({ where, body });
  };

  const spyFetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
    const method = (init?.method ?? "GET").toUpperCase();
    const res = (await innerFetch(input, init)) as unknown as {
      ok: boolean;
      status: number;
      headers: { get(name: string): string | null };
      body: { getReader(): { read(): Promise<{ done: boolean; value?: Uint8Array }> } } | null;
      json(): Promise<unknown>;
    };

    // Objeto envolvente duck-typed: expone EXACTAMENTE la superficie que
    // consumen `use-turn-stream.ts` (`ok`/`status`/`headers.get`/`body.getReader`/
    // `json`) y `chat-content.tsx` (`ok`/`status`/`json`), delegando en `res`
    // y registrando de pasada. No se toca ningún dato: cada método devuelve lo
    // mismo que devolvería el original.
    const wrapped = {
      ok: res.ok,
      status: res.status,
      headers: res.headers,
      async json() {
        const data = await res.json();
        record(`JSON ${method} ${url}`, JSON.stringify(data));
        return data;
      },
      get body() {
        if (res.body === null) return null;
        return {
          getReader() {
            const reader = res.body!.getReader();
            const decoder = new TextDecoder();
            return {
              async read() {
                const chunk = await reader.read();
                if (!chunk.done && chunk.value) {
                  record(`SSE ${method} ${url}`, decoder.decode(chunk.value));
                }
                return chunk;
              },
            };
          },
        };
      },
    };
    return wrapped;
  }) as unknown as typeof fetch;

  return {
    fetch: spyFetch,
    payloads,
    /** Payloads (con su origen) que contienen el marcador -- vacío es limpio. */
    markerHits(): CapturedPayload[] {
      return payloads.filter(
        (p) => p.body.includes(RAW_MARKER) || p.body.includes(BARE_MARKER),
      );
    },
  };
}

function expectNoMarkerInDom(phase: string) {
  const domText = document.body.textContent ?? "";
  expect(domText.includes(RAW_MARKER), `marcador crudo en el DOM (${phase})`).toBe(false);
  expect(domText.includes(BARE_MARKER), `forma desnuda del marcador en el DOM (${phase})`).toBe(
    false,
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  pushMock.mockClear();
  replaceMock.mockClear();
});

describe("Flujo D — escalación manual a Pro (tarea 9.3)", () => {
  it("recorre el flujo completo: tarjeta tras el evento, «Continuar con Pro» abre sesión Pro con nota-enlace bidireccional, origen intacto, idempotencia -- y el marcador crudo nunca llega al cliente", async () => {
    const user = userEvent.setup();
    const double = createChatApiDouble({
      role: "funcional",
      escalationEnabled: true,
      escalationTargetProfile: "deepseek_v4_pro",
    });
    const spy = createPayloadSpy(double.fetch);
    vi.stubGlobal("fetch", spy.fetch);

    // --- Fase 1 (Flujo D, punto 1): un turno normal en el chat --------------
    const originView = render(
      <SessionProvider value={sessionFor("funcional")}>
        <ChatContent initialSessionId={null} labels={LABELS} />
      </SessionProvider>,
    );

    const question =
      "¿Cómo consolido el balance entre las localizaciones de Bolivia, Perú y Paraguay con normativas distintas?";
    const textarea = await screen.findByLabelText(LABELS.composer.textareaLabel);
    await user.type(textarea, question);
    await user.keyboard("{Enter}");

    // Enter creó la sesión origen y arrancó el stream.
    await waitFor(() => expect(double.currentTurn).not.toBeNull());
    const turn = double.currentTurn!;
    expect(double.getSessions()).toHaveLength(1);
    const originSessionId = double.getSessions()[0].id;
    expect(turn.sessionId).toBe(originSessionId);
    expect(await screen.findByText(question)).toBeTruthy();

    // --- Fase 2 (Flujo D, punto 2): fragmentos LIMPIOS + evento de escalación
    // El guion del doble entrega SOLO texto ya filtrado (espejo del backend,
    // ver el docstring de cabecera) y luego el evento de escalación ANTES del
    // `done` -- independiente del texto, igual que el contrato real.
    turn.pushFragment("Puedo darte un panorama general, ");
    turn.pushFragment(
      "pero la consolidación multi-país con normativas distintas requiere un análisis más profundo.",
    );
    const escalationReason =
      "Tu consulta cruza varias localizaciones tributarias y amerita el modelo avanzado.";
    turn.pushEscalation({ reason: escalationReason, target_profile: "deepseek_v4_pro" });
    turn.complete();

    // --- Fase 3 (Flujo D, punto 3): la tarjeta aparece tras la respuesta ----
    // Embebida después del mensaje del turno, con razón, perfil destino y los
    // dos botones EXACTOS.
    const confirmButton = await screen.findByRole("button", { name: LABELS.escalation.confirm });
    expect(confirmButton).toBeTruthy();
    expect(screen.getByRole("button", { name: LABELS.escalation.dismiss })).toBeTruthy();
    expect(screen.getByText(escalationReason)).toBeTruthy();
    expect(screen.getByText("deepseek_v4_pro")).toBeTruthy();
    expect(screen.getByText(LABELS.escalation.title)).toBeTruthy();
    // El texto final del turno se renderizó completo y limpio.
    expect(screen.getByText(/requiere un análisis más profundo\./)).toBeTruthy();
    expectNoMarkerInDom("fase 3 -- tarjeta visible");
    expect(spy.markerHits()).toEqual([]);

    // Copia profunda del estado del origen ANTES de escalar (para la aserción
    // "byte a byte" de la fase 5).
    const originMessagesBefore = structuredClone(double.getMessages(originSessionId));
    expect(originMessagesBefore).toHaveLength(2); // user + assistant
    const originUserMessageId = originMessagesBefore.find((m) => m.role === "user")!.id;

    // --- Fase 4 (Flujo D, punto 4): «Continuar con Pro» --------------------
    pushMock.mockClear();
    await user.click(confirmButton);

    // Una sola llamada a `/escalate`, sesión nueva registrada en el doble.
    await waitFor(() => expect(double.getSessions()).toHaveLength(2));
    const escalated = double.getSessions().find((s) => s.forkedFromId === originSessionId)!;
    expect(escalated).toBeTruthy();
    const escalatedSessionId = escalated.id;
    // Perfil Pro y enlace forked_from_id al origen.
    expect(escalated.modelProfile).toBe("deepseek_v4_pro");
    expect(escalated.forkedFromId).toBe(originSessionId);
    // Sembrada con el re-planteo: el mensaje de usuario del origen.
    const escalatedMessages = double.getMessages(escalatedSessionId);
    expect(escalatedMessages).toHaveLength(1);
    expect(escalatedMessages[0].role).toBe("user");
    expect(escalatedMessages[0].content).toBe(question);
    // Navegación (router.push espiado) a /chat/{escalated_session_id}.
    await waitFor(() => expect(pushMock).toHaveBeenCalledWith(`/chat/${escalatedSessionId}`));
    expect(pushMock).toHaveBeenCalledTimes(1);
    // La tarjeta en el origen colapsó a nota-enlace (idempotencia: no re-usable).
    expect(await screen.findByText(LABELS.escalation.doneLink)).toBeTruthy();
    expect(screen.queryByRole("button", { name: LABELS.escalation.confirm })).toBeNull();
    expectNoMarkerInDom("fase 4 -- tras escalar");
    expect(spy.markerHits()).toEqual([]);

    // --- Fase 5 (Flujo D, punto 5): la sesión original queda INTACTA --------
    // Idéntica byte a byte a la copia previa (escalar no muta el origen).
    expect(double.getMessages(originSessionId)).toEqual(originMessagesBefore);

    originView.unmount();

    // --- Fase 6 (Flujo D, punto 6): bidireccionalidad ----------------------
    // 6a. La sesión ESCALADA muestra la nota-enlace de VUELTA al origen.
    pushMock.mockClear();
    render(
      <SessionProvider value={sessionFor("funcional")}>
        <ChatContent initialSessionId={escalatedSessionId} labels={LABELS} />
      </SessionProvider>,
    );
    const backLink = await screen.findByRole("button", { name: LABELS.escalationOriginLink });
    await user.click(backLink);
    expect(pushMock).toHaveBeenCalledWith(`/chat/${originSessionId}`);
    expectNoMarkerInDom("fase 6a -- sesión escalada");
    expect(spy.markerHits()).toEqual([]);

    cleanup();

    // 6b. La sesión ORIGEN (recargada) muestra la nota-enlace hacia la escalada.
    pushMock.mockClear();
    render(
      <SessionProvider value={sessionFor("funcional")}>
        <ChatContent initialSessionId={originSessionId} labels={LABELS} />
      </SessionProvider>,
    );
    const doneLink = await screen.findByRole("button", { name: /Continuaste esta consulta/ });
    expect(doneLink).toBeTruthy();
    // Sin botones de reposo: arranca directamente en la nota-enlace persistida.
    expect(screen.queryByRole("button", { name: LABELS.escalation.confirm })).toBeNull();
    await user.click(doneLink);
    expect(pushMock).toHaveBeenCalledWith(`/chat/${escalatedSessionId}`);
    // El origen sigue intacto tras recargarlo y navegar.
    expect(double.getMessages(originSessionId)).toEqual(originMessagesBefore);
    expectNoMarkerInDom("fase 6b -- sesión origen recargada");
    expect(spy.markerHits()).toEqual([]);

    // --- Fase 7 (Flujo D, punto 8): idempotencia de flujo (doble pestaña) ---
    // Segunda activación de `/escalate` con el MISMO origen (simula la otra
    // pestaña): misma sesión de destino, `created: false`, sin duplicados.
    const idempotentRes = await spy.fetch(`/api/sessions/${originSessionId}/escalate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ origin_message_id: originUserMessageId }),
    });
    const idempotentData = (await idempotentRes.json()) as {
      escalated_session_id: string;
      created: boolean;
    };
    expect(idempotentData.created).toBe(false);
    expect(idempotentData.escalated_session_id).toBe(escalatedSessionId);
    // Sin sesiones nuevas: sigue habiendo exactamente 2 (origen + escalada).
    expect(double.getSessions()).toHaveLength(2);

    // --- Fase 8 (Flujo D, punto 7): aserción central del marcador -----------
    // El espía capturó tráfico real y NO TRIVIAL: la escalación llegó como
    // evento SSE estructurado (`event: escalation` con el perfil destino),
    // nunca como marcador en el texto.
    const escalationEventPayloads = spy.payloads.filter(
      (p) => p.body.includes("escalation") && p.body.includes("deepseek_v4_pro"),
    );
    expect(escalationEventPayloads.length).toBeGreaterThan(0);
    // Sanity-check del detector: da POSITIVO sobre un string de control que sí
    // contiene el marcador -- prueba de que la aserción de abajo FALLARÍA si el
    // marcador apareciera en algún payload real.
    const detector = (bodies: string[]) =>
      bodies.some((b) => b.includes(RAW_MARKER) || b.includes(BARE_MARKER));
    expect(detector([`prefijo ${RAW_MARKER} sufijo`])).toBe(true);
    // Aserción central: NINGÚN payload entregado al cliente en NINGÚN punto del
    // flujo contiene el marcador (ni entero ni desnudo).
    expect(spy.markerHits()).toEqual([]);
    expect(detector(spy.payloads.map((p) => p.body))).toBe(false);
    // Y tampoco quedó en el DOM en la fase final.
    expectNoMarkerInDom("fase 8 -- cierre");
  });
});
