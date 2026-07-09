"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Toast (tarea 4.5, d10-design-system-shell).
 * Envoltorio fino sobre `.toast-stack`/`.toast` (styles/components/toast.css,
 * portado verbatim de design/mockups/tokens.css §5.10). Sin CSS propio en
 * este archivo: toda apariencia viene de esas clases.
 *
 * API: hook `useToasts()` + `<ToastStack />` (design.md decisión 1: "hook o
 * API imperativa simple"), sin provider global — cada árbol que necesite
 * toasts llama al hook y renderiza su propio `<ToastStack />`.
 *
 * Textos: cero hardcodeados. `title`/`message` de cada toast los define quien
 * llama a `show()`; `label`/`dismissLabel` de `<ToastStack />` son props
 * requeridas que la sección 6 (catálogo i18n) cablea.
 */

export type ToastVariant = "info" | "success" | "warn" | "danger";

const VARIANT_CLASS: Record<ToastVariant, string> = {
  info: "toast",
  success: "toast toast--ok",
  warn: "toast toast--warn",
  danger: "toast toast--danger",
};

/**
 * design/DESIGN-SYSTEM.md §8.9: "auto-cierre 6s (info/ok) — warn/danger
 * persisten hasta cierre manual". La persistencia depende únicamente de la
 * variante: aunque el llamador pase `duration`, warn/danger nunca se
 * auto-cierran.
 */
const PERSISTENT_VARIANTS: readonly ToastVariant[] = ["warn", "danger"];
const DEFAULT_DURATION_MS = 6000;

function isPersistent(variant: ToastVariant): boolean {
  return PERSISTENT_VARIANTS.includes(variant);
}

export type ToastItem = {
  id: string;
  variant: ToastVariant;
  title: string;
  message?: string;
  /** ms antes del auto-cierre. Ignorado (persistente) en warn/danger. */
  duration?: number;
};

export type ShowToastInput = {
  variant: ToastVariant;
  title: string;
  message?: string;
  duration?: number;
};

let toastIdSeq = 0;
function nextToastId(): string {
  toastIdSeq += 1;
  return `toast-${toastIdSeq}`;
}

export type UseToastsResult = {
  toasts: ToastItem[];
  show: (input: ShowToastInput) => string;
  dismiss: (id: string) => void;
};

export function useToasts(): UseToastsResult {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const dismiss = useCallback((id: string) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const show = useCallback((input: ShowToastInput) => {
    const id = nextToastId();
    setToasts((current) => [
      ...current,
      {
        id,
        variant: input.variant,
        title: input.title,
        message: input.message,
        duration: input.duration ?? DEFAULT_DURATION_MS,
      },
    ]);
    return id;
  }, []);

  return { toasts, show, dismiss };
}

export type ToastStackProps = {
  toasts: ToastItem[];
  onDismiss: (id: string) => void;
  /** Nombre accesible del contenedor (landmark), ej. "Notificaciones". */
  label: string;
  /** aria-label del botón de cierre manual de cada toast. */
  dismissLabel: string;
};

export function ToastStack({ toasts, onDismiss, label, dismissLabel }: ToastStackProps) {
  return (
    <div className="toast-stack" role="region" aria-label={label}>
      {toasts.map((toast) => (
        <ToastCard key={toast.id} toast={toast} onDismiss={onDismiss} dismissLabel={dismissLabel} />
      ))}
    </div>
  );
}

type ToastCardProps = {
  toast: ToastItem;
  onDismiss: (id: string) => void;
  dismissLabel: string;
};

function ToastCard({ toast, onDismiss, dismissLabel }: ToastCardProps) {
  const persistent = isPersistent(toast.variant);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const remainingRef = useRef(toast.duration ?? DEFAULT_DURATION_MS);
  const startedAtRef = useRef(0);

  const clearTimer = useCallback(() => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const startTimer = useCallback(() => {
    if (persistent) return;
    startedAtRef.current = Date.now();
    timerRef.current = setTimeout(() => {
      onDismiss(toast.id);
    }, remainingRef.current);
  }, [onDismiss, persistent, toast.id]);

  useEffect(() => {
    startTimer();
    return clearTimer;
    // Temporizador de auto-cierre: se arma una sola vez al montar (y se
    // reinicia manualmente en el hover-pause de abajo), no en cada render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleMouseEnter() {
    if (persistent) return;
    remainingRef.current = Math.max(0, remainingRef.current - (Date.now() - startedAtRef.current));
    clearTimer();
  }

  function handleMouseLeave() {
    if (persistent) return;
    startTimer();
  }

  // design/DESIGN-SYSTEM.md §8.9: "aria-live='polite' (assertive solo
  // danger)". role="alert" (assertive implícito) vs role="status" (polite
  // implícito) por toast individual: evita alternar aria-live en un mismo
  // contenedor compartido, que varios lectores de pantalla no reevalúan bien.
  const role = toast.variant === "danger" ? "alert" : "status";

  return (
    <div
      className={VARIANT_CLASS[toast.variant]}
      role={role}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <span className="toast__icon" aria-hidden="true" />
      <div>
        <p className="toast__title">{toast.title}</p>
        {toast.message ? <p className="toast__msg">{toast.message}</p> : null}
      </div>
      <button type="button" className="toast__close" aria-label={dismissLabel} onClick={() => onDismiss(toast.id)}>
        <CloseIcon />
      </button>
    </div>
  );
}

function CloseIcon() {
  return (
    <svg viewBox="0 0 12 12" width="12" height="12" aria-hidden="true" focusable="false">
      <path d="M2 2l8 8M10 2l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" fill="none" />
    </svg>
  );
}
