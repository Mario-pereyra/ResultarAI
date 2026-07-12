import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  DEFAULT_MAX_ATTACHMENTS_PER_MESSAGE,
  useAttachmentAdapter,
  type AttachmentAdapterLabels,
} from "./attachment-adapter";

/**
 * Tests del `AttachmentAdapter` del composer (d14-attachments, tarea 8.1).
 * Cubre lo pedido por la verificación de la tarea: subir → polling → listo,
 * error de subida tipado (texto §10 exacto, incluido el escenario "Imagen
 * rechazada con alternativa accionable" de `attachments-ui`) y que `send()`
 * (`attachmentIdsForSend`) devuelve el `attachment_id`. Suma además la
 * validación client-side de "demasiados adjuntos", `remove()` cortando el
 * polling, y el mapeo de los estados terminales `blocked` (N3)/`ready` con
 * advertencia (N2) -- mismo contrato que `GET /api/attachments/{id}`
 * documentado en `resultarai/app/api/attachments.py`.
 *
 * `pollIntervalMs: 0` en todos los tests (mismo patrón que
 * `reconnectDelayMs: 0` de `use-turn-stream.test.ts`): temporizadores reales
 * de 0 ms + `waitFor` de Testing Library, sin depender de fake timers.
 */

// Valores REALES de `messages/es.json` → `Chat.attachments.errors`/`fileTypes`
// (mismo criterio que `chat-content.test.tsx`: copiados verbatim en vez de
// inventar redacción nueva).
const LABELS: AttachmentAdapterLabels = {
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
  // Valores reales de `Chat.attachments.piiEntityLabels` (tarea 8.2): etiquetas
  // amigables por `entity_type` de Presidio (`_PII_ENTITIES`, `data_scan.py`).
  piiEntityLabels: {
    EMAIL_ADDRESS: { one: "email", other: "emails" },
    PHONE_NUMBER: { one: "número de teléfono", other: "números de teléfono" },
    BO_PHONE: { one: "número de teléfono", other: "números de teléfono" },
    PERSON: { one: "nombre de persona", other: "nombres de persona" },
    BO_CI: { one: "número de carnet", other: "números de carnet" },
    BO_NIT: { one: "NIT", other: "NIT" },
  },
};

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function makeFile(name = "reporte.pdf"): File {
  return new File(["contenido"], name, { type: "application/pdf" });
}

function urlOf(input: RequestInfo | URL): string {
  return typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
}

/** Espejo mínimo de `AttachmentResponse` (`POST /api/attachments`, 201). */
function createdPayload(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: "att-1",
    session_id: "session-1",
    status: "uploaded",
    original_name: "reporte.pdf",
    detected_type: "pdf",
    size_bytes: 1024,
    sha256: "deadbeef",
    created_at: "2026-07-12T00:00:00.000Z",
    ...overrides,
  };
}

/** Espejo mínimo de `AttachmentStatusResponse` (`GET /api/attachments/{id}`). */
function statusPayload(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: "att-1",
    status: "extracting",
    original_name: "reporte.pdf",
    detected_type: "pdf",
    size_bytes: 1024,
    created_at: "2026-07-12T00:00:00.000Z",
    sendable: false,
    requires_test_data_confirmation: false,
    scan_summary: null,
    inserted: false,
    token_count: null,
    included_percent: null,
    truncated: null,
    ...overrides,
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useAttachmentAdapter — subir → polling → listo", () => {
  it("add() sube, hace polling de extracting→ready y queda sendable", async () => {
    const ensureSession = vi.fn().mockResolvedValue("session-1");
    let statusCalls = 0;
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = urlOf(input);
      if (init?.method === "POST" && url === "/api/attachments") {
        return jsonResponse(201, createdPayload());
      }
      if (url === "/api/attachments/att-1") {
        statusCalls += 1;
        if (statusCalls === 1) return jsonResponse(200, statusPayload({ status: "extracting" }));
        return jsonResponse(
          200,
          statusPayload({
            status: "ready",
            sendable: true,
            token_count: 8200,
            included_percent: 100,
            truncated: false,
          }),
        );
      }
      throw new Error(`fetch inesperado: ${init?.method ?? "GET"} ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() =>
      useAttachmentAdapter({ ensureSession, labels: LABELS, pollIntervalMs: 0 }),
    );

    await act(async () => {
      await result.current.add(makeFile());
    });

    // Justo tras `add()`: la subida ya resolvió (id real asignado), el
    // primer poll puede seguir en vuelo -- `waitFor` espera el estado
    // terminal sin acoplarse a temporizadores reales.
    expect(result.current.attachments[0].attachmentId).toBe("att-1");

    await waitFor(() => {
      expect(result.current.attachments[0].status).toBe("ready");
    });
    expect(result.current.attachments[0].sendable).toBe(true);
    expect(result.current.attachments[0].tokenCount).toBe(8200);
    expect(result.current.attachments[0].message).toBeNull();
    expect(statusCalls).toBeGreaterThanOrEqual(2);
  });

  it("send(): attachmentIdsForSend() devuelve el attachment_id una vez sendable", async () => {
    const ensureSession = vi.fn().mockResolvedValue("session-1");
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = urlOf(input);
      if (init?.method === "POST" && url === "/api/attachments") return jsonResponse(201, createdPayload());
      if (url === "/api/attachments/att-1") {
        return jsonResponse(200, statusPayload({ status: "ready", sendable: true }));
      }
      throw new Error(`fetch inesperado: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() =>
      useAttachmentAdapter({ ensureSession, labels: LABELS, pollIntervalMs: 0 }),
    );

    expect(result.current.attachmentIdsForSend()).toEqual([]);

    await act(async () => {
      await result.current.add(makeFile());
    });
    await waitFor(() => expect(result.current.attachments[0].status).toBe("ready"));

    expect(result.current.attachmentIdsForSend()).toEqual(["att-1"]);
  });

  it("send(): un adjunto blocked/no-sendable queda EXCLUIDO de attachmentIdsForSend()", async () => {
    const ensureSession = vi.fn().mockResolvedValue("session-1");
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = urlOf(input);
      if (init?.method === "POST" && url === "/api/attachments") return jsonResponse(201, createdPayload());
      if (url === "/api/attachments/att-1") {
        return jsonResponse(
          200,
          statusPayload({
            status: "blocked",
            sendable: false,
            scan_summary: { n3_findings: [{ secret_type: "password", line: 23, redacted: "Password=***" }] },
          }),
        );
      }
      throw new Error(`fetch inesperado: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() =>
      useAttachmentAdapter({ ensureSession, labels: LABELS, pollIntervalMs: 0 }),
    );

    await act(async () => {
      await result.current.add(makeFile("conexiones_prod.txt"));
    });
    await waitFor(() => expect(result.current.attachments[0].status).toBe("blocked"));

    expect(result.current.attachmentIdsForSend()).toEqual([]);
    expect(result.current.attachments[0].message).toBe(
      'Este archivo contiene lo que parece una contraseña o clave de acceso ("Password=***" en la línea 23). Por política no puede enviarse a la IA. Quitá las credenciales del archivo y volvé a subirlo.',
    );
  });
});

describe("useAttachmentAdapter — error de subida tipado (texto §10)", () => {
  it("422 macros_not_allowed resuelve al texto §10 exacto, sin arrancar polling", async () => {
    const ensureSession = vi.fn().mockResolvedValue("session-1");
    const fetchMock = vi.fn(async () =>
      jsonResponse(422, { detail: { error_code: "macros_not_allowed", params: { extension: ".xlsm" } } }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() =>
      useAttachmentAdapter({ ensureSession, labels: LABELS, pollIntervalMs: 0 }),
    );

    await act(async () => {
      await result.current.add(makeFile("plan.xlsm"));
    });

    expect(result.current.attachments[0].status).toBe("error");
    expect(result.current.attachments[0].message).toBe(
      'Los archivos con macros (.xlsm) no están permitidos. Guardalo desde Excel como "Libro de Excel (.xlsx)" y volvé a subirlo.',
    );
    // Solo el POST -- ningún GET de polling para un adjunto que nunca se persistió.
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('escenario "Imagen rechazada con alternativa accionable": 422 image_not_supported resuelve al texto §10 "Imagen (V1)", sin arrancar polling', async () => {
    const ensureSession = vi.fn().mockResolvedValue("session-1");
    const fetchMock = vi.fn(async () =>
      jsonResponse(422, { detail: { error_code: "image_not_supported", params: { extension: ".png" } } }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() =>
      useAttachmentAdapter({ ensureSession, labels: LABELS, pollIntervalMs: 0 }),
    );

    await act(async () => {
      await result.current.add(makeFile("captura.png"));
    });

    expect(result.current.attachments[0].status).toBe("error");
    expect(result.current.attachments[0].message).toBe(
      "Este agente todavía no puede ver imágenes. Si es una captura de un error, pegá el texto del mensaje directamente en el chat; si es un reporte, exportalo a PDF o Excel.",
    );
    // La subida se rechaza sin aceptarla: solo el POST, ningún GET de polling.
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("422 too_large interpola {limitMb} y {fileType} (excel)", async () => {
    const ensureSession = vi.fn().mockResolvedValue("session-1");
    const fetchMock = vi.fn(async () =>
      jsonResponse(422, {
        detail: { error_code: "too_large", params: { limit_mb: 20, limit_bytes: 20_971_520, type_group: "excel" } },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() =>
      useAttachmentAdapter({ ensureSession, labels: LABELS, pollIntervalMs: 0 }),
    );

    await act(async () => {
      await result.current.add(makeFile("ventas_anual_completo.xlsx"));
    });

    expect(result.current.attachments[0].message).toBe(
      "El archivo supera el límite de 20 MB para Excel. Si solo necesitás algunas hojas, copialas a un archivo nuevo.",
    );
  });

  it("demasiados adjuntos (client-side): rechaza sin llamar a fetch, con el texto §10", async () => {
    const ensureSession = vi.fn(() => new Promise<string | null>(() => {})); // nunca resuelve
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() =>
      useAttachmentAdapter({ ensureSession, labels: LABELS, maxAttachments: 1, pollIntervalMs: 0 }),
    );

    act(() => {
      void result.current.add(makeFile("uno.pdf"));
    });
    await waitFor(() => expect(result.current.attachments).toHaveLength(1));

    await act(async () => {
      await result.current.add(makeFile("dos.pdf"));
    });

    expect(result.current.attachments).toHaveLength(2);
    expect(result.current.attachments[1].status).toBe("error");
    expect(result.current.attachments[1].message).toBe(
      "Máximo 1 archivos por mensaje. Quitá alguno o enviá en dos mensajes.",
    );
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("DEFAULT_MAX_ATTACHMENTS_PER_MESSAGE es 5 (espejo de AttachmentsConfig por default)", () => {
    expect(DEFAULT_MAX_ATTACHMENTS_PER_MESSAGE).toBe(5);
  });
});

describe("useAttachmentAdapter — remove() corta el polling en curso", () => {
  it("un adjunto removido deja de aparecer y no vuelve a poblarse por un poll tardío", async () => {
    const ensureSession = vi.fn().mockResolvedValue("session-1");
    let resolveGet: ((response: Response) => void) | null = null;
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = urlOf(input);
      if (init?.method === "POST" && url === "/api/attachments") return jsonResponse(201, createdPayload());
      if (url === "/api/attachments/att-1") {
        return new Promise<Response>((resolve) => {
          resolveGet = resolve;
        });
      }
      throw new Error(`fetch inesperado: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() =>
      useAttachmentAdapter({ ensureSession, labels: LABELS, pollIntervalMs: 0 }),
    );

    await act(async () => {
      await result.current.add(makeFile());
    });
    const localId = result.current.attachments[0].id;

    act(() => {
      result.current.remove(localId);
    });
    expect(result.current.attachments).toHaveLength(0);

    // El GET del primer poll sigue "en vuelo" -- resolverlo tarde NO debe
    // resucitar el adjunto ya removido.
    await act(async () => {
      resolveGet?.(jsonResponse(200, statusPayload({ status: "ready", sendable: true })));
      await Promise.resolve();
    });
    expect(result.current.attachments).toHaveLength(0);
    expect(result.current.attachmentIdsForSend()).toEqual([]);
  });
});

describe("useAttachmentAdapter — estados terminales con advertencia (N2, ANEXO §4.4)", () => {
  it("ready + requires_test_data_confirmation queda en warning, no sendable, con {detail}", async () => {
    const ensureSession = vi.fn().mockResolvedValue("session-1");
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = urlOf(input);
      if (init?.method === "POST" && url === "/api/attachments") return jsonResponse(201, createdPayload());
      if (url === "/api/attachments/att-1") {
        return jsonResponse(
          200,
          statusPayload({
            status: "ready",
            sendable: false,
            requires_test_data_confirmation: true,
            scan_summary: { pii_findings: [{ entity_type: "EMAIL_ADDRESS", count: 2, lines: [14] }] },
          }),
        );
      }
      throw new Error(`fetch inesperado: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() =>
      useAttachmentAdapter({ ensureSession, labels: LABELS, pollIntervalMs: 0 }),
    );

    await act(async () => {
      await result.current.add(makeFile("planilla.xlsx"));
    });
    await waitFor(() => expect(result.current.attachments[0].status).toBe("warning"));

    expect(result.current.attachments[0].sendable).toBe(false);
    // Tarea 8.2: el `entity_type` crudo de Presidio (`EMAIL_ADDRESS`) se
    // resuelve a su etiqueta amigable en plural (`labels.piiEntityLabels`,
    // ver el docstring de `summarizePii`) -- nunca el código crudo.
    expect(result.current.attachments[0].message).toBe(
      "Detectamos posibles datos personales en este archivo (2 emails). Recordá la política: solo datos de prueba hacia la IA.",
    );
    expect(result.current.attachmentIdsForSend()).toEqual([]);
  });

  it("singular/plural por hallazgo + múltiples hallazgos unidos con coma (ANEXO §10: «2 emails, 1 número de carnet»)", async () => {
    const ensureSession = vi.fn().mockResolvedValue("session-1");
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = urlOf(input);
      if (init?.method === "POST" && url === "/api/attachments") return jsonResponse(201, createdPayload());
      if (url === "/api/attachments/att-1") {
        return jsonResponse(
          200,
          statusPayload({
            status: "ready",
            sendable: false,
            requires_test_data_confirmation: true,
            scan_summary: {
              pii_findings: [
                { entity_type: "EMAIL_ADDRESS", count: 2, lines: [14] },
                { entity_type: "BO_CI", count: 1, lines: [22] },
              ],
            },
          }),
        );
      }
      throw new Error(`fetch inesperado: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() =>
      useAttachmentAdapter({ ensureSession, labels: LABELS, pollIntervalMs: 0 }),
    );

    await act(async () => {
      await result.current.add(makeFile("planilla.xlsx"));
    });
    await waitFor(() => expect(result.current.attachments[0].status).toBe("warning"));

    expect(result.current.attachments[0].message).toBe(
      "Detectamos posibles datos personales en este archivo (2 emails, 1 número de carnet). Recordá la política: solo datos de prueba hacia la IA.",
    );
  });

  it("entity_type sin mapear cae al código crudo (defensa en profundidad ante un reconocedor nuevo)", async () => {
    const ensureSession = vi.fn().mockResolvedValue("session-1");
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = urlOf(input);
      if (init?.method === "POST" && url === "/api/attachments") return jsonResponse(201, createdPayload());
      if (url === "/api/attachments/att-1") {
        return jsonResponse(
          200,
          statusPayload({
            status: "ready",
            sendable: false,
            requires_test_data_confirmation: true,
            scan_summary: {
              pii_findings: [{ entity_type: "CREDIT_CARD", count: 1, lines: [3] }],
            },
          }),
        );
      }
      throw new Error(`fetch inesperado: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() =>
      useAttachmentAdapter({ ensureSession, labels: LABELS, pollIntervalMs: 0 }),
    );

    await act(async () => {
      await result.current.add(makeFile("planilla.xlsx"));
    });
    await waitFor(() => expect(result.current.attachments[0].status).toBe("warning"));

    expect(result.current.attachments[0].message).toContain("1 CREDIT_CARD");
  });
});

describe("useAttachmentAdapter — confirmTestData() (N2, tarea 8.2)", () => {
  it("POST confirm-test-data + re-fetch de estado: pasa a ready sendable, sin advertencia", async () => {
    const ensureSession = vi.fn().mockResolvedValue("session-1");
    let statusCalls = 0;
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = urlOf(input);
      if (init?.method === "POST" && url === "/api/attachments") return jsonResponse(201, createdPayload());
      if (init?.method === "POST" && url === "/api/attachments/att-1/confirm-test-data") {
        return jsonResponse(200, {
          id: "att-1",
          status: "ready",
          requires_test_data_confirmation: false,
          sendable: true,
        });
      }
      if (url === "/api/attachments/att-1") {
        statusCalls += 1;
        if (statusCalls === 1) {
          return jsonResponse(
            200,
            statusPayload({
              status: "ready",
              sendable: false,
              requires_test_data_confirmation: true,
              scan_summary: { pii_findings: [{ entity_type: "EMAIL_ADDRESS", count: 1, lines: [5] }] },
            }),
          );
        }
        // Re-fetch tras confirmar: ya sin PII pendiente ni heurística de
        // inyección -- `deriveChipStatus` lo resuelve a `ready` limpio.
        return jsonResponse(200, statusPayload({ status: "ready", sendable: true }));
      }
      throw new Error(`fetch inesperado: ${init?.method ?? "GET"} ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() =>
      useAttachmentAdapter({ ensureSession, labels: LABELS, pollIntervalMs: 0 }),
    );

    await act(async () => {
      await result.current.add(makeFile("planilla.xlsx"));
    });
    await waitFor(() => expect(result.current.attachments[0].status).toBe("warning"));
    expect(result.current.attachments[0].sendable).toBe(false);

    const localId = result.current.attachments[0].id;
    await act(async () => {
      await result.current.confirmTestData(localId);
    });

    expect(result.current.attachments[0].status).toBe("ready");
    expect(result.current.attachments[0].sendable).toBe(true);
    expect(result.current.attachments[0].message).toBeNull();
    expect(result.current.attachments[0].confirming).toBe(false);
    expect(result.current.attachmentIdsForSend()).toEqual(["att-1"]);
  });

  it("fallo del POST (409 sin confirmación pendiente): deja la advertencia intacta, nunca silencioso", async () => {
    const ensureSession = vi.fn().mockResolvedValue("session-1");
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = urlOf(input);
      if (init?.method === "POST" && url === "/api/attachments") return jsonResponse(201, createdPayload());
      if (init?.method === "POST" && url === "/api/attachments/att-1/confirm-test-data") {
        return jsonResponse(409, { detail: { error_code: "no_pending_confirmation", params: {} } });
      }
      if (url === "/api/attachments/att-1") {
        return jsonResponse(
          200,
          statusPayload({
            status: "ready",
            sendable: false,
            requires_test_data_confirmation: true,
            scan_summary: { pii_findings: [{ entity_type: "EMAIL_ADDRESS", count: 1, lines: [5] }] },
          }),
        );
      }
      throw new Error(`fetch inesperado: ${init?.method ?? "GET"} ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() =>
      useAttachmentAdapter({ ensureSession, labels: LABELS, pollIntervalMs: 0 }),
    );

    await act(async () => {
      await result.current.add(makeFile("planilla.xlsx"));
    });
    await waitFor(() => expect(result.current.attachments[0].status).toBe("warning"));

    const localId = result.current.attachments[0].id;
    await act(async () => {
      await result.current.confirmTestData(localId);
    });

    expect(result.current.attachments[0].status).toBe("warning");
    expect(result.current.attachments[0].sendable).toBe(false);
    expect(result.current.attachments[0].confirming).toBe(false);
    expect(result.current.attachments[0].message).toBe(
      "Detectamos posibles datos personales en este archivo (1 email). Recordá la política: solo datos de prueba hacia la IA.",
    );
  });

  it("remove() a mitad de confirmTestData(): no revive el adjunto ya quitado", async () => {
    const ensureSession = vi.fn().mockResolvedValue("session-1");
    let resolveConfirm: ((response: Response) => void) | undefined;
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = urlOf(input);
      if (init?.method === "POST" && url === "/api/attachments") return jsonResponse(201, createdPayload());
      if (init?.method === "POST" && url === "/api/attachments/att-1/confirm-test-data") {
        return new Promise<Response>((resolve) => {
          resolveConfirm = resolve;
        });
      }
      if (url === "/api/attachments/att-1") {
        return jsonResponse(
          200,
          statusPayload({
            status: "ready",
            sendable: false,
            requires_test_data_confirmation: true,
            scan_summary: { pii_findings: [{ entity_type: "EMAIL_ADDRESS", count: 1, lines: [5] }] },
          }),
        );
      }
      throw new Error(`fetch inesperado: ${init?.method ?? "GET"} ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() =>
      useAttachmentAdapter({ ensureSession, labels: LABELS, pollIntervalMs: 0 }),
    );

    await act(async () => {
      await result.current.add(makeFile("planilla.xlsx"));
    });
    await waitFor(() => expect(result.current.attachments[0].status).toBe("warning"));

    const localId = result.current.attachments[0].id;
    let confirmPromise: Promise<void> | undefined;
    act(() => {
      confirmPromise = result.current.confirmTestData(localId);
    });
    act(() => {
      result.current.remove(localId);
    });
    expect(result.current.attachments).toHaveLength(0);

    await act(async () => {
      resolveConfirm?.(jsonResponse(200, { id: "att-1", status: "ready", requires_test_data_confirmation: false, sendable: true }));
      await confirmPromise;
    });

    expect(result.current.attachments).toHaveLength(0);
  });
});
