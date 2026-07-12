"use client";

import {
  forwardRef,
  useImperativeHandle,
  useRef,
  type ChangeEvent,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import { Button } from "@/components/ui/button";
import { AttachmentChip, type AttachmentChipStateLabels } from "@/components/chat/attachment-chip";
import type { AttachmentItem } from "@/lib/chat/attachment-adapter";
import type { Role } from "@/lib/session-context";

export interface ComposerLabels {
  placeholder: string;
  textareaLabel: string;
  send: string;
  stop: string;
  hint: string;
  /** Botón "Adjuntar archivo" (d14-attachments, tarea 8.1) -- ver
   * `design/mockups/07-composer-attachments.html`, mismo texto literal. */
  attach: string;
  /** `aria-label` de la lista de adjuntos (`role="list"`, mismo mockup). */
  attachmentsListLabel: string;
  /** Plantilla `Quitar adjunto {file}` -- `{file}` se interpola con
   * `item.originalName` (`AttachmentChip`, que reutiliza este mismo texto). */
  removeAttachment: string;
  /** Textos de los estados del chip (tarea 8.2) -- ver
   * `AttachmentChip`/`Chat.attachments.states` (`messages/es.json`,
   * portados en la tarea 8.4). */
  attachmentStates: AttachmentChipStateLabels;
  /** Checkbox auditado N2 "Confirmo que son datos de prueba" (tarea 8.2,
   * `Chat.attachments.warnings.piiConfirmation`). */
  attachmentPiiConfirmation: string;
  /** "Cancelar" de la advertencia N2 (tarea 8.2,
   * `Chat.attachments.warnings.piiCancel`). */
  attachmentPiiCancel: string;
  /** "Ver lo que verá el agente" (tarea 8.3, `Chat.attachments.preview.action`)
   * -- ver `AttachmentChipLabels.previewAction`. */
  attachmentPreviewAction: string;
}

export interface ComposerHandle {
  /** Foco programático (tarea 3.5: click en una sugerencia de inicio le da
   * foco al composer después de precargar el texto). */
  focus: () => void;
}

export interface ComposerProps {
  labels: ComposerLabels;
  /** Deshabilita el composer entero (p. ej. sesión ajena/agente inactivo --
   * fuera de alcance de esta tarea, se deja el punto de integración listo,
   * ver tarea 7.3; también lo usa la tarea 6.2, cuota agotada). */
  disabled?: boolean;
  /** Motivo inline mostrado en lugar del hint normal mientras `disabled` es
   * `true` por un BLOQUEO (tarea 6.2, `design/VISTAS/02-chat.md` vista 10
   * §Interacciones: "QUOTA además deshabilita el composer con el motivo
   * inline -- es bloqueo, no solo error de turno"). `undefined` conserva
   * `labels.hint` de siempre (p. ej. mientras se edita un mensaje, tarea
   * 5.5, que deshabilita el composer sin necesitar un motivo propio). */
  disabledReason?: string;
  /** `true` mientras el turno del agente está en streaming (`use-turn-stream.ts`):
   * el botón pasa a "Detener" y el textarea se bloquea (doble envío, vista 05:
   * "bloqueado durante el round-trip"). */
  streaming?: boolean;
  /** Texto controlado por quien llama (`chat-content.tsx`): permite que la
   * tarea 3.5 precargue una sugerencia sin que el composer tenga que conocer
   * el origen del texto. */
  value: string;
  onChange: (value: string) => void;
  /** Enter (sin Shift) con texto no vacío, o click en "Enviar". */
  onSubmit: (text: string) => void;
  /** Click en "Detener" durante el streaming. */
  onStop: () => void;
  /** Adjuntos del borrador actual (d14-attachments, tarea 8.1) --
   * `useAttachmentAdapter().attachments` de `chat-content.tsx`. Cada uno se
   * renderiza como un `AttachmentChip` (tarea 8.2): estados
   * subiendo→procesando→listo/advertencia/bloqueado/error con causa
   * específica, nunca silencioso -- ver el docstring de `AttachmentChip`. */
  attachments: AttachmentItem[];
  /** Rol de la sesión de identidad -- decide la métrica de espacio del chip
   * `listo` (tarea 8.2, Requirement "Transparencia de espacio por capa de
   * rol"). Recibido como prop (no `useSession()` acá adentro), mismo
   * criterio que el resto de `components/chat/*`. */
  role: Role;
  /** Click en "Adjuntar archivo" + selección en el `<input type="file">`
   * oculto -- una llamada a `add()` del adapter por archivo elegido. */
  onAttachFiles: (files: File[]) => void;
  /** Click en "Quitar" (× general) o "Cancelar" (advertencia N2) de un
   * adjunto -- `remove(id)` del adapter. */
  onRemoveAttachment: (id: string) => void;
  /** Checkbox "Confirmo que son datos de prueba" del chip en `warning`
   * (tarea 8.2) -- `confirmTestData(id)` del adapter (POST auditado, ver su
   * docstring en `lib/chat/attachment-adapter.ts`). */
  onConfirmAttachmentTestData: (id: string) => void;
  /** Punto de integración de la tarea 8.3 ("Ver lo que verá el agente") --
   * ver el docstring de `AttachmentChip.onOpenPreview`. `undefined` hasta
   * que 8.3 implemente el panel. */
  onOpenAttachmentPreview?: (id: string) => void;
  /** `true` cuando ya se alcanzó el máximo de adjuntos por mensaje (ANEXO §9,
   * default 5) -- deshabilita el botón "Adjuntar archivo" de forma
   * PROACTIVA; el adapter igual rechaza con el texto §10 "Demasiados
   * adjuntos" si de todos modos llega una subida de más (defensa en
   * profundidad, mismo criterio que el resto del pipeline). Default `false`. */
  attachDisabled?: boolean;
}

/**
 * Composer del chat (d13-chat-conversacion, tarea 3.4, `design/VISTAS/02-chat.md`
 * vista 05): Enter envía / Shift+Enter salto de línea, botón enviar↔detener
 * según el estado de streaming, deshabilitado con el composer vacío, hint
 * visible debajo del textarea. Reemplaza a `composer-placeholder.tsx` (tarea 3.1).
 *
 * El textarea NO usa el componente `Textarea` del design system (que exige un
 * `<label>` visible vía `Field`): la vista 05 no muestra ningún label sobre el
 * composer, solo el placeholder ("Escribile a {agent}…") -- se mantiene el
 * mismo patrón que `composer-placeholder.tsx` (clase `.textarea` + `aria-label`)
 * para lograr la MISMA apariencia sin un label visible espurio. `Button` sí se
 * reutiliza tal cual del design system.
 */
export const Composer = forwardRef<ComposerHandle, ComposerProps>(function Composer(
  {
    labels,
    disabled = false,
    disabledReason,
    streaming = false,
    value,
    onChange,
    onSubmit,
    onStop,
    attachments,
    role,
    onAttachFiles,
    onRemoveAttachment,
    onConfirmAttachmentTestData,
    onOpenAttachmentPreview,
    attachDisabled = false,
  },
  ref,
) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useImperativeHandle(ref, () => ({
    focus: () => textareaRef.current?.focus(),
  }));

  function handleFileInputChange(event: ChangeEvent<HTMLInputElement>) {
    const files = event.target.files;
    if (files && files.length > 0) onAttachFiles(Array.from(files));
    // Limpia el valor del input -- sin esto, re-seleccionar EL MISMO archivo
    // (mismo nombre) no dispara `onChange` una segunda vez.
    event.target.value = "";
  }

  // ANEXO §6/§10 ("nunca... silencioso", spec `attachments-ui`): mientras
  // algún adjunto no sea `sendable` (subiendo/procesando/bloqueado/con error/
  // PII sin confirmar -- ver `is_sendable` en
  // `resultarai/app/attachments/data_scan.py`, que es la MISMA condición que
  // ya calcula el backend en `GET /api/attachments/{id}`), el envío queda
  // deshabilitado -- nunca se manda el mensaje "de todos modos" excluyendo en
  // silencio el adjunto todavía no listo. Quitar el adjunto problemático
  // (`onRemoveAttachment`) libera el envío sin él.
  const hasUnsendableAttachment = attachments.some((item) => !item.sendable);

  function submit() {
    const trimmed = value.trim();
    if (!trimmed || disabled || streaming || hasUnsendableAttachment) return;
    onSubmit(trimmed);
  }

  function handleFormSubmit(event: FormEvent) {
    event.preventDefault();
    submit();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }

  function handleButtonClick() {
    if (streaming) onStop();
    // Sin `streaming`: el botón es `type="submit"`, el `onSubmit` del <form>
    // ya se encarga (evita disparar el envío dos veces).
  }

  const sendDisabled =
    !streaming && (disabled || value.trim().length === 0 || hasUnsendableAttachment);
  // Tarea 6.2: el motivo de bloqueo SOLO reemplaza el hint mientras el
  // composer está efectivamente deshabilitado -- si `disabled` se libera
  // (p. ej. se resuelve el bloqueo) el hint normal vuelve solo, sin que el
  // caller tenga que limpiar `disabledReason` en sincronía.
  const showBlockedReason = disabled && Boolean(disabledReason);

  const attachButtonDisabled = disabled || streaming || attachDisabled;

  return (
    <form className="chat-composer" onSubmit={handleFormSubmit}>
      {attachments.length > 0 ? (
        // Chips reales (d14-attachments, tarea 8.2) -- ver el docstring de
        // `AttachmentChip` para el detalle de cada estado/causa. Reemplaza la
        // lista mínima de texto que dejó la tarea 8.1.
        <ul className="chat-composer__attachments" role="list" aria-label={labels.attachmentsListLabel}>
          {attachments.map((item) => (
            <AttachmentChip
              key={item.id}
              item={item}
              role={role}
              labels={{
                states: labels.attachmentStates,
                removeAttachment: labels.removeAttachment,
                piiConfirmation: labels.attachmentPiiConfirmation,
                piiCancel: labels.attachmentPiiCancel,
                previewAction: labels.attachmentPreviewAction,
              }}
              onRemove={onRemoveAttachment}
              onConfirmTestData={onConfirmAttachmentTestData}
              onOpenPreview={onOpenAttachmentPreview}
            />
          ))}
        </ul>
      ) : null}
      <textarea
        ref={textareaRef}
        className="textarea chat-composer__textarea"
        aria-label={labels.textareaLabel}
        placeholder={labels.placeholder}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled || streaming}
        rows={1}
      />
      <input
        ref={fileInputRef}
        type="file"
        multiple
        className="chat-composer__file-input"
        onChange={handleFileInputChange}
        // Sin `accept` a propósito -- ver el docstring de
        // `lib/chat/attachment-adapter.ts`: el allowlist real es config de
        // instancia server-side (ANEXO §9), duplicarlo acá lo haría
        // divergir en silencio.
        hidden
      />
      <Button
        type="button"
        variant="ghost"
        size="sm"
        disabled={attachButtonDisabled}
        onClick={() => fileInputRef.current?.click()}
      >
        {labels.attach}
      </Button>
      <Button
        type={streaming ? "button" : "submit"}
        variant={streaming ? "secondary" : "primary"}
        disabled={streaming ? disabled : sendDisabled}
        onClick={streaming ? handleButtonClick : undefined}
      >
        {streaming ? labels.stop : labels.send}
      </Button>
      <p
        className={
          showBlockedReason ? "chat-composer__hint chat-composer__hint--blocked" : "chat-composer__hint"
        }
      >
        {showBlockedReason ? disabledReason : labels.hint}
      </p>
    </form>
  );
});
