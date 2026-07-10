"use client";

import { useState, type FormEvent, type KeyboardEvent } from "react";
import { Button } from "@/components/ui/button";

export interface ComposerPlaceholderLabels {
  placeholder: string;
  send: string;
  sending: string;
  hint: string;
  textareaLabel: string;
}

export interface ComposerPlaceholderProps {
  labels: ComposerPlaceholderLabels;
  /** Deshabilita el composer entero (p. ej. sesión ajena/agente inactivo -- fuera de
   * alcance de esta tarea, se deja el punto de integración listo). */
  disabled?: boolean;
  /** Turno en curso: deshabilita el envío (doble envío) y muestra el label "Enviando…". */
  sending?: boolean;
  onSubmit: (text: string) => void;
}

/**
 * Placeholder MÍNIMO del composer (tarea 3.1: "la página renderiza la
 * columna y un placeholder simple del composer con textarea+submit
 * funcional mínimo para que el flujo sea probable end-to-end").
 *
 * La tarea 3.4 lo reemplaza por el composer completo: botón enviar↔detener
 * según streaming (acá no hay botón "Detener" -- cancelar es 3.4), hint de
 * estado de espacio, adjuntos (3.7/d14). Acá solo Enter-envía/Shift+Enter
 * salto de línea y un botón deshabilitado con el textarea vacío/enviando,
 * lo mínimo para accionar `use-turn-stream.ts` de punta a punta.
 */
export function ComposerPlaceholder({
  labels,
  disabled = false,
  sending = false,
  onSubmit,
}: ComposerPlaceholderProps) {
  const [value, setValue] = useState("");

  function submit() {
    const trimmed = value.trim();
    if (!trimmed || disabled || sending) return;
    onSubmit(trimmed);
    setValue("");
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    submit();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }

  return (
    <form className="chat-composer" onSubmit={handleSubmit}>
      <textarea
        className="textarea chat-composer__textarea"
        aria-label={labels.textareaLabel}
        placeholder={labels.placeholder}
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled || sending}
        rows={1}
      />
      <Button
        type="submit"
        variant="primary"
        disabled={disabled || sending || value.trim().length === 0}
        loading={sending}
      >
        {sending ? labels.sending : labels.send}
      </Button>
      <p className="chat-composer__hint">{labels.hint}</p>
    </form>
  );
}
