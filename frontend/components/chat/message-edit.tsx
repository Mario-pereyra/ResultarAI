"use client";

import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { Button } from "@/components/ui/button";

/** Umbral del aviso de re-proceso (vista 09 §Datos): "Aparece solo si N ≥ 3
 * (editar el último mensaje no lo necesita)" -- mismo número que el
 * requirement "Aviso suave de regeneración costosa al editar lejos" de
 * `specs/chat-experience/spec.md`. */
const REPROCESS_WARNING_THRESHOLD = 3;

export interface MessageEditLabels {
  /** `aria-label` del botón lápiz "Editar" en reposo (`Chat.edit.action`,
   * `EditMessageButton` más abajo). */
  action: string;
  /** `aria-label` del textarea de edición (`Chat.edit.textareaLabel`). */
  textareaLabel: string;
  cancel: string;
  confirm: string;
  /**
   * Plantilla con placeholder literal `{n}` para N=1 (categoría ICU "one").
   * Caso borde que HOY nunca se renderiza -- el aviso solo aparece desde
   * `REPROCESS_WARNING_THRESHOLD` (3) -- pero se resuelve correctamente para
   * no dejar la pluralización rota si ese umbral cambiara. Ver el docstring
   * de `MessageEdit` para por qué la categoría se elige con
   * `Intl.PluralRules` en vez de vía `next-intl` (que exigiría un
   * `NextIntlClientProvider` en cada test que monte este árbol).
   */
  reprocessWarningOne: string;
  /** Plantilla con placeholder literal `{n}` para N>=2 (categoría ICU
   * "other" -- el ÚNICO caso real hoy, dado el umbral de 3). */
  reprocessWarningOther: string;
}

export interface MessageEditProps {
  /** Texto original del mensaje, PRECARGADO en el textarea al activar la
   * edición (vista 09 §Estados: "Editando"). */
  originalText: string;
  /** N = mensajes posteriores al editado en su rama VISIBLE, ya calculado
   * por el caller con `countMessagesAfter` (`lib/chat/session-tree.ts`) --
   * este componente es puramente presentacional, no conoce el árbol. Ver el
   * docstring de esa función para la relación con `reprocessed_count`
   * (decisión 8 de `design.md`). */
  reprocessCount: number;
  /** `true` mientras se está creando la rama (`POST` con `edits_message_id`
   * en vuelo, vista 09 §Estados "Creando rama"): "Crear rama" pasa a
   * loading y el textarea se deshabilita, pero el texto tipeado NUNCA se
   * pierde (sigue montado) -- cubre también el caso de error de la vista
   * (el textarea persiste porque el caller no desmonta este componente al
   * fallar, solo vuelve `pending` a `false`). */
  pending?: boolean;
  labels: MessageEditLabels;
  /** Confirmar ("Crear rama"): el caller es quien invoca `sendTurn` con
   * `edits_message_id` -- este componente no conoce `use-turn-stream`. */
  onConfirm: (text: string) => void;
  /** Cancelar (botón o Esc): vuelve a la burbuja de lectura SIN llamar a
   * `onConfirm` ni a ningún endpoint. */
  onCancel: () => void;
}

/**
 * Elige la categoría de plural ICU ("one"/"other") con la misma tabla CLDR
 * que usa el motor de `next-intl`/ICU MessageFormat, sin necesitar el hook
 * `useTranslations` (que exigiría envolver cada árbol que monte este
 * componente -- incluido `chat-content.tsx` completo -- en un
 * `NextIntlClientProvider` en los tests). `n` es un dato de runtime del
 * cliente (cuántos mensajes hay que reprocesar), por eso la resolución no
 * puede hacerse al construir `labels` server-side como el resto de las
 * strings de este módulo (`app/(shell)/chat/labels.ts`).
 */
function pluralWarningText(labels: MessageEditLabels, n: number): string {
  const category = new Intl.PluralRules("es").select(n);
  const template = category === "one" ? labels.reprocessWarningOne : labels.reprocessWarningOther;
  return template.replace("{n}", String(n));
}

/**
 * Edición inline de un mensaje de USUARIO (tarea 5.5 de d13-chat-conversacion,
 * `design/VISTAS/02-chat.md` vista 09 §Layout/§Estados "Editando",
 * `design/FLUJOS.md` Flujo G paso 3). Reemplaza la burbuja de lectura del
 * mensaje mientras está activa (`chat-content.tsx` la monta vía el render-prop
 * `renderMessageEdit` de `MessageColumn`, mismo patrón que
 * `renderVersionSelector`/`renderEscalation`).
 *
 * Componente CONTROLADO y presentacional: mantiene el texto tipeado en
 * estado local (arranca en `originalText`) pero no sabe nada de sesiones,
 * ramas ni streaming -- `onConfirm`/`onCancel` son la única superficie hacia
 * el caller. El aviso "reprocesa N mensajes" (vista 09 §Datos) es SOLO
 * informativo: nunca deshabilita "Crear rama" (requirement "Aviso suave de
 * regeneración costosa al editar lejos", `specs/chat-experience/spec.md` --
 * "el aviso SHALL solo informar, sin impedir la operación").
 */
export function MessageEdit({
  originalText,
  reprocessCount,
  pending = false,
  labels,
  onConfirm,
  onCancel,
}: MessageEditProps) {
  const [text, setText] = useState(originalText);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Foco automático al activar la edición (vista 09 §Estados: la burbuja
  // MUTA a textarea -- el usuario ya venía de hacer click en "Editar", así
  // que llevar el foco acá es continuar su gesto, no robarlo). Vía `ref` +
  // efecto (no el atributo `autoFocus`) para no depender de
  // `jsx-a11y/no-autofocus`; corre una sola vez al montar este componente
  // (se desmonta y remonta entero al cancelar/reabrir la edición).
  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // Vista 09 §Estados: "Esc cancela".
    if (event.key === "Escape") {
      event.preventDefault();
      onCancel();
    }
  }

  const showWarning = reprocessCount >= REPROCESS_WARNING_THRESHOLD;
  const trimmed = text.trim();

  return (
    <div className="edit-box">
      <textarea
        ref={textareaRef}
        className="textarea"
        aria-label={labels.textareaLabel}
        rows={2}
        value={text}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={handleKeyDown}
        disabled={pending}
      />
      {showWarning ? (
        <p className="edit-warn" role="status">
          <span className="edit-warn__icon" aria-hidden="true">
            ⚠
          </span>
          {pluralWarningText(labels, reprocessCount)}
        </p>
      ) : null}
      <div className="edit-actions">
        <Button variant="secondary" size="sm" disabled={pending} onClick={onCancel}>
          {labels.cancel}
        </Button>
        <Button
          variant="primary"
          size="sm"
          loading={pending}
          disabled={trimmed.length === 0}
          onClick={() => onConfirm(trimmed)}
        >
          {labels.confirm}
        </Button>
      </div>
    </div>
  );
}

export interface EditMessageButtonProps {
  label: string;
  onClick: () => void;
}

/**
 * Botón "Editar" (lápiz) sobre un mensaje de usuario en reposo (vista 09
 * §Interacciones: "aparece en hover y focus del mensaje propio"). La
 * visibilidad la controla `.edit-btn`/`.msg-user__row:hover`/`:focus-within`
 * en `styles/components/chat.css` -- este componente siempre está en el DOM,
 * nunca la oculta con JS (así el foco por teclado lo revela igual que el
 * hover, sin lógica de estado extra).
 */
export function EditMessageButton({ label, onClick }: EditMessageButtonProps) {
  return (
    <button type="button" className="edit-btn" aria-label={label} onClick={onClick}>
      <span aria-hidden="true">✎</span>
    </button>
  );
}
