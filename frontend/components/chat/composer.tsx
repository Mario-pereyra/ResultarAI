"use client";

import {
  forwardRef,
  useImperativeHandle,
  useRef,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import { Button } from "@/components/ui/button";

export interface ComposerLabels {
  placeholder: string;
  textareaLabel: string;
  send: string;
  stop: string;
  hint: string;
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
   * ver tarea 7.3). */
  disabled?: boolean;
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
  { labels, disabled = false, streaming = false, value, onChange, onSubmit, onStop },
  ref,
) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useImperativeHandle(ref, () => ({
    focus: () => textareaRef.current?.focus(),
  }));

  function submit() {
    const trimmed = value.trim();
    if (!trimmed || disabled || streaming) return;
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

  const sendDisabled = !streaming && (disabled || value.trim().length === 0);

  return (
    <form className="chat-composer" onSubmit={handleFormSubmit}>
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
      <Button
        type={streaming ? "button" : "submit"}
        variant={streaming ? "secondary" : "primary"}
        disabled={streaming ? disabled : sendDisabled}
        onClick={streaming ? handleButtonClick : undefined}
      >
        {streaming ? labels.stop : labels.send}
      </Button>
      <p className="chat-composer__hint">{labels.hint}</p>
    </form>
  );
});
