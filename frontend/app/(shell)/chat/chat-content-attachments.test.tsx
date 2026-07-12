import userEvent from "@testing-library/user-event";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createControlledReader, mockSseResponse, sseFrame } from "@/lib/chat/test-support/sse-mock";
import { SessionProvider, type SessionContextValue } from "@/lib/session-context";
import { ChatContent, type ChatContentLabels } from "./chat-content";

/**
 * Test de integración end-to-end del `AttachmentAdapter` del composer
 * (d14-attachments, tarea 8.1, verificación: "subir→procesar→listo funciona
 * end-to-end contra el endpoint", ANEXO §6). Mismo criterio de "E2E" que
 * `e2e-flujo-b/d/g.test.tsx` (sin Playwright: monta `ChatContent` real,
 * maneja como un usuario) pero con un doble de `fetch` PROPIO en vez de
 * `createChatApiDouble` (`lib/chat/test-support/api-double.ts`) -- ese doble
 * todavía no modela `POST /api/attachments`/`GET /api/attachments/{id}`
 * (fuera de su alcance actual, ver `openspec/BACKLOG-DESCUBRIMIENTOS.md`);
 * agregar acá un doble mínimo evita tocar ese fixture compartido por el
 * resto de la suite de d13-chat-conversacion.
 *
 * Cubre la costura completa: adjuntar un archivo desde el composer real
 * (botón "Adjuntar archivo" -> `<input type="file">` oculto) crea la sesión
 * si hace falta, sube, hace polling de `extracting`→`ready`, habilita el
 * envío, y el POST de `POST /sessions/{id}/messages/stream` efectivamente
 * lleva `attachment_ids` con el `attachment_id` real.
 */

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
}));

// Valores REALES de `messages/es.json` (namespace `Chat`), copiados verbatim
// -- mismo criterio que `chat-content.test.tsx`/`e2e-flujo-b.test.tsx`.
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
      unsupportedType:
        "No podemos procesar archivos {extension}. Extraé el archivo que necesitás y subilo directamente.",
      falsifiedType:
        "El contenido del archivo no coincide con su extensión ({extension}). Por seguridad no se puede adjuntar.",
      withMacros:
        'Los archivos con macros ({extension}) no están permitidos. Guardalo desde Excel como "Libro de Excel (.xlsx)" y volvé a subirlo.',
      tooLarge:
        "El archivo supera el límite de {limitMb} MB para {fileType}. Si solo necesitás algunas hojas, copialas a un archivo nuevo.",
      pdfProtected:
        "Este PDF está protegido con contraseña y no se puede leer. Quitale la protección y volvé a subirlo.",
      imageNotSupported:
        "Este agente todavía no puede ver imágenes. Si es una captura de un error, pegá el texto del mensaje directamente en el chat; si es un reporte, exportalo a PDF o Excel.",
      wordLegacy: "El formato .doc (Word 97-2003) no está soportado. Abrilo en Word y guardalo como .docx.",
      tooManyAttachments: "Máximo {limit} archivos por mensaje. Quitá alguno o enviá en dos mensajes.",
      credentialsDetected:
        "Este archivo contiene lo que parece una contraseña o clave de acceso ({detail}). Por política no puede enviarse a la IA. Quitá las credenciales del archivo y volvé a subirlo.",
      piiDetected:
        "Detectamos posibles datos personales en este archivo ({detail}). Recordá la política: solo datos de prueba hacia la IA.",
      embeddedInstruction:
        "Este documento contiene texto que parece dirigido a la IA ({detail}). El agente lo tratará solo como contenido del documento. Revisalo si no lo esperabas.",
      genericError:
        "No pudimos procesar este archivo (puede estar dañado). Probá guardarlo de nuevo desde la aplicación original.",
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

function sessionFor(role: SessionContextValue["user"]["role"]): SessionContextValue {
  return {
    user: { name: "carla", role },
    gateway: { status: "ok" },
    pendingApprovals: 0,
    unreadNotifications: 0,
    capabilities: [],
  };
}

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ChatContent + AttachmentAdapter — subir→procesar→listo, envío con attachment_ids", () => {
  it("adjuntar un archivo llega a listo y el turno enviado incluye su attachment_id", async () => {
    const user = userEvent.setup();
    const streamReader = createControlledReader();
    let statusCalls = 0;
    let capturedStreamBody: { text?: string; attachment_ids?: string[] } | null = null;

    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      const method = (init?.method ?? "GET").toUpperCase();

      if (method === "POST" && url === "/api/sessions") {
        return jsonResponse(201, {
          id: "session-1",
          agent_id: "default_chat",
          model_profile: "deepseek-v4-flash",
          created_at: "2026-07-12T00:00:00.000Z",
        });
      }
      if (method === "GET" && url === "/api/agents/default_chat") {
        return jsonResponse(200, {
          name: "Chat por Defecto",
          starter_prompts: [],
          escalation_enabled: false,
        });
      }
      if (method === "POST" && url === "/api/attachments") {
        return jsonResponse(201, {
          id: "att-1",
          session_id: "session-1",
          status: "uploaded",
          original_name: "reporte.pdf",
          detected_type: "pdf",
          size_bytes: 2048,
          sha256: "deadbeef",
          created_at: "2026-07-12T00:00:00.000Z",
        });
      }
      if (method === "GET" && url === "/api/attachments/att-1") {
        statusCalls += 1;
        const status = statusCalls === 1 ? "extracting" : "ready";
        return jsonResponse(200, {
          id: "att-1",
          status,
          original_name: "reporte.pdf",
          detected_type: "pdf",
          size_bytes: 2048,
          created_at: "2026-07-12T00:00:00.000Z",
          sendable: status === "ready",
          requires_test_data_confirmation: false,
          scan_summary: null,
          inserted: false,
          token_count: status === "ready" ? 500 : null,
          included_percent: status === "ready" ? 100 : null,
          truncated: status === "ready" ? false : null,
        });
      }
      if (method === "POST" && url === "/api/sessions/session-1/messages/stream") {
        capturedStreamBody = init?.body ? JSON.parse(init.body as string) : null;
        return mockSseResponse(streamReader.reader, {
          status: 200,
          headers: { "X-Turn-Id": "turn-1", "X-User-Message-Id": "u1" },
        });
      }
      throw new Error(`fetch inesperado en el doble del test: ${method} ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <SessionProvider value={sessionFor("funcional")}>
        <ChatContent initialSessionId={null} labels={LABELS} />
      </SessionProvider>,
    );

    // Escribe el texto ANTES de adjuntar -- así el único motivo restante de
    // "Enviar" deshabilitado, mientras el adjunto sube/procesa, es el
    // adjunto (gating de la tarea 8.1, `composer.tsx::hasUnsendableAttachment`).
    await user.type(screen.getByLabelText("Mensaje"), "Adjunto el reporte, revisalo por favor");

    const file = new File(["contenido"], "reporte.pdf", { type: "application/pdf" });
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    await user.upload(fileInput, file);

    // Mientras el adjunto sigue en `extracting` (`sendable: false`), el envío
    // queda bloqueado -- nunca se manda "de todos modos" excluyendo el
    // adjunto en silencio (ANEXO §6/§10).
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Enviar" }).hasAttribute("disabled")).toBe(true);
    });

    // El polling llega a `ready`/`sendable: true` -- el envío se habilita solo.
    // `chat-content.tsx` NO override-a `pollIntervalMs` (el default de
    // producción, 1500 ms, aplica también acá) -- timeout generoso para
    // cubrir al menos dos vueltas de polling con margen.
    await waitFor(
      () => {
        expect(screen.getByRole("button", { name: "Enviar" }).hasAttribute("disabled")).toBe(false);
      },
      { timeout: 4000 },
    );

    await user.click(screen.getByRole("button", { name: "Enviar" }));

    await waitFor(() => expect(capturedStreamBody).not.toBeNull());
    expect(capturedStreamBody).toEqual({
      text: "Adjunto el reporte, revisalo por favor",
      attachment_ids: ["att-1"],
    });

    // Cierra el turno (evita dejar la promesa de streaming colgada entre tests).
    streamReader.push(
      sseFrame(1, "done", {
        turn_id: "turn-1",
        user_message_id: "u1",
        assistant_message_id: "a1",
        reprocessed_count: 0,
        stopped: false,
        is_alternate_model: false,
        compacted: false,
        escalation: null,
      }),
    );
    streamReader.close();
    await waitFor(() => expect(screen.queryByTestId("stream-cursor")).toBeNull());
  });
});
