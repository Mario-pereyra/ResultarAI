"use client";

import { useEffect, useRef, type PointerEvent as ReactPointerEvent } from "react";

/** Umbral por defecto en ms (tarea 8.2 de d13-chat-conversacion,
 * `design/VISTAS/02-chat.md` vista 12 §Móvil: "acciones en menú por
 * long-press"). El prompt de la tarea fija "~500ms"; sin otra fuente más
 * específica en `design/`, se usa ese mismo valor. */
const DEFAULT_LONG_PRESS_DELAY_MS = 500;

export interface UseLongPressOptions {
  /** Se invoca cuando el pointer permanece presionado `delayMs` sin
   * soltarse, salir del elemento ni cancelarse. */
  onLongPress: () => void;
  /** Umbral en ms antes de considerar el gesto un long-press. Default 500. */
  delayMs?: number;
}

export interface UseLongPressHandlers {
  onPointerDown: (event: ReactPointerEvent) => void;
  onPointerUp: (event: ReactPointerEvent) => void;
  onPointerLeave: (event: ReactPointerEvent) => void;
  onPointerCancel: (event: ReactPointerEvent) => void;
}

export interface UseLongPressResult {
  /** Handlers de pointer para esparcir sobre el elemento que reacciona al
   * press-and-hold (p. ej. `<TableRow {...handlers}>`, ver
   * `app/(shell)/chat/history-row.tsx`). */
  handlers: UseLongPressHandlers;
  /**
   * `true` si el gesto que acaba de terminar fue un long-press -- el caller
   * la consulta desde SU PROPIO `onClick` para suprimir la acción normal de
   * click que el navegador dispara igual tras soltar (p. ej. no navegar si
   * el long-press ya abrió un menú). Consumirla la resetea a `false` para
   * el próximo gesto -- ver el docstring completo más abajo.
   */
  consumeLongPress: () => boolean;
}

/**
 * Long-press genérico por `PointerEvent` (tarea 8.2 de d13-chat-conversacion,
 * `design/VISTAS/02-chat.md` vista 12 §Móvil). Una sola API para
 * mouse/touch/pen (`PointerEvent` los unifica, sin duplicar lógica
 * touchstart/touchend vs mousedown/mouseup) y mockeable en tests con
 * `vi.useFakeTimers()` disparando `pointerDown` -> avanzar el reloj ->
 * `pointerUp` a mano, sin depender de un dispositivo táctil real (que
 * jsdom no simula).
 *
 * MECANISMO DE SUPRESIÓN DEL CLICK POSTERIOR: en un navegador real, soltar
 * el pointer tras un press-and-hold igual dispara un evento `click` (el
 * gesto completo mousedown+mouseup o touchstart+touchend sigue siendo un
 * "click" desde la perspectiva del DOM, sin importar cuánto duró). Sin
 * distinguirlo, un long-press que abre el menú de acciones NAVEGARÍA
 * ADEMÁS a la fila (doble efecto). Por eso este hook no intercepta el
 * click por sí solo (evitaría acoplarse a qué hace ESE click, que varía
 * por caller) -- expone `consumeLongPress()`: el caller la llama al
 * INICIO de su propio `onClick` y corta ahí si devuelve `true`. Ver
 * `app/(shell)/chat/history-row.tsx` para el caso de uso real.
 *
 * Soltar antes del umbral (`onPointerUp`) o salir del elemento
 * (`onPointerLeave`)/cancelar (`onPointerCancel`, p. ej. un scroll que
 * empieza a mitad de la presión) cancela el temporizador sin disparar
 * `onLongPress` -- el click normal sigue su curso sin que
 * `consumeLongPress()` lo bloquee.
 *
 * ORDEN EN EL CALLER: si `onLongPress` abre un menú SIMULANDO un click
 * sobre un botón anidado (ver `HistoryRowActionsHandle.openMenu` en
 * `app/(shell)/chat/history-row-actions.tsx`), ESE click sintético también
 * burbujea hasta el elemento con estos handlers. El caller debe resolver
 * primero cualquier guard propio de "el click vino de un control anidado"
 * (p. ej. `event.target.closest("button")`) y llamar a `consumeLongPress()`
 * DESPUÉS -- si el orden se invierte, ese primer click sintético "gasta" el
 * flag y el click de compatibilidad real que el navegador dispara tras
 * soltar el dedo (fuera de cualquier botón) deja de estar protegido. Ver
 * `HistoryTableRow.handleClick` para el caso real.
 */
export function useLongPress({
  onLongPress,
  delayMs = DEFAULT_LONG_PRESS_DELAY_MS,
}: UseLongPressOptions): UseLongPressResult {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const firedRef = useRef(false);
  // Vía ref actualizada en un efecto (nunca escrita durante el render --
  // mismo criterio ya documentado en `lib/chat/use-retry-backoff.ts` para
  // `onRetryRef`): un caller que pasa una función nueva en cada render
  // (el caso común, `onLongPress={() => actionsRef.current?.openMenu()}`)
  // no reinicia el temporizador en vuelo.
  const onLongPressRef = useRef(onLongPress);
  useEffect(() => {
    onLongPressRef.current = onLongPress;
  }, [onLongPress]);

  function clearTimer() {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }

  function handlePointerDown() {
    clearTimer();
    // Un gesto NUEVO no hereda el flag de un gesto anterior que nunca fue
    // consumido (p. ej. si el click de compatibilidad del navegador tras un
    // long-press previo nunca llegó a dispararse) -- sin este reset, un tap
    // corto y genuino posterior podría quedar suprimido por error.
    firedRef.current = false;
    timerRef.current = setTimeout(() => {
      timerRef.current = null;
      firedRef.current = true;
      onLongPressRef.current();
    }, delayMs);
  }

  function handlePointerUp() {
    clearTimer();
  }

  function handlePointerLeave() {
    clearTimer();
  }

  function handlePointerCancel() {
    clearTimer();
  }

  function consumeLongPress(): boolean {
    if (!firedRef.current) return false;
    firedRef.current = false;
    return true;
  }

  // Limpieza al desmontar: un temporizador en vuelo sobre un componente ya
  // desmontado no debe disparar `onLongPress` (evita un `openMenu()` sobre
  // un ref que ya no apunta a nada montado).
  useEffect(() => clearTimer, []);

  return {
    handlers: {
      onPointerDown: handlePointerDown,
      onPointerUp: handlePointerUp,
      onPointerLeave: handlePointerLeave,
      onPointerCancel: handlePointerCancel,
    },
    consumeLongPress,
  };
}
