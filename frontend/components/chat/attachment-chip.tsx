"use client";

import { formatTokenCountBO } from "@/lib/format-bo";
import type { AttachmentItem } from "@/lib/chat/attachment-adapter";
import type { Role } from "@/lib/session-context";

/**
 * Chip de adjunto del composer (d14-attachments, tarea 8.2, vista
 * `07-composer` / `design/mockups/07-composer-attachments.html` sección A).
 * Fuente normativa: `design/ANEXO-ATTACHMENTS.md` §6 ("estados visibles en
 * el chip ... con causa específica") y §10 ("Estados del chip") + spec
 * `openspec/changes/d14-attachments/specs/attachments-ui/spec.md`
 * (Requirement "Chip de adjunto con estados y causa específica").
 *
 * Puramente presentacional: consume `AttachmentItem` tal cual lo expone
 * `useAttachmentAdapter()` (`lib/chat/attachment-adapter.ts`) -- ESTE
 * componente NO hace ningún `fetch` propio (`onRemove`/`onConfirmTestData`
 * son las únicas piezas de red, y viven en el adapter). Reemplaza la lista
 * mínima de texto ("nombre + mensaje §10 + Quitar") que la tarea 8.1 dejó
 * como punto de integración en `composer.tsx`.
 *
 * Estados (`AttachmentChipStatus`) → texto de `Chat.attachments.states`
 * (`messages/es.json`, portados en la tarea 8.4):
 * - `uploading`/`processing`: transitorios, spinner + texto neutro.
 * - `ready`: "Listo" -- la MÉTRICA de espacio cambia por rol (Requirement
 *   "Transparencia de espacio por capa de rol"): Funcional ve `%` del
 *   espacio del mensaje, Técnico/Admin ve tokens (`formatTokenCountBO`,
 *   `lib/format-bo.ts`). Si además está truncado, un tercer texto
 *   (`readyTruncated`, universal para cualquier rol) invita a abrir "Ver lo
 *   que verá el agente" -- la tarea 8.3 implementa ESE panel; acá solo se
 *   deja el punto de integración (`onOpenPreview`, opcional): sin ese
 *   callback el texto queda como texto plano, nunca un botón roto.
 * - `warning`: N2 (PII sin confirmar) o heurística de instrucción embebida
 *   (`item.message` ya trae la causa exacta, resuelta por el adapter). Con
 *   PII pendiente (`requiresTestDataConfirmation`) se agrega el checkbox
 *   auditado "Confirmo que son datos de prueba" (`onConfirmTestData`, POST
 *   `/api/attachments/{id}/confirm-test-data` -- ver el adapter) + un
 *   "Cancelar" que quita el adjunto (`onRemove`, mismo destino que el ×
 *   general, con la redacción específica de ANEXO §10/mockup sección D).
 * - `blocked` (N3)/`error` (fallo de extracción): causa específica siempre
 *   visible en `.attachment-chip__message`, `role="alert"` (a diferencia de
 *   `warning`, que usa `role="status"` -- N3/error son más urgentes: el
 *   adjunto ya es irrecuperable sin que el usuario actúe). El composer
 *   (`composer.tsx`) ya deshabilita "Enviar" mientras algún chip no sea
 *   `sendable` -- este componente hace visible la CAUSA de ese bloqueo.
 *
 * Gap documentado (no bloquea la verificación de 8.2, que no pide el %):
 * `add()` del adapter sube el archivo con un único `fetch()` (sin eventos
 * de progreso -- eso exigiría `XMLHttpRequest`, un cambio de transporte
 * fuera de alcance de esta tarea, ver el docstring de
 * `lib/chat/attachment-adapter.ts`), así que no hay un `{percent}` real
 * para `Chat.attachments.states.uploading`. `uploadingLabel()` usa el MISMO
 * texto del catálogo sin el placeholder de porcentaje en vez de inventar un
 * número -- spinner + "Subiendo…" siguen dejando el estado visible, nunca
 * silencioso, solo sin la granularidad de bytes que ANEXO §10 ejemplifica.
 */

export interface AttachmentChipStateLabels {
  /** "Subiendo… {percent}%" -- ver el docstring del módulo (gap de %). */
  uploading: string;
  processing: string;
  /** "Listo · {tokens} tokens" (Técnico/Admin). */
  readyTechAdmin: string;
  /** "Listo · usa {percent}% del espacio del mensaje" (Funcional). */
  readyFunctional: string;
  /** "Listo · incluye el {percent}% del archivo — tocá para ver qué verá
   * el agente" -- universal (no depende del rol), disparador de 8.3. */
  readyTruncated: string;
  warning: string;
  blocked: string;
  error: string;
}

export interface AttachmentChipLabels {
  states: AttachmentChipStateLabels;
  /** Plantilla `Quitar adjunto {file}` (mismo texto que ya usaba la lista
   * mínima de 8.1, `Chat.composer.removeAttachment`). */
  removeAttachment: string;
  /** Checkbox auditado N2 (`Chat.attachments.warnings.piiConfirmation`). */
  piiConfirmation: string;
  /** Acción "Cancelar" de la confirmación N2 (`Chat.attachments.warnings.piiCancel`) --
   * mismo destino que el × general (`onRemove`), redacción específica del
   * flujo de advertencia (ANEXO §10/mockup sección D). */
  piiCancel: string;
}

export interface AttachmentChipProps {
  item: AttachmentItem;
  /** Rol de la sesión de identidad -- decide la métrica de espacio del
   * estado `ready` (Requirement "Transparencia de espacio por capa de
   * rol"). Recibido como prop (no `useSession()` acá adentro) para que el
   * componente quede puro/testeable -- mismo criterio que
   * `session-taximeter.tsx`/`chat-header.tsx`. */
  role: Role;
  labels: AttachmentChipLabels;
  /** Click en el × general o en "Cancelar" (advertencia N2) -- `remove(id)`
   * del adapter. */
  onRemove: (id: string) => void;
  /** Checkbox "Confirmo que son datos de prueba" -- `confirmTestData(id)`
   * del adapter (POST auditado, ver su docstring). */
  onConfirmTestData: (id: string) => void;
  /** Punto de integración de la tarea 8.3 ("Ver lo que verá el agente"):
   * si se pasa, el texto de estado truncado se vuelve accionable. `undefined`
   * (el caso de hoy, `composer.tsx` todavía no lo pasa) deja el mismo texto
   * como contenido plano -- nunca un botón roto sin handler. */
  onOpenPreview?: (id: string) => void;
}

/** Mismo patrón `.replace`/`.split` que `composer.tsx::interpolateFileName`. */
function interpolateTemplate(template: string, key: string, value: string): string {
  return template.split(`{${key}}`).join(value);
}

/** "Subiendo…" sin el placeholder de porcentaje -- ver el docstring del
 * módulo ("Gap documentado"): no hay tracking real de progreso de bytes. */
function uploadingLabel(template: string): string {
  return template.replace("{percent}%", "").trim();
}

/** Texto del estado `ready` -- ver el docstring del módulo para el porqué
 * de cada rama (rol + truncado). */
function readyLabel(item: AttachmentItem, role: Role, states: AttachmentChipStateLabels): string {
  const percent = String(item.includedPercent ?? 0);
  if (item.truncated) {
    return interpolateTemplate(states.readyTruncated, "percent", percent);
  }
  if (role === "funcional") {
    return interpolateTemplate(states.readyFunctional, "percent", percent);
  }
  return interpolateTemplate(states.readyTechAdmin, "tokens", formatTokenCountBO(item.tokenCount ?? 0));
}

function statusLabel(item: AttachmentItem, role: Role, states: AttachmentChipStateLabels): string {
  switch (item.status) {
    case "uploading":
      return uploadingLabel(states.uploading);
    case "processing":
      return states.processing;
    case "ready":
      return readyLabel(item, role, states);
    case "warning":
      return states.warning;
    case "blocked":
      return states.blocked;
    case "error":
      return states.error;
    /* istanbul ignore next -- exhaustividad defensiva, `AttachmentChipStatus`
       no tiene más miembros hoy; si se agrega uno nuevo, TypeScript marca
       este `default` como inalcanzable y obliga a resolverlo acá. */
    default:
      return states.error;
  }
}

const SPINNER_STATUSES = new Set(["uploading", "processing"]);
const URGENT_STATUSES = new Set(["blocked", "error"]);

export function AttachmentChip({
  item,
  role,
  labels,
  onRemove,
  onConfirmTestData,
  onOpenPreview,
}: AttachmentChipProps) {
  const text = statusLabel(item, role, labels.states);
  const showSpinner = SPINNER_STATUSES.has(item.status);
  const isUrgent = URGENT_STATUSES.has(item.status);
  const showPiiConfirmation = item.status === "warning" && item.requiresTestDataConfirmation;
  const isTruncatedReady = item.status === "ready" && Boolean(item.truncated);

  return (
    <li
      className={`attachment-chip attachment-chip--${item.status}`}
      role="listitem"
      data-attachment-status={item.status}
    >
      <div className="attachment-chip__main">
        <span className="attachment-chip__name">{item.originalName}</span>
        <span className="attachment-chip__status" role={isUrgent ? "alert" : "status"}>
          {showSpinner ? <span className="attachment-chip__spinner" aria-hidden="true" /> : null}
          {isTruncatedReady && onOpenPreview ? (
            <button
              type="button"
              className="attachment-chip__status-trigger"
              onClick={() => onOpenPreview(item.id)}
            >
              {text}
            </button>
          ) : (
            text
          )}
        </span>
        {item.message ? <p className="attachment-chip__message">{item.message}</p> : null}
        {showPiiConfirmation ? (
          <div className="attachment-chip__confirm">
            <label className="check-row">
              <input
                type="checkbox"
                className="checkbox"
                checked={item.confirming}
                disabled={item.confirming}
                onChange={() => onConfirmTestData(item.id)}
              />
              <span>{labels.piiConfirmation}</span>
            </label>
            <button
              type="button"
              className="attachment-chip__cancel"
              onClick={() => onRemove(item.id)}
            >
              {labels.piiCancel}
            </button>
          </div>
        ) : null}
      </div>
      <button
        type="button"
        className="attachment-chip__remove"
        aria-label={interpolateTemplate(labels.removeAttachment, "file", item.originalName)}
        onClick={() => onRemove(item.id)}
      >
        ×
      </button>
    </li>
  );
}
