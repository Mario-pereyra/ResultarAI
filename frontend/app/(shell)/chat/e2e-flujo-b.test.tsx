import userEvent from "@testing-library/user-event";
import { render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { formatCompactNumberBO, formatLlmCostBO } from "@/lib/format-bo";
import { createChatApiDouble } from "@/lib/chat/test-support/api-double";
import { SessionProvider, type SessionContextValue } from "@/lib/session-context";
import { ChatContent, type ChatContentLabels } from "./chat-content";

/**
 * Test E2E del Flujo B (`design/FLUJOS.md`, sin la parte de citas -- ese
 * subconjunto es `c07-citas-evidencia`, fuera de `d13-chat-conversacion`),
 * tarea 9.1: un turno con streaming, indicador de actividad, feedback 👍/👎
 * con comentario y el turno visible en la capa de telemetría Técnico/Admin.
 *
 * "E2E" acá (sin Playwright/browser-runner en el repo, ver
 * `openspec/changes/d13-chat-conversacion/design.md`) es un test de
 * INTEGRACIÓN de flujo completo a nivel de UI: monta la página real
 * (`ChatContent`, el mismo componente que `chat/nueva/page.tsx` renderiza)
 * con sus labels reales de `messages/es.json` (copiados verbatim del
 * namespace `Chat`, mismo patrón que `chat-content.test.tsx` -- no hay forma
 * sincrónica de resolver `getTranslations()` de `next-intl`, que es
 * server-only, dentro de Vitest/jsdom), y la maneja como un usuario
 * (`@testing-library/user-event`: tipear, Enter, votar) contra
 * `createChatApiDouble` (`lib/chat/test-support/api-double.ts`), el doble de
 * alta fidelidad del contrato HTTP/SSE documentado en
 * `resultarai/app/api/chat.py`/`chat_stream.py`. El lado backend del flujo
 * (persistencia, telemetría por rol, feedback en Langfuse) ya está cubierto
 * por `tests/app/chat/*.py`; este test verifica la COSTURA del lado del
 * cliente contra ese mismo contrato.
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

// Valores REALES de `messages/es.json` (namespace `Chat`), copiados
// verbatim -- mismo criterio que `chat-content.test.tsx` (que ya prueba este
// mismo componente): `buildChatLabels` normalmente los resuelve vía
// `getTranslations()` de next-intl, server-only y por lo tanto no invocable
// sincrónicamente en un test de Vitest/jsdom, así que se copian tal cual
// aparecen en el catálogo en vez de inventar redacción nueva.
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

afterEach(() => {
  vi.unstubAllGlobals();
  pushMock.mockClear();
  replaceMock.mockClear();
});

describe("Flujo B — consulta con streaming, telemetría T/A y feedback (tarea 9.1)", () => {
  it("recorre el flujo completo: turno en streaming, telemetría/taxímetro y feedback 👍→👎 sin duplicar mensajes", async () => {
    const user = userEvent.setup();
    const double = createChatApiDouble({ role: "tecnico", escalationEnabled: true });
    vi.stubGlobal("fetch", double.fetch);

    render(
      <SessionProvider value={sessionFor("tecnico")}>
        <ChatContent initialSessionId={null} labels={LABELS} />
      </SessionProvider>,
    );

    // --- Paso 1 (Flujo B, punto 1): el usuario pregunta en el chat -------
    const question = "¿Qué parámetro controla la numeración de facturas en Bolivia?";
    const textarea = await screen.findByLabelText(LABELS.composer.textareaLabel);
    await user.type(textarea, question);
    await user.keyboard("{Enter}");

    // Enter creó la sesión y arrancó el stream: el doble ya tiene un turno
    // en curso para gobernar a mano.
    await waitFor(() => expect(double.currentTurn).not.toBeNull());
    const turn = double.currentTurn!;
    expect(double.getSessions()).toHaveLength(1);
    expect(turn.sessionId).toBe(double.getSessions()[0].id);

    // El eco del mensaje del usuario ya está en el hilo.
    expect(await screen.findByText(question)).toBeTruthy();

    // --- Paso 2 (Flujo B, punto 2): streaming con indicador de actividad -
    // Indicador de actividad visible ANTES de cualquier fragmento (todavía
    // no se empujó ninguno) -- sin cursor de streaming todavía, porque el
    // cursor pertenece al TEXTO en curso, que no existe aún.
    expect(await screen.findByText(LABELS.activity.consulting)).toBeTruthy();
    expect(screen.queryByTestId("stream-cursor")).toBeNull();

    // Primer fragmento: la actividad plegada da paso al texto en streaming,
    // con el cursor de bloque parpadeante.
    turn.pushFragment("La numeración de facturas se controla con el parámetro ");
    await waitFor(() => expect(screen.queryByText(LABELS.activity.consulting)).toBeNull());
    expect(screen.getByTestId("stream-cursor")).toBeTruthy();
    expect(screen.getByText(/La numeración de facturas se controla/)).toBeTruthy();

    // Fragmentos siguientes con markdown: se renderizan INCREMENTALMENTE
    // (antes del `done`), no solo al final -- el `**...**` ya es <strong>
    // real, no texto crudo con asteriscos.
    turn.pushFragment("**MV_NFISFAT** (tabla SX6) del ambiente de Bolivia.");
    await waitFor(() => expect(document.querySelector("strong")?.textContent).toBe("MV_NFISFAT"));
    // El cursor sigue presente: el turno todavía está en curso.
    expect(screen.getByTestId("stream-cursor")).toBeTruthy();

    // Cierra el turno (tarea 4.1: rol técnico -> `telemetry` presente, sin
    // `trace_id`, ver `layer_turn_metadata`).
    const turnTelemetry = {
      cost_usd: 0.015,
      latency_ms: 2300,
      cache_hit_tokens: 12000,
      cache_miss_tokens: 500,
    };
    const { assistantMessageId } = turn.complete({ telemetry: turnTelemetry });

    // Al `done`: el cursor desaparece -- el turno ya no está en curso.
    await waitFor(() => expect(screen.queryByTestId("stream-cursor")).toBeNull());
    // El cursor desaparece un tick ANTES de que `chat-content.tsx` pliegue el
    // turno dentro del historial persistido (efecto separado que corre en un
    // commit posterior): esperar solo el cursor no garantiza todavía que la
    // fila de telemetría/feedback -- que solo existen en el mensaje YA
    // plegado, nunca en el bloque `StreamingMessageRow` -- esté montada. Se
    // usa la acción de feedback (siempre presente en un mensaje `assistant`
    // plegado, tarea 3.6) como señal inequívoca de que el pliegue terminó.
    await screen.findByRole("button", { name: LABELS.feedback.like });
    // El texto final completo sigue visible tras el cierre.
    expect(screen.getByText(/del ambiente de Bolivia\./)).toBeTruthy();

    // --- Paso 3 (Flujo B, punto 7): telemetría T/A + taxímetro acumulado -
    const expectedCost = formatLlmCostBO(turnTelemetry.cost_usd); // "USD 0,0150"
    const expectedHitChip = `${LABELS.telemetry.cacheHit} · ${formatCompactNumberBO(turnTelemetry.cache_hit_tokens)}`;
    const expectedMissChip = `${LABELS.telemetry.cacheMiss} · ${formatCompactNumberBO(turnTelemetry.cache_miss_tokens)}`;

    // Fila de telemetría del turno (costo + chips de cache).
    expect(screen.getByText(expectedHitChip)).toBeTruthy();
    expect(screen.getByText(expectedMissChip)).toBeTruthy();
    // "ver traza" está AUSENTE para Técnico (tarea 4.3 -- solo Admin).
    expect(screen.queryByText(LABELS.telemetry.viewTrace)).toBeNull();

    // Taxímetro del header: visible para Técnico (tarea 4.2) y acumula el
    // costo de este turno -- con un único turno, el total ES el costo del
    // turno (mismo costo aparece dos veces: fila del turno + taxímetro).
    const taximeterStatus = screen.getByRole("status", { name: /Costo de sesión/ });
    expect(taximeterStatus).toBeTruthy();
    expect(screen.getAllByText(expectedCost)).toHaveLength(2);

    // --- Paso 4 (Flujo B, punto 6): feedback 👍 con comentario ------------
    // El popover comparte el texto "Enviar" con el botón del composer (el
    // hint/disponibilidad no lo distingue por accesibilidad), así que se
    // busca DENTRO del popover -- mismo criterio que un usuario que hace
    // click adentro del popover recién abierto, no en el composer de atrás.
    function feedbackPopover(): HTMLElement {
      return screen.getByText(LABELS.feedback.prompt).closest(".msg-feedback__popover") as HTMLElement;
    }

    await user.click(screen.getByRole("button", { name: LABELS.feedback.like }));
    const comment = "Justo la respuesta que necesitaba, gracias.";
    await user.type(screen.getByLabelText(LABELS.feedback.commentLabel), comment);
    await user.click(within(feedbackPopover()).getByRole("button", { name: LABELS.feedback.send }));

    await waitFor(() => expect(double.getVotes()).toHaveLength(1));
    const [firstVote] = double.getVotes();
    expect(firstVote).toEqual({
      messageId: assistantMessageId,
      vote: "up",
      comment,
      traceId: firstVote.traceId,
    });
    expect(firstVote.traceId).toBeTruthy();

    // Cambiar a 👎: el doble registra el REEMPLAZO (nueva llamada, append-only
    // del lado de Langfuse -- ver `use_cases/chat/feedback.py`), esta vez sin
    // comentario ("Omitir").
    await user.click(screen.getByRole("button", { name: LABELS.feedback.dislike }));
    await user.click(within(feedbackPopover()).getByRole("button", { name: LABELS.feedback.skip }));

    await waitFor(() => expect(double.getVotes()).toHaveLength(2));
    const [, secondVote] = double.getVotes();
    expect(secondVote.messageId).toBe(assistantMessageId);
    expect(secondVote.vote).toBe("down");
    expect(secondVote.comment).toBeNull();
    // El voto vigente (el último) reemplazó al anterior; ambos quedan
    // registrados (append-only), nunca se muta el primero.
    expect(firstVote.vote).toBe("up");

    // --- Paso 5: estado final del doble -- sin duplicados -----------------
    const persisted = double.getMessages();
    expect(persisted).toHaveLength(2);
    const userMessages = persisted.filter((message) => message.role === "user");
    const assistantMessages = persisted.filter((message) => message.role === "assistant");
    expect(userMessages).toHaveLength(1);
    expect(assistantMessages).toHaveLength(1);
    expect(userMessages[0].content).toBe(question);
    expect(assistantMessages[0].id).toBe(assistantMessageId);
    expect(assistantMessages[0].content).toBe(
      "La numeración de facturas se controla con el parámetro **MV_NFISFAT** (tabla SX6) del ambiente de Bolivia.",
    );
    expect(assistantMessages[0].parentId).toBe(userMessages[0].id);

    // El eco del mensaje del usuario aparece UNA sola vez en el DOM (nunca se
    // reenvía/duplica al cerrar el turno).
    expect(screen.getAllByText(question)).toHaveLength(1);
  });
});
