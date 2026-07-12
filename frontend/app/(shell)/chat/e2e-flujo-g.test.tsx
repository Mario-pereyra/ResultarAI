import userEvent from "@testing-library/user-event";
import { render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createChatApiDouble, type PersistedMessage } from "@/lib/chat/test-support/api-double";
import { SessionProvider, type SessionContextValue } from "@/lib/session-context";
import { ChatContent, type ChatContentLabels } from "./chat-content";

/**
 * Test E2E del Flujo G (`design/FLUJOS.md` §"Edición de mensaje → rama nueva",
 * `design/VISTAS/02-chat.md` vista 09), tarea 9.2 de `d13-chat-conversacion`:
 * editar un mensaje INTERMEDIO crea una RAMA nueva (append-only, nunca se
 * reescribe la historia), aparece el selector de versiones "N/M" junto al
 * mensaje editado, y alternar entre ramas conserva las respuestas posteriores
 * de cada una intactas. La aserción CENTRAL de la tarea es el invariante
 * append-only: al terminar, todos los mensajes originales existen byte a byte
 * idénticos a los sembrados (mismo id/parent_id/content/created_at), los
 * únicos mensajes nuevos son el mensaje editado (hermano del original, mismo
 * parent_id) y su respuesta -- ningún DELETE, ningún UPDATE.
 *
 * "E2E" acá (sin Playwright/browser-runner en el repo, ver
 * `openspec/changes/d13-chat-conversacion/design.md`) es un test de
 * INTEGRACIÓN de flujo completo a nivel de UI, igual que `e2e-flujo-b.test.tsx`:
 * monta la página real (`ChatContent`) con sus labels reales de
 * `messages/es.json` (copiados verbatim del namespace `Chat` -- `buildChatLabels`
 * los resuelve vía `getTranslations()` de next-intl, server-only y por lo tanto
 * no invocable sincrónicamente en Vitest/jsdom, mismo criterio que
 * `chat-content.test.tsx`/`e2e-flujo-b.test.tsx`), y la maneja como un usuario
 * (`@testing-library/user-event`) contra `createChatApiDouble`
 * (`lib/chat/test-support/api-double.ts`), el doble de alta fidelidad del
 * contrato HTTP/SSE de `resultarai/app/api/chat.py`/`chat_stream.py`, que hace
 * branching REAL por `edits_message_id` (mismo `parent_id` que el mensaje
 * editado). El lado backend del branching (persistencia append-only, conteo de
 * descendientes activos) ya está cubierto por `tests/app/chat/*.py`; este test
 * verifica la costura del cliente contra ese contrato.
 *
 * ## Rol elegido: Funcional
 *
 * El invariante append-only y el modelo de ramas son INDEPENDIENTES del rol
 * (la capa de telemetría por rol -- `layer_turn_metadata` -- solo cambia qué
 * metadatos se muestran, nunca la topología del árbol). Se elige Funcional
 * porque deja el DOM libre del taxímetro y las filas de telemetría
 * (Técnico/Admin), de modo que las aserciones sobre el CONTENIDO EXACTO de
 * cada rama al alternar quedan sin ambigüedad. La capa por rol ya se ejercita
 * en `e2e-flujo-b.test.tsx` (Técnico) y `chat-content.test.tsx` (Admin/Técnico).
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
// `buildChatLabels` normalmente los resuelve vía `getTranslations()` de
// next-intl (server-only, no invocable sincrónicamente en Vitest/jsdom), así
// que se copian tal cual aparecen en el catálogo en vez de inventar redacción.
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

// --- Conversación lineal sembrada (3 intercambios = 6 mensajes) ------------
// u1 ── a1 ── u2 ── a2 ── u3 ── a3   (active_leaf = a3)
// Se edita el mensaje INTERMEDIO u2. Textos elegidos sin colisión de
// substrings ("dólares" vs "euros") para que `queryByText` distinga una rama
// de la otra sin falsos positivos.
const SESSION_ID = "session-g";
const U1 = "¿Cómo configuro el tipo de cambio de la moneda extranjera?";
const A1 = "Entrá a Parámetros → Monedas y definí la cotización diaria.";
const U2 = "¿Y para las facturas emitidas en dólares?";
const A2 = "Para las facturas en dólares se toma la cotización del día de emisión.";
const U3 = "Perfecto. ¿Qué reporte muestra el detalle por moneda?";
const A3 = "El reporte de ventas por moneda, filtrando por USD.";
// Texto corregido de la edición y respuesta de la rama nueva.
const U2_EDIT = "¿Y para las facturas emitidas en euros?";
const A2_NEW = "Para las facturas en euros se aplica la cotización del BCB del día.";

const ORIGINAL_IDS = ["u1", "a1", "u2", "a2", "u3", "a3"] as const;

// jsdom no implementa `scrollIntoView` (lo usa el anclaje de scroll al
// alternar de versión, `chat-content.tsx`); se stubbea con un no-op para no
// depender de la versión de jsdom (el componente ya lo guarda con
// `typeof … === "function"`, pero esto mantiene la consola limpia).
const originalScrollIntoView = Element.prototype.scrollIntoView;

beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  Element.prototype.scrollIntoView = originalScrollIntoView;
  vi.unstubAllGlobals();
  pushMock.mockClear();
  replaceMock.mockClear();
});

/** Siembra la conversación lineal de 3 intercambios en el doble y fija la
 * hoja activa en la última respuesta (a3). */
function seedLinearConversation(double: ReturnType<typeof createChatApiDouble>) {
  double.seedSession({ id: SESSION_ID });
  double.seedMessage({ id: "u1", sessionId: SESSION_ID, parentId: null, role: "user", content: U1 });
  double.seedMessage({ id: "a1", sessionId: SESSION_ID, parentId: "u1", role: "assistant", content: A1 });
  double.seedMessage({ id: "u2", sessionId: SESSION_ID, parentId: "a1", role: "user", content: U2 });
  double.seedMessage({ id: "a2", sessionId: SESSION_ID, parentId: "u2", role: "assistant", content: A2 });
  double.seedMessage({ id: "u3", sessionId: SESSION_ID, parentId: "a2", role: "user", content: U3 });
  double.seedMessage({ id: "a3", sessionId: SESSION_ID, parentId: "u3", role: "assistant", content: A3 });
  double.setActiveLeaf(SESSION_ID, "a3");
}

describe("Flujo G — edición de un mensaje intermedio → rama nueva (tarea 9.2)", () => {
  it("editar u2 crea una rama, aparece el selector 1/2·2/2, alternar conserva ambas ramas y respeta el invariante append-only", async () => {
    const user = userEvent.setup();
    const double = createChatApiDouble({ role: "funcional", escalationEnabled: true });
    seedLinearConversation(double);
    vi.stubGlobal("fetch", double.fetch);

    // Copia PROFUNDA de los 6 mensajes sembrados ANTES de editar: es el patrón
    // de referencia contra el que se prueba, al final, que ninguno se tocó.
    const seededSnapshot: PersistedMessage[] = JSON.parse(
      JSON.stringify(double.getMessages(SESSION_ID)),
    );
    expect(seededSnapshot).toHaveLength(6);

    render(
      <SessionProvider value={sessionFor("funcional")}>
        <ChatContent initialSessionId={SESSION_ID} labels={LABELS} />
      </SessionProvider>,
    );

    // --- Paso 1 (Flujo G, punto 1): la conversación lineal carga completa ---
    // La rama activa (única, lineal) muestra los 6 mensajes en orden.
    await screen.findByText(A3);
    for (const text of [U1, A1, U2, A2, U3]) {
      expect(screen.getByText(text)).toBeTruthy();
    }

    // Sin ediciones todavía, NINGÚN mensaje tiene versiones hermanas: no hay
    // selector de versiones en el DOM.
    expect(screen.queryByTestId("version-selector")).toBeNull();

    // --- Paso 2 (Flujo G, puntos 2-4): editar el mensaje intermedio u2 ------
    // El botón "Editar" del mensaje u2 (anclado en su fila `data-message-id`).
    const u2Row = document.querySelector('[data-message-id="u2"]') as HTMLElement;
    expect(u2Row).not.toBeNull();
    await user.click(within(u2Row).getByRole("button", { name: LABELS.messageEdit.action }));

    // La burbuja de u2 MUTA a un textarea PRECARGADO con el texto ORIGINAL
    // (append-only visible desde la UI: se parte del texto real, no de vacío).
    const editTextarea = screen.getByLabelText(LABELS.messageEdit.textareaLabel) as HTMLTextAreaElement;
    expect(editTextarea.value).toBe(U2);

    // Aviso "reprocesa N mensajes": N = posteriores a u2 en su rama = a2,u3,a3
    // = 3 (≥ 3 -> el aviso DEBE aparecer). Es SOLO informativo: no bloquea
    // "Crear rama".
    expect(screen.getByText("Crear una rama acá reprocesa 3 mensajes")).toBeTruthy();
    const confirmBtn = screen.getByRole("button", { name: LABELS.messageEdit.confirm }) as HTMLButtonElement;
    expect(confirmBtn.disabled).toBe(false);

    // El usuario corrige el texto y confirma la creación de la rama.
    await user.clear(editTextarea);
    await user.type(editTextarea, U2_EDIT);
    await user.click(screen.getByRole("button", { name: LABELS.messageEdit.confirm }));

    // El doble arrancó el turno de la rama nueva (branching real por
    // `edits_message_id`): se gobierna a mano y se cierra con la respuesta.
    await waitFor(() => expect(double.currentTurn).not.toBeNull());
    double.currentTurn!.completeWithText(A2_NEW);

    // --- Paso 3 (Flujo G, punto 5): el selector "2/2" aparece en u2' --------
    // Al cerrar el turno de edición, `chat-content.tsx` recarga la sesión: la
    // rama nueva (activa) queda visible con el selector "2/2" en el mensaje
    // editado. Esperar "2/2" es la señal inequívoca de que la recarga terminó
    // (durante el streaming el árbol todavía no tenía el hermano nuevo).
    await screen.findByText("2/2");
    expect(screen.getByRole("group", { name: "versión 2 de 2" })).toBeTruthy();

    // La rama nueva se muestra COMPLETA y EXACTA; la rama vieja no se mezcla.
    expect(screen.getByText(U2_EDIT)).toBeTruthy();
    expect(screen.getByText(A2_NEW)).toBeTruthy();
    expect(screen.queryByText(U2)).toBeNull();
    expect(screen.queryByText(A2)).toBeNull();
    expect(screen.queryByText(U3)).toBeNull();
    expect(screen.queryByText(A3)).toBeNull();
    // El prefijo común a ambas ramas (u1, a1) sigue visible.
    expect(screen.getByText(U1)).toBeTruthy();
    expect(screen.getByText(A1)).toBeTruthy();

    // En "2/2" (rama más nueva) la flecha ‹ (anterior) está habilitada y la
    // › (siguiente) deshabilitada -- estamos en el extremo más reciente.
    expect((screen.getByRole("button", { name: LABELS.versionSelector.previousVersion }) as HTMLButtonElement).disabled).toBe(false);
    expect((screen.getByRole("button", { name: LABELS.versionSelector.nextVersion }) as HTMLButtonElement).disabled).toBe(true);

    // --- Paso 4 (Flujo G, punto 6): alternar dos veces (2/2 → 1/2 → 2/2) ----
    // Toggle 1: 2/2 → 1/2 (flecha ‹). Vuelve la rama VIEJA con sus respuestas
    // posteriores EXACTAS (a2, u3, a3); la rama nueva desaparece del DOM (queda
    // intacta en memoria, recuperable).
    await user.click(screen.getByRole("button", { name: LABELS.versionSelector.previousVersion }));
    await screen.findByText("1/2");
    expect(screen.getByRole("group", { name: "versión 1 de 2" })).toBeTruthy();
    expect(screen.getByText(U2)).toBeTruthy();
    expect(screen.getByText(A2)).toBeTruthy();
    expect(screen.getByText(U3)).toBeTruthy();
    expect(screen.getByText(A3)).toBeTruthy();
    expect(screen.queryByText(U2_EDIT)).toBeNull();
    expect(screen.queryByText(A2_NEW)).toBeNull();
    // En "1/2" (rama más vieja) la flecha ‹ está deshabilitada y la › habilitada.
    expect((screen.getByRole("button", { name: LABELS.versionSelector.previousVersion }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: LABELS.versionSelector.nextVersion }) as HTMLButtonElement).disabled).toBe(false);

    // Toggle 2: 1/2 → 2/2 (flecha ›). Vuelve la rama NUEVA con su contenido
    // EXACTO; la rama vieja no quedó mezclada.
    await user.click(screen.getByRole("button", { name: LABELS.versionSelector.nextVersion }));
    await screen.findByText("2/2");
    expect(screen.getByText(U2_EDIT)).toBeTruthy();
    expect(screen.getByText(A2_NEW)).toBeTruthy();
    expect(screen.queryByText(U2)).toBeNull();
    expect(screen.queryByText(A2)).toBeNull();
    expect(screen.queryByText(U3)).toBeNull();
    expect(screen.queryByText(A3)).toBeNull();

    // --- Paso 5 (aserción CENTRAL): invariante append-only ------------------
    const after = double.getMessages(SESSION_ID);

    // (a) TODOS los mensajes originales existen byte a byte idénticos a los
    //     sembrados: mismo id, parent_id, content, created_at, role, status.
    //     Ningún UPDATE (mutación) ni DELETE (los 6 siguen presentes).
    for (const id of ORIGINAL_IDS) {
      const seeded = seededSnapshot.find((message) => message.id === id);
      const current = after.find((message) => message.id === id);
      expect(current).toEqual(seeded);
    }

    // (b) Los ÚNICOS mensajes nuevos son el mensaje editado (u2') y su
    //     respuesta (a2'): exactamente 2 más que los 6 originales.
    const newMessages = after.filter(
      (message) => !ORIGINAL_IDS.includes(message.id as (typeof ORIGINAL_IDS)[number]),
    );
    expect(newMessages).toHaveLength(2);
    expect(after).toHaveLength(8);

    // (c) u2' es HERMANO de u2: mismo parent_id (a1) -- la edición ramifica,
    //     no reescribe. Su contenido es el texto corregido.
    const editedUser = newMessages.find((message) => message.role === "user");
    expect(editedUser).toBeDefined();
    expect(editedUser!.parentId).toBe("a1");
    expect(editedUser!.parentId).toBe(seededSnapshot.find((m) => m.id === "u2")!.parentId);
    expect(editedUser!.content).toBe(U2_EDIT);
    // u2' es un mensaje DISTINTO del original u2 (no lo pisó).
    expect(editedUser!.id).not.toBe("u2");

    // (d) a2' cuelga de u2' (la respuesta de la rama nueva), con el texto
    //     transmitido por el turno.
    const branchReply = newMessages.find((message) => message.role === "assistant");
    expect(branchReply).toBeDefined();
    expect(branchReply!.parentId).toBe(editedUser!.id);
    expect(branchReply!.content).toBe(A2_NEW);

    // --- Paso 6 (fidelidad al criterio): el resto del estado no cambió ------
    // Editar NO forkeó una sesión nueva (contraste con la escalación): sigue
    // habiendo una sola sesión, con su misma identidad/configuración; el
    // título permanece nulo. La hoja activa sí se movió a la rama nueva (a2'),
    // que es el comportamiento correcto, no una mutación de lo sembrado.
    const sessions = double.getSessions();
    expect(sessions).toHaveLength(1);
    expect(sessions[0].id).toBe(SESSION_ID);
    expect(sessions[0].agentId).toBe("default_chat");
    expect(sessions[0].forkedFromId).toBeNull();
    expect(sessions[0].activeLeafId).toBe(branchReply!.id);
  });
});
