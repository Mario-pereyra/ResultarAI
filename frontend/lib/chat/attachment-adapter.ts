"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { csrfHeaders } from "@/lib/csrf";

/**
 * `AttachmentAdapter` del composer (d14-attachments, tarea 8.1). Fuente
 * normativa: `openspec/changes/d14-attachments/design.md` decisión 9,
 * `design/ANEXO-ATTACHMENTS.md` §6 (UX de referencia)/§8 (pipeline)/§10
 * (textos de UI), `openspec/changes/d14-attachments/specs/attachments-ui/spec.md`.
 *
 * ## Decisión de integración: módulo propio, NO el runtime real de assistant-ui
 *
 * La decisión 9 de `design.md` describe "`AttachmentAdapter` de assistant-ui...
 * componibles con `CompositeAttachmentAdapter`". Este repo tiene
 * `@assistant-ui/react` en `package.json`, pero el chat (`chat-content.tsx` +
 * `composer.tsx`, d13-chat-conversacion) es un componente 100% CUSTOM: estado
 * propio (`useState`) + streaming SSE propio (`use-turn-stream.ts`, `fetch()` +
 * `ReadableStream` con reconexión por `Last-Event-ID`), sin montar
 * `AssistantRuntimeProvider`/`Thread`/`useComposerRuntime`. Adoptar el runtime
 * real de assistant-ui SOLO para heredar su `AttachmentAdapter` implicaría
 * reescribir `chat-content.tsx`/`use-turn-stream.ts` sobre ese runtime --
 * fuera de alcance de esta tarea puntual (y no lo pide ninguna spec vigente).
 *
 * Por eso este módulo implementa la MISMA interfaz CONCEPTUAL que
 * assistant-ui documenta (`add()`/`send()`/`remove()`, ver ANEXO §6 "Encaje
 * con assistant-ui"), como un hook de React propio compatible con el resto de
 * `lib/chat/*` (mismo patrón que `use-turn-stream.ts`), con el agregado
 * específico de este dominio que assistant-ui no modela: la extracción es
 * ASÍNCRONA server-side (worker aislado, ANEXO §4.1/§8), así que `add()` no
 * solo valida/sube -- también hace *polling* de `GET /api/attachments/{id}`
 * hasta un estado terminal, actualizando el estado observable en vivo.
 *
 * Un único adapter para TODAS las familias de tipo (no "uno por familia" como
 * en el stack real de assistant-ui, que necesita distinguir `accept` por
 * adapter para saber a cuál despachar): acá hay un solo endpoint de subida
 * (`POST /api/attachments`) y el backend (`app/attachments/upload.py::resolve_type`)
 * ya resuelve el tipo real por extensión + magic bytes (ANEXO §4.1, "el
 * Content-Type del navegador nunca se confía") -- no hay nada que un adapter
 * por familia decida del lado del cliente; el `accept` del `<input type="file">`
 * del composer se deja SIN restringir a propósito (ver `composer.tsx`), para no
 * duplicar en el cliente una matriz de tipos que ya es config de instancia
 * server-side (ANEXO §9, "todos los valores son defaults de configuración").
 *
 * `send()` real de assistant-ui convierte el adjunto pendiente en una parte de
 * contenido del mensaje; acá (decisión 9: "la `inserted_text` la compone el
 * SERVIDOR") el cliente nunca ve/transporta el texto extraído -- `send()` se
 * reduce a `attachmentIdsForSend()`, que junta los `attachment_id` `sendable`
 * para que el llamador (`chat-content.tsx`) los pase como `attachment_ids` en
 * el turno (`SendMessageRequest`, ver `use-turn-stream.ts`).
 *
 * ## Qué mapea este módulo a texto §10 (y qué NO)
 *
 * `add()` mapea el rechazo tipado de la subida (`POST /api/attachments`, 422
 * `{error_code, params}` -- ver el docstring de
 * `resultarai/app/attachments/errors.py`) a los textos de
 * `messages/es.json` → `Chat.attachments.errors.*`. El polling mapea también
 * los estados terminales `blocked` (N3, ANEXO §4.4) y `error` (fallo de
 * extracción, todos los `error_code` de esa familia colapsan al texto
 * "Error genérico de extracción" -- documentado así en `errors.py`) a texto
 * resuelto. Lo que este módulo NO resuelve a texto (queda para 8.2/8.3, fuera
 * de esta tarea): la redacción de los estados NO terminales que dependen de
 * datos en vivo/rol (`Subiendo… {percent}%`, `Listo · {tokens} tokens` vs.
 * `Listo · usa {percent}%…`) -- el chip (8.2, `components/chat/attachment-chip.tsx`)
 * es quien decide esa presentación con `tokenCount`/`includedPercent`/
 * `truncated`/rol, que este hook expone tal cual vienen de
 * `GET /api/attachments/{id}`.
 *
 * ## Agregado de la tarea 8.2 (chip de estado)
 *
 * `confirmTestData()` es la ÚNICA pieza de red nueva de 8.2 en este módulo
 * (todo lo demás -- estados/textos/rol -- es puramente presentacional en el
 * chip, ver su docstring): completa el ciclo N2 que 8.1 dejó expuesto solo
 * como lectura (`requiresTestDataConfirmation`) sin forma de resolverlo.
 * También se resuelven acá los códigos crudos de `entity_type` de Presidio
 * del `{detail}` de `errors.piiDetected` a etiquetas amigables
 * (`piiEntityLabels`, ver `summarizePii`) -- mejora dentro de alcance de
 * 8.2 documentada en `tasks.md`.
 */

// ---------------------------------------------------------------------------
// Contrato HTTP (espejo de `resultarai/app/api/attachments.py`)
// ---------------------------------------------------------------------------

/** Espejo de `AttachmentResponse` (`POST /api/attachments`, 201). */
interface AttachmentCreatedPayload {
  id: string;
  session_id: string | null;
  status: string;
  original_name: string;
  detected_type: string | null;
  size_bytes: number;
  sha256: string;
  created_at: string;
}

/** Espejo de `AttachmentStatusResponse` (`GET /api/attachments/{id}`). */
interface AttachmentStatusPayload {
  id: string;
  status: string;
  original_name: string;
  detected_type: string | null;
  size_bytes: number;
  created_at: string;
  sendable: boolean;
  requires_test_data_confirmation: boolean;
  scan_summary: Record<string, unknown> | null;
  inserted: boolean;
  token_count: number | null;
  included_percent: number | null;
  truncated: boolean | null;
}

interface TypedErrorDetail {
  error_code?: string;
  params?: Record<string, unknown>;
}

/** Hallazgo N3 (`scan_result.n3_findings`, ver `app/attachments/data_scan.py`). */
interface N3FindingPayload {
  secret_type: string;
  line: number;
  redacted: string;
}

/** Hallazgo N2 agregado (`scan_result.pii_findings`). */
interface PiiFindingPayload {
  entity_type: string;
  count: number;
  lines: number[];
}

/** Flag heurístico de instrucción embebida (`scan_result.injection_flags`). */
interface InjectionFlagPayload {
  flag_type: string;
  pattern_id: string;
  evidence: string;
  line: number;
  offset: number;
}

// ---------------------------------------------------------------------------
// Tipos públicos
// ---------------------------------------------------------------------------

/**
 * Estado observable de un adjunto, en el vocabulario del chip (ANEXO §10,
 * "Estados del chip"): `uploading` (subida en curso -- POST en vuelo o
 * `Attachment.status == "uploaded"`, todavía sin extracción arrancada),
 * `processing` (`status == "extracting"`), `ready` (`status == "ready"` sin
 * hallazgos que requieran atención), `warning` (`status == "ready"` PERO con
 * PII sin confirmar o una heurística de instrucción embebida -- ANEXO §4.3/
 * §4.4), `blocked` (N3) y `error` (rechazo de subida o fallo de extracción).
 */
export type AttachmentChipStatus =
  | "uploading"
  | "processing"
  | "ready"
  | "warning"
  | "blocked"
  | "error";

/** Estado observable de UN adjunto del composer -- lo que 8.2 (chips) y 8.3
 * (vista previa) van a leer para renderizar, sin tener que volver a llamar al
 * backend. */
export interface AttachmentItem {
  /** Id ESTABLE de UI (no cambia aunque `attachmentId` pase de `null` al id
   * real del backend) -- clave de React y argumento de `remove()`. */
  id: string;
  /** `Attachment.id` real, `null` mientras el `POST /api/attachments` sigue
   * en vuelo (estado `uploading` sin id todavía). */
  attachmentId: string | null;
  file: File;
  originalName: string;
  status: AttachmentChipStatus;
  /** `is_sendable(attachment)` tal cual lo devuelve el backend -- el turno
   * solo debe incluir adjuntos con `sendable: true` (ver
   * `attachmentIdsForSend`). */
  sendable: boolean;
  requiresTestDataConfirmation: boolean;
  tokenCount: number | null;
  includedPercent: number | null;
  truncated: boolean | null;
  /** Texto §10 YA resuelto para `error`/`blocked`/`warning` -- `null` en
   * `uploading`/`processing`/`ready` limpio (nada que decir todavía). */
  message: string | null;
  /** `true` mientras `confirmTestData()` tiene un `POST
   * /api/attachments/{id}/confirm-test-data` en vuelo (tarea 8.2) -- el chip
   * lo usa para deshabilitar el checkbox "Confirmo que son datos de prueba"
   * y evitar un doble envío mientras se audita la confirmación. */
  confirming: boolean;
}

/** Textos §10 que este módulo necesita para mapear errores tipados --
 * subconjunto de `Chat.attachments.errors`/`Chat.attachments.fileTypes` de
 * `messages/es.json` (ver `app/(shell)/chat/labels.ts::buildChatLabels`).
 * Deliberadamente NO incluye `pdfScanned`/`emptyFile`/`truncatedPreview`/
 * `pdfTableWarning`/`quotaExceeded` -- ninguno es un `error_code` que
 * `POST /api/attachments` o el escaneo de estado terminal puedan producir
 * hoy (OCR es V1.1 diferido; la vista previa truncada es 8.3; el rechazo de
 * cuota-en-mensaje es `message_token_budget_exceeded`, un error del ENVÍO del
 * turno -- no de este adapter, ver el docstring del módulo). */
export interface AttachmentAdapterErrorLabels {
  unsupportedType: string; // {extension}
  falsifiedType: string; // {extension}
  withMacros: string; // {extension}
  tooLarge: string; // {limitMb} {fileType}
  pdfProtected: string;
  imageNotSupported: string;
  wordLegacy: string;
  tooManyAttachments: string; // {limit}
  credentialsDetected: string; // {detail}
  piiDetected: string; // {detail}
  embeddedInstruction: string; // {detail}
  genericError: string;
}

/** Nombres legibles de `FileCategory` (`resultarai/app/attachments/filetypes.py`)
 * para interpolar `{fileType}` en `errors.tooLarge` -- ver `Chat.attachments.fileTypes`. */
export interface AttachmentFileTypeLabels {
  excel: string;
  csv: string;
  pdf: string;
  docx: string;
  text: string;
  code: string;
  log: string;
}

/** Etiqueta amigable singular/plural de un `entity_type` de Presidio (mismo
 * patrón `...One`/`...Other` que `Chat.branch.reprocessWarningOne/Other` --
 * ver `labels.ts`, que arma este objeto desde `Chat.attachments.piiEntityLabels`). */
export interface PiiEntityLabel {
  one: string;
  other: string;
}

export interface AttachmentAdapterLabels {
  errors: AttachmentAdapterErrorLabels;
  fileTypes: AttachmentFileTypeLabels;
  /** Etiquetas amigables por `entity_type` (`EMAIL_ADDRESS`/`PHONE_NUMBER`/
   * `PERSON`/`BO_CI`/`BO_NIT`/`BO_PHONE`, ver `_PII_ENTITIES` en
   * `resultarai/app/attachments/data_scan.py`) para el `{detail}` de
   * `errors.piiDetected` -- mejora dentro de alcance de la tarea 8.2: los
   * códigos crudos de Presidio nunca llegan al usuario tal cual (ver
   * `summarizePii` más abajo). Un `entity_type` sin entrada cae al código
   * crudo (defensa en profundidad ante un reconocedor nuevo sin mapear). */
  piiEntityLabels: Record<string, PiiEntityLabel>;
}

export const DEFAULT_MAX_ATTACHMENTS_PER_MESSAGE = 5;
const DEFAULT_POLL_INTERVAL_MS = 1500;

export interface UseAttachmentAdapterOptions {
  /** Resuelve (creando si hace falta) el id de la sesión borrador -- EL MISMO
   * `ensureSession` que `chat-content.tsx` ya usa en `handleSubmit`: adjuntar
   * un archivo ANTES del primer mensaje debe crear la sesión igual que
   * enviarlo, porque `POST /api/attachments` exige un `session_id` de una
   * sesión ya existente y propia (`app/api/attachments.py`). `null` si la
   * creación falla (mismo contrato que `ensureSession` ya expone). */
  ensureSession: () => Promise<string | null>;
  labels: AttachmentAdapterLabels;
  /** Default 5 (`DEFAULT_MAX_ATTACHMENTS_PER_MESSAGE`, espejo de
   * `AttachmentsConfig.max_attachments_per_message` -- ANEXO §9). La
   * autoridad real es siempre el 422 `too_many_attachments` del backend;
   * este límite es la validación CLIENT-SIDE pedida por la tarea 8.1 para no
   * ni siquiera intentar la subida número 6. */
  maxAttachments?: number;
  /** Intervalo entre polls de `GET /api/attachments/{id}`, en ms. `0` en
   * tests para no depender de temporizadores reales (mismo patrón que
   * `reconnectDelayMs` de `use-turn-stream.ts`). Default 1500. */
  pollIntervalMs?: number;
}

export interface UseAttachmentAdapterResult {
  attachments: AttachmentItem[];
  /** `add()` del adapter conceptual: valida el límite client-side, sube y
   * arranca el polling -- ver el docstring del módulo. */
  add: (file: File) => Promise<void>;
  /** `remove()` del adapter conceptual: quita un adjunto de la lista y corta
   * cualquier polling en curso. Sin endpoint de borrado en el backend todavía
   * (`app/api/attachments.py` no expone `DELETE`) -- quitar del lado del
   * cliente ANTES de enviar el turno es suficiente porque `attachmentIdsForSend`
   * solo junta los adjuntos que siguen en la lista; el archivo ya subido queda
   * huérfano en el borrador hasta que la retención (tarea 7.2) lo limpie. */
  remove: (id: string) => void;
  /** Confirma la advertencia N2 de un adjunto (tarea 8.2) -- ver el
   * docstring de `confirmTestData` más abajo para el detalle del contrato
   * HTTP y por qué re-consulta `GET /api/attachments/{id}` en vez de aplicar
   * directo la respuesta del POST. */
  confirmTestData: (id: string) => Promise<void>;
  /** `send()` del adapter conceptual: los `attachment_id` `sendable` listos
   * para viajar en `attachment_ids` del turno (`SendMessageRequest`). */
  attachmentIdsForSend: () => string[];
  /** Limpia la lista tras un envío exitoso (mismo momento en que
   * `chat-content.tsx` limpia `composerText`) -- el servidor ya compuso el
   * mensaje con esos `attachment_id`, así que no hay razón para seguir
   * mostrándolos como "pendientes" del próximo turno. */
  clear: () => void;
}

// ---------------------------------------------------------------------------
// Interpolación de plantillas (mismo patrón `.replace("{x}", …)` que
// `message-edit.tsx`/`gateway-offline-card.tsx`, generalizado a N claves)
// ---------------------------------------------------------------------------

function interpolate(template: string, params: Record<string, string | number>): string {
  return Object.entries(params).reduce(
    (text, [key, value]) => text.split(`{${key}}`).join(String(value)),
    template,
  );
}

// ---------------------------------------------------------------------------
// Mapeo de rechazos de subida (422 `{error_code, params}`) a texto §10
// ---------------------------------------------------------------------------

type RejectionResolver = (
  params: Record<string, unknown>,
  labels: AttachmentAdapterLabels,
) => string;

function fileTypeLabel(typeGroup: unknown, labels: AttachmentAdapterLabels): string {
  const key = String(typeGroup ?? "");
  const known = labels.fileTypes as unknown as Record<string, string | undefined>;
  return known[key] ?? key;
}

const UPLOAD_REJECTION_RESOLVERS: Record<string, RejectionResolver> = {
  too_large: (params, labels) =>
    interpolate(labels.errors.tooLarge, {
      limitMb: String(params.limit_mb ?? ""),
      fileType: fileTypeLabel(params.type_group, labels),
    }),
  type_not_allowed: (params, labels) =>
    interpolate(labels.errors.unsupportedType, { extension: String(params.extension ?? "") }),
  type_forged: (params, labels) =>
    interpolate(labels.errors.falsifiedType, { extension: String(params.extension ?? "") }),
  macros_not_allowed: (params, labels) =>
    interpolate(labels.errors.withMacros, { extension: String(params.extension ?? "") }),
  // Comprimido (ANEXO §2.6): mismo texto "tipo no soportado" que un rechazo
  // de extensión genérico -- ver el mapa error_code -> texto §10 documentado
  // en `resultarai/app/attachments/errors.py`.
  compressed_not_allowed: (params, labels) =>
    interpolate(labels.errors.unsupportedType, { extension: String(params.extension ?? "") }),
  // Ejecutable/script: sin texto propio en el §10 (solo aparece en la
  // matriz §9 como "Rechazado") -- reutiliza el mismo genérico de tipo no
  // soportado que `compressed_not_allowed`.
  executable_rejected: (params, labels) =>
    interpolate(labels.errors.unsupportedType, { extension: String(params.extension ?? "") }),
  legacy_doc: (_params, labels) => labels.errors.wordLegacy,
  image_not_supported: (_params, labels) => labels.errors.imageNotSupported,
  pdf_password: (_params, labels) => labels.errors.pdfProtected,
  too_many_attachments: (params, labels) =>
    interpolate(labels.errors.tooManyAttachments, { limit: String(params.limit ?? "") }),
};

function resolveUploadRejectionMessage(
  errorCode: string,
  params: Record<string, unknown>,
  labels: AttachmentAdapterLabels,
): string {
  const resolver = UPLOAD_REJECTION_RESOLVERS[errorCode];
  return resolver ? resolver(params, labels) : labels.errors.genericError;
}

// ---------------------------------------------------------------------------
// Mapeo de estados terminales (`blocked`/`error`/`ready` con advertencia) a texto §10
// ---------------------------------------------------------------------------

/**
 * `{detail}` de "N3 (credenciales)" -- ANEXO §10: `Password=" en la línea 23`.
 * Se toma el PRIMER hallazgo (el backend ya solo bloquea, no hace falta
 * enumerar todos para que el usuario sepa qué limpiar).
 */
function summarizeN3(findings: N3FindingPayload[]): string {
  const first = findings[0];
  if (!first) return "";
  return `"${first.redacted}" en la línea ${first.line}`;
}

/** Singular/plural del `entity_type` de un hallazgo N2 -- cae al código
 * crudo (`EMAIL_ADDRESS`, ...) si `piiEntityLabels` no lo cubre todavía. */
function pluralizePiiEntity(
  entityType: string,
  count: number,
  piiEntityLabels: Record<string, PiiEntityLabel>,
): string {
  const label = piiEntityLabels[entityType];
  if (!label) return entityType;
  return count === 1 ? label.one : label.other;
}

/** `{detail}` de "N2 (PII)" -- agrega cantidad+tipo AMIGABLE de cada
 * hallazgo, ANEXO §10 (`"2 emails, 1 número de carnet…"`) -- tarea 8.2:
 * los `entity_type` crudos que produce el escáner (`data_scan.py`) nunca
 * llegan al usuario, se resuelven vía `piiEntityLabels` (ver su docstring). */
function summarizePii(
  findings: PiiFindingPayload[],
  piiEntityLabels: Record<string, PiiEntityLabel>,
): string {
  return findings
    .map(
      (finding) =>
        `${finding.count} ${pluralizePiiEntity(finding.entity_type, finding.count, piiEntityLabels)}`,
    )
    .join(", ");
}

function resolveBlockedMessage(
  scanSummary: Record<string, unknown> | null,
  labels: AttachmentAdapterLabels,
): string {
  const findings = (scanSummary?.n3_findings as N3FindingPayload[] | undefined) ?? [];
  return interpolate(labels.errors.credentialsDetected, { detail: summarizeN3(findings) });
}

/** `null` si el adjunto `ready` está limpio (sin PII sin confirmar ni
 * heurística de inyección) -- ver `deriveChipStatus`, que decide `warning`
 * vs. `ready` con la MISMA condición. */
function resolveReadyWarningMessage(
  scanSummary: Record<string, unknown> | null,
  requiresConfirmation: boolean,
  labels: AttachmentAdapterLabels,
): string | null {
  if (requiresConfirmation) {
    const findings = (scanSummary?.pii_findings as PiiFindingPayload[] | undefined) ?? [];
    return interpolate(labels.errors.piiDetected, {
      detail: summarizePii(findings, labels.piiEntityLabels),
    });
  }
  const injectionFlags = (scanSummary?.injection_flags as InjectionFlagPayload[] | undefined) ?? [];
  const first = injectionFlags[0];
  if (first) {
    return interpolate(labels.errors.embeddedInstruction, {
      detail: `"${first.evidence}" en la línea ${first.line}`,
    });
  }
  return null;
}

/** Todos los `error_code` de la familia `AttachmentExtractionError`
 * (`zip_bomb_suspected`/`extraction_timeout`/`extraction_failed`) colapsan al
 * mismo texto genérico -- documentado así en el docstring de
 * `resultarai/app/attachments/errors.py`. */
function resolveExtractionErrorMessage(labels: AttachmentAdapterLabels): string {
  return labels.errors.genericError;
}

function deriveChipStatus(payload: AttachmentStatusPayload): AttachmentChipStatus {
  if (payload.status === "uploaded") return "uploading";
  if (payload.status === "extracting") return "processing";
  if (payload.status === "blocked") return "blocked";
  if (payload.status === "error") return "error";
  // "ready": advertencia (N2 sin confirmar o heurística de inyección) vs. limpio.
  const injectionFlags =
    (payload.scan_summary?.injection_flags as InjectionFlagPayload[] | undefined) ?? [];
  return payload.requires_test_data_confirmation || injectionFlags.length > 0 ? "warning" : "ready";
}

function resolveStatusMessage(
  payload: AttachmentStatusPayload,
  labels: AttachmentAdapterLabels,
): string | null {
  if (payload.status === "blocked") return resolveBlockedMessage(payload.scan_summary, labels);
  if (payload.status === "error") return resolveExtractionErrorMessage(labels);
  if (payload.status === "ready") {
    return resolveReadyWarningMessage(
      payload.scan_summary,
      payload.requires_test_data_confirmation,
      labels,
    );
  }
  return null; // uploaded/extracting: todavía nada que decir.
}

const TERMINAL_BACKEND_STATUSES: ReadonlySet<string> = new Set(["ready", "blocked", "error"]);

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

let localIdCounter = 0;
function nextLocalId(): string {
  localIdCounter += 1;
  return `attachment-local-${localIdCounter}`;
}

export function useAttachmentAdapter(
  options: UseAttachmentAdapterOptions,
): UseAttachmentAdapterResult {
  const { ensureSession, labels } = options;
  const maxAttachments = options.maxAttachments ?? DEFAULT_MAX_ATTACHMENTS_PER_MESSAGE;
  const pollIntervalMs = options.pollIntervalMs ?? DEFAULT_POLL_INTERVAL_MS;

  const [attachments, setAttachments] = useState<AttachmentItem[]>([]);
  // Espejo de `attachments` para leer el conteo/lista ACTUAL desde dentro de
  // un callback async ya en vuelo (`add`) sin encadenar la identidad de la
  // función a cada cambio de estado -- mismo motivo que
  // `turnIdRef`/`accumulatedTextRef` en `use-turn-stream.ts`. Sincronizado en
  // un efecto (no durante el render: mutar un ref en el cuerpo del
  // componente dispara `react-hooks/refs`, ver docs de la regla) -- corre
  // ANTES de que cualquier evento de usuario nuevo pueda disparar `add()`,
  // así que sigue siendo la lectura "última" válida para ese uso.
  const attachmentsRef = useRef<AttachmentItem[]>([]);
  useEffect(() => {
    attachmentsRef.current = attachments;
  }, [attachments]);

  // Temporizadores de polling en curso, por id LOCAL -- se cancelan al
  // remover/limpiar/desmontar (defensa en profundidad: sin esto, un poll
  // tardío podría "resucitar" un adjunto ya quitado por el usuario).
  const timersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());
  // Ids LOCALES removidos -- un poll en vuelo lo consulta antes de aplicar
  // cualquier actualización de estado (evita el "setState en un item que ya
  // no existe" cuando la remoción llega mientras el `fetch` estaba en el aire).
  const removedRef = useRef<Set<string>>(new Set());

  const clearTimer = useCallback((id: string) => {
    const timer = timersRef.current.get(id);
    if (timer !== undefined) {
      clearTimeout(timer);
      timersRef.current.delete(id);
    }
  }, []);

  useEffect(() => {
    // Desmontar el composer (navegación fuera del chat a mitad de subida)
    // corta cualquier polling pendiente -- sin esto, `setAttachments` de un
    // poll tardío dispararía el warning de React "no se puede actualizar un
    // componente desmontado". Captura la instancia del `Map` DENTRO del
    // efecto (no `timersRef.current` directo en la cleanup) -- mismo motivo
    // que documenta `react-hooks/exhaustive-deps` para refs de ciclo de vida.
    const timers = timersRef.current;
    return () => {
      for (const timer of timers.values()) clearTimeout(timer);
      timers.clear();
    };
  }, []);

  const updateItem = useCallback((localId: string, patch: Partial<AttachmentItem>) => {
    setAttachments((prev) =>
      prev.map((item) => (item.id === localId ? { ...item, ...patch } : item)),
    );
  }, []);

  const applyStatusPayload = useCallback(
    (localId: string, payload: AttachmentStatusPayload) => {
      updateItem(localId, {
        attachmentId: payload.id,
        status: deriveChipStatus(payload),
        sendable: payload.sendable,
        requiresTestDataConfirmation: payload.requires_test_data_confirmation,
        tokenCount: payload.token_count,
        includedPercent: payload.included_percent,
        truncated: payload.truncated,
        message: resolveStatusMessage(payload, labels),
      });
    },
    [labels, updateItem],
  );

  const pollStatus = useCallback(
    (localId: string, attachmentId: string) => {
      const scheduleNext = () => {
        if (removedRef.current.has(localId)) return;
        const timer = setTimeout(() => void poll(), pollIntervalMs);
        timersRef.current.set(localId, timer);
      };

      async function poll(): Promise<void> {
        if (removedRef.current.has(localId)) return;
        let response: Response;
        try {
          response = await fetch(`/api/attachments/${attachmentId}`);
        } catch {
          // Corte de red pasajero -- reintenta en el próximo tick (mismo
          // espíritu que la reconexión de `use-turn-stream.ts`, sin el límite
          // de intentos de esa reconexión: acá no hay un turno esperando, así
          // que reintentar indefinidamente mientras el adjunto siga en la
          // lista es aceptable).
          scheduleNext();
          return;
        }
        if (removedRef.current.has(localId)) return;
        if (!response.ok) {
          updateItem(localId, { status: "error", message: labels.errors.genericError });
          return;
        }
        const payload = (await response.json()) as AttachmentStatusPayload;
        if (removedRef.current.has(localId)) return;
        applyStatusPayload(localId, payload);
        if (!TERMINAL_BACKEND_STATUSES.has(payload.status)) scheduleNext();
      }

      void poll();
    },
    [pollIntervalMs, labels, updateItem, applyStatusPayload],
  );

  const add = useCallback(
    async (file: File) => {
      const localId = nextLocalId();

      if (attachmentsRef.current.length >= maxAttachments) {
        setAttachments((prev) => [
          ...prev,
          {
            id: localId,
            attachmentId: null,
            file,
            originalName: file.name,
            status: "error",
            sendable: false,
            requiresTestDataConfirmation: false,
            tokenCount: null,
            includedPercent: null,
            truncated: null,
            message: interpolate(labels.errors.tooManyAttachments, { limit: maxAttachments }),
            confirming: false,
          },
        ]);
        return;
      }

      setAttachments((prev) => [
        ...prev,
        {
          id: localId,
          attachmentId: null,
          file,
          originalName: file.name,
          status: "uploading",
          sendable: false,
          requiresTestDataConfirmation: false,
          tokenCount: null,
          includedPercent: null,
          truncated: null,
          message: null,
          confirming: false,
        },
      ]);

      const sessionId = await ensureSession();
      if (removedRef.current.has(localId)) return; // se quitó mientras se creaba la sesión
      if (!sessionId) {
        updateItem(localId, { status: "error", message: labels.errors.genericError });
        return;
      }

      const formData = new FormData();
      formData.append("file", file);
      formData.append("session_id", sessionId);

      let response: Response;
      try {
        // Sin `Content-Type` explícito: el navegador arma el boundary de
        // `multipart/form-data` -- fijarlo a mano rompería el parseo del
        // backend (mismo motivo por el que `fetch` con `FormData` nunca debe
        // llevar ese header manual).
        response = await fetch("/api/attachments", {
          method: "POST",
          headers: { ...csrfHeaders() },
          body: formData,
        });
      } catch {
        if (!removedRef.current.has(localId)) {
          updateItem(localId, { status: "error", message: labels.errors.genericError });
        }
        return;
      }
      if (removedRef.current.has(localId)) return;

      if (!response.ok) {
        let errorCode = "";
        let params: Record<string, unknown> = {};
        try {
          const body = (await response.json()) as { detail?: TypedErrorDetail };
          errorCode = body.detail?.error_code ?? "";
          params = body.detail?.params ?? {};
        } catch {
          // Sin cuerpo interpretable -- se resuelve al genérico más abajo.
        }
        updateItem(localId, {
          status: "error",
          message: resolveUploadRejectionMessage(errorCode, params, labels),
        });
        return;
      }

      const created = (await response.json()) as AttachmentCreatedPayload;
      // `create_attachment` siempre persiste en estado `uploaded` (nunca
      // arranca "ready" de una) -- mapea directo a `uploading` sin pasar por
      // `deriveChipStatus`.
      updateItem(localId, { attachmentId: created.id, status: "uploading" });
      pollStatus(localId, created.id);
    },
    [maxAttachments, ensureSession, labels, updateItem, pollStatus],
  );

  const remove = useCallback(
    (id: string) => {
      removedRef.current.add(id);
      clearTimer(id);
      setAttachments((prev) => prev.filter((item) => item.id !== id));
    },
    [clearTimer],
  );

  /**
   * Confirma la advertencia N2 de `id` (`AttachmentItem.id`, el LOCAL --
   * mismo argumento que `remove`) -- tarea 8.2: el chip lo llama desde el
   * checkbox "Confirmo que son datos de prueba" (ANEXO §4.4/§10).
   *
   * POSTea `/api/attachments/{attachmentId}/confirm-test-data`
   * (`confirm_test_data_endpoint`, audita la confirmación server-side y baja
   * el bloqueo N2) y luego vuelve a pedir `GET /api/attachments/{id}` en vez
   * de aplicar directo la respuesta del POST: `TestDataConfirmationResponse`
   * no trae `scan_summary`, así que no alcanza para saber si el adjunto
   * sigue en `warning` por OTRO motivo (heurística de instrucción embebida,
   * ver `deriveChipStatus`) -- reutiliza el MISMO mapeo que el polling
   * (`applyStatusPayload`) para no duplicar esa lógica.
   *
   * Un fallo (409 "sin confirmación pendiente" por doble click/doble
   * pestaña, o de red) deja la advertencia N2 intacta -- nunca silencioso,
   * el usuario sigue viendo la causa por la que no puede enviar -- y solo
   * libera `confirming` para que el checkbox admita reintentar.
   */
  const confirmTestData = useCallback(
    async (id: string) => {
      const item = attachmentsRef.current.find((entry) => entry.id === id);
      if (!item || !item.attachmentId) return;
      const attachmentId = item.attachmentId;

      updateItem(id, { confirming: true });

      let response: Response;
      try {
        response = await fetch(`/api/attachments/${attachmentId}/confirm-test-data`, {
          method: "POST",
          headers: { ...csrfHeaders() },
        });
      } catch {
        if (!removedRef.current.has(id)) updateItem(id, { confirming: false });
        return;
      }
      if (removedRef.current.has(id)) return;
      if (!response.ok) {
        updateItem(id, { confirming: false });
        return;
      }

      let statusResponse: Response;
      try {
        statusResponse = await fetch(`/api/attachments/${attachmentId}`);
      } catch {
        if (!removedRef.current.has(id)) updateItem(id, { confirming: false });
        return;
      }
      if (removedRef.current.has(id)) return;
      if (!statusResponse.ok) {
        updateItem(id, { confirming: false });
        return;
      }
      const payload = (await statusResponse.json()) as AttachmentStatusPayload;
      if (removedRef.current.has(id)) return;
      applyStatusPayload(id, payload);
      updateItem(id, { confirming: false });
    },
    [updateItem, applyStatusPayload],
  );

  const attachmentIdsForSend = useCallback((): string[] => {
    return attachmentsRef.current
      .filter((item): item is AttachmentItem & { attachmentId: string } =>
        item.attachmentId !== null && item.sendable,
      )
      .map((item) => item.attachmentId);
  }, []);

  const clear = useCallback(() => {
    for (const item of attachmentsRef.current) {
      removedRef.current.add(item.id);
      clearTimer(item.id);
    }
    setAttachments([]);
  }, [clearTimer]);

  return { attachments, add, remove, confirmTestData, attachmentIdsForSend, clear };
}
