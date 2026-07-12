"use client";

import { Modal } from "@/components/ui/modal";
import { useAttachmentPreview } from "@/lib/chat/attachment-preview";
import { formatTokenCountBO } from "@/lib/format-bo";
import type { AttachmentItem } from "@/lib/chat/attachment-adapter";
import type { Role } from "@/lib/session-context";

/**
 * Panel "Ver lo que verá el agente" (d14-attachments, tarea 8.3, vista
 * `07-composer` / `design/mockups/07-composer-attachments.html` sección C
 * "Vista previa de extracción"). Fuente normativa:
 * `design/ANEXO-ATTACHMENTS.md` §3.4 ("Vista previa de extracción — patrón
 * de transparencia") y §10 (textos de UI) + spec
 * `openspec/changes/d14-attachments/specs/attachments-ui/spec.md`
 * (Requirements "Vista previa 'Ver lo que verá el agente'" y "Transparencia
 * de espacio por capa de rol").
 *
 * Envoltorio de negocio sobre `Modal` (design system, `components/ui/modal.tsx`):
 * reutiliza su trampa de foco + cierre por Escape + `role="dialog"`/
 * `aria-modal` + retorno de foco al disparador -- mismo patrón ya validado
 * por el escenario "Modal con trampa de foco" de d10-design-system-shell,
 * sin reimplementar nada de eso acá. Es el primer consumidor de `Modal`
 * fuera del styleguide.
 *
 * Puramente presentacional (mismo criterio que `AttachmentChip`): el
 * `fetch` de la extracción vive en `useAttachmentPreview`
 * (`lib/chat/attachment-preview.ts`) -- este componente solo decide qué
 * mostrar según su `status`.
 *
 * Se dispara desde `AttachmentChip.onOpenPreview` (tarea 8.2) vía
 * `chat-content.tsx`, que resuelve el `AttachmentItem` completo a partir del
 * id LOCAL que ese callback entrega (mismo id que `remove()`) -- por eso
 * `item` acá es el `AttachmentItem`, no un id suelto: la línea de
 * metadatos necesita `item.originalName`, y el fetch necesita
 * `item.attachmentId` (el id REAL del backend).
 *
 * ## Capa por rol (Requirement "Transparencia de espacio por capa de rol",
 * escenario "mismo adjunto, métricas por rol")
 *
 * La línea de métrica reutiliza EXACTAMENTE las mismas plantillas que ya
 * usa el chip en estado `listo` (`labels.metricTechAdmin`/`metricFunctional`,
 * espejo de `Chat.attachments.states.readyTechAdmin`/`readyFunctional`,
 * `messages/es.json`) -- mismo texto literal del ANEXO §10 ("Listo · 8.200
 * tokens" / "Listo · usa 34% del espacio del mensaje"): Funcional y
 * Técnico/Admin ven la MISMA redacción ya validada en el chip (8.2), ahora
 * también en el panel, en vez de inventar una fórmula nueva.
 *
 * A diferencia del chip (que lee `tokenCount`/`includedPercent` cacheados
 * del último poll de `GET /api/attachments/{id}`), acá se usan los valores
 * DEL PROPIO `GET /api/attachments/{id}/preview` (`useAttachmentPreview`) --
 * la fuente más fresca/autoritativa, coherente con el texto que se muestra
 * al lado.
 */

export interface AttachmentPreviewPanelLabels {
  /** Título del panel (`Chat.attachments.preview.title`): "Esto es
   * exactamente lo que recibirá el agente". */
  title: string;
  /** `aria-label` del botón de cierre (ícono-only, mismo patrón que
   * `ModalProps.closeLabel`). */
  closeLabel: string;
  /** Pie PERMANENTE (`Chat.attachments.preview.footer`): "Contenido
   * extraído automáticamente — puede diferir del documento original." --
   * se muestra SIEMPRE, en cualquier estado con datos, nunca condicional. */
  footer: string;
  /** Texto mientras `useAttachmentPreview` sigue en `loading`. */
  loading: string;
  /** Texto si el fetch falla o el adjunto todavía no tiene extracción
   * disponible (409 `extraction_not_ready`) -- nunca un panel en blanco. */
  error: string;
  /** "Listo · {tokens} tokens" (Técnico/Admin) -- mismo texto que
   * `AttachmentChipStateLabels.readyTechAdmin`. */
  metricTechAdmin: string;
  /** "Listo · usa {percent}% del espacio del mensaje" (Funcional) -- mismo
   * texto que `AttachmentChipStateLabels.readyFunctional`. */
  metricFunctional: string;
  /** `Chat.attachments.errors.truncatedPreview`: aviso sobre las secciones
   * omitidas cuando la extracción viene truncada (escenario "vista previa
   * de un adjunto truncado") -- interpola `{percent}`. */
  truncatedNotice: string;
}

export interface AttachmentPreviewPanelProps {
  /** Adjunto seleccionado (el mismo objeto que expone
   * `useAttachmentAdapter().attachments`) -- `null` cierra el panel. */
  item: AttachmentItem | null;
  onClose: () => void;
  /** Rol de la sesión -- decide la métrica de la línea de metadatos
   * (Requirement "Transparencia de espacio por capa de rol"). */
  role: Role;
  labels: AttachmentPreviewPanelLabels;
}

/** Mismo patrón `.split`/`.join` que `attachment-chip.tsx::interpolateTemplate`. */
function interpolate(template: string, key: string, value: string): string {
  return template.split(`{${key}}`).join(value);
}

/** Línea de métrica por rol -- ver el docstring del módulo. Ignora a
 * propósito la variante "truncado" del chip (`readyTruncated`): acá el
 * truncado se anuncia aparte, como un aviso propio (`truncatedNotice`), no
 * mezclado con la métrica de espacio. */
function metricLabel(
  role: Role,
  tokenCount: number,
  includedPercent: number,
  labels: AttachmentPreviewPanelLabels,
): string {
  if (role === "funcional") {
    return interpolate(labels.metricFunctional, "percent", String(includedPercent));
  }
  return interpolate(labels.metricTechAdmin, "tokens", formatTokenCountBO(tokenCount));
}

export function AttachmentPreviewPanel({ item, onClose, role, labels }: AttachmentPreviewPanelProps) {
  const attachmentId = item?.attachmentId ?? null;
  const state = useAttachmentPreview(attachmentId);
  // `item` presente pero sin `attachmentId` todavía (caso extremo, ver el
  // docstring de `useAttachmentPreview`): el hook queda en `idle` porque
  // nunca arranca el fetch -- se trata igual que un error, nunca un panel
  // vacío silencioso.
  const effectiveStatus = item !== null && attachmentId === null ? "error" : state.status;

  return (
    <Modal
      open={item !== null}
      onClose={onClose}
      title={labels.title}
      closeLabel={labels.closeLabel}
      footer={<p className="attachment-preview__foot">{labels.footer}</p>}
    >
      {effectiveStatus === "loading" || effectiveStatus === "idle" ? (
        <p className="attachment-preview__status">{labels.loading}</p>
      ) : null}
      {effectiveStatus === "error" ? (
        <p className="attachment-preview__status" role="alert">
          {labels.error}
        </p>
      ) : null}
      {effectiveStatus === "ready" && state.status === "ready" ? (
        <>
          <p className="attachment-preview__meta">
            {item?.originalName} ·{" "}
            {metricLabel(role, state.payload.tokenCount, state.payload.includedPercent, labels)}
          </p>
          {state.payload.truncated ? (
            <p className="attachment-preview__notice" role="status">
              {interpolate(labels.truncatedNotice, "percent", String(state.payload.includedPercent))}
            </p>
          ) : null}
          <pre className="attachment-preview__body">{state.payload.text}</pre>
        </>
      ) : null}
    </Modal>
  );
}
