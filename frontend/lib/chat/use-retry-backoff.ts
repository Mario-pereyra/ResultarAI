"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Pasos de backoff en segundos (tarea 6.1 de d13-chat-conversacion,
 * `design/VISTAS/02-chat.md` vista 10 §Estados: "GATEWAY: countdown
 * decreciente; al llegar a 0 reintenta solo; backoff visible (5→15→60 s)").
 * El último paso es el tope: cualquier intento por encima de la cantidad de
 * pasos se queda ahí (no crece indefinidamente).
 */
const DEFAULT_BACKOFF_STEPS_SECONDS: readonly number[] = [5, 15, 60];

export interface UseRetryBackoffOptions {
  /**
   * Intento consecutivo actual (1-based) para el turno pendiente: `1` usa el
   * primer paso del backoff, `2` el segundo, etc. -- el caller (
   * `GatewayOfflineCard`/`chat-content.tsx`) lo incrementa en cada fallo
   * `GATEWAY_OFFLINE` nuevo sobre el MISMO turno.
   *
   * IMPORTANTE: este hook NO reacciona a que `attempt` cambie de valor en el
   * MISMO componente montado -- lee el valor una sola vez, al montar (mismo
   * criterio que un `useState(() => ...)` de inicialización perezosa). El
   * caller es responsable de remontar el componente que usa este hook con
   * un `key={attempt}` cuando el intento avanza (ver `GatewayOfflineCard` en
   * `chat-content.tsx`): eso evita depender de un efecto que "reajuste"
   * estado derivado de una prop (patrón desaconsejado, ver
   * https://react.dev/learn/you-might-not-need-an-effect#adjusting-some-state-when-a-prop-changes)
   * y le da a cada intento su propio countdown limpio, sin arrastrar el
   * guard de "ya disparé" del intento anterior.
   */
  attempt: number;
  /**
   * Se invoca UNA sola vez, ya sea porque el countdown llegó a 0 o porque
   * se llamó a `retryNow()`. El caller decide qué hacer (reenviar el turno)
   * -- este hook no conoce el chat.
   */
  onRetry: () => void;
  /** Pasos de backoff en segundos. Default `[5, 15, 60]` (vista 10). */
  steps?: readonly number[];
}

export interface UseRetryBackoffResult {
  /** Segundos restantes del countdown en curso (0 si no hay ninguno activo). */
  secondsRemaining: number;
  /**
   * Dispara el reintento YA, cancela el countdown en curso. No-op si este
   * intento ya disparó (por countdown o por una llamada previa) --
   * garantiza un único reintento por intento (vista 10 §Estados:
   * "Reintentando ... la tarjeta no se duplica -- un solo reintento en
   * vuelo").
   */
  retryNow: () => void;
}

/**
 * Countdown de reintento con backoff (tarea 6.1 de d13-chat-conversacion,
 * `design/VISTAS/02-chat.md` vista 10 §Estados "GATEWAY"). Traduce
 * `attempt` al paso de backoff correspondiente y cuenta hacia atrás en
 * segundos reales (`setInterval`, mockeable con `vi.useFakeTimers()` en los
 * tests) desde que el componente que lo usa se MONTA -- ver la nota sobre
 * `key={attempt}` en el docstring de `attempt` para por qué un fallo nuevo
 * (que cambia `attempt`) debe remontar, no solo re-renderizar.
 *
 * Garantía de "un solo reintento": tanto llegar a 0 como llamar a
 * `retryNow()` disparan `onRetry` EXACTAMENTE una vez -- un guard
 * (`firedRef`) bloquea cualquier disparo posterior, y el intervalo activo
 * se cancela en cuanto se dispara por cualquiera de las dos vías (nunca
 * sigue descontando en el fondo tras un `retryNow()` manual).
 */
export function useRetryBackoff({
  attempt,
  onRetry,
  steps = DEFAULT_BACKOFF_STEPS_SECONDS,
}: UseRetryBackoffOptions): UseRetryBackoffResult {
  const [secondsRemaining, setSecondsRemaining] = useState(() => stepFor(attempt, steps));

  const firedRef = useRef(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // `onRetry` va por ref (actualizada en un efecto propio, nunca durante el
  // render -- las reglas de hooks de este repo prohíben escribir un ref en
  // el cuerpo del render, ver `lib/use-focus-trap.ts` para el mismo patrón):
  // así un caller que pasa una función nueva en cada render (el caso común,
  // ver `GatewayOfflineCard`) no reinicia nada, el intervalo sigue leyendo
  // siempre la versión más reciente.
  const onRetryRef = useRef(onRetry);
  useEffect(() => {
    onRetryRef.current = onRetry;
  }, [onRetry]);

  function fireOnce() {
    if (firedRef.current) return;
    firedRef.current = true;
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    onRetryRef.current();
  }

  useEffect(() => {
    const total = stepFor(attempt, steps);
    if (total <= 0) return;

    // El contador "real" vive en una variable local del efecto (no en el
    // `useState`): `fireOnce()` dispara `onRetry`, que en el caso real
    // (`chat-content.tsx`) termina llamando `setState` en OTRO componente
    // (`retryPendingTurn` -> `turnStream.sendTurn`) -- si ese disparo
    // ocurriera desde DENTRO de la función actualizadora de
    // `setSecondsRemaining` (`setSecondsRemaining(prev => ...)`), React lo
    // trata como "setState de otro componente durante el render de este"
    // (warning + comportamiento no confiable). Separar el conteo del
    // `setState` deja `fireOnce()` como una llamada de nivel superior del
    // callback del `setInterval` -- un contexto de evento normal, no el
    // cuerpo de un actualizador.
    let remaining = total;
    intervalRef.current = setInterval(() => {
      remaining -= 1;
      if (remaining <= 0) {
        setSecondsRemaining(0);
        fireOnce();
        return;
      }
      setSecondsRemaining(remaining);
    }, 1000);

    return () => {
      if (intervalRef.current !== null) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
    // Deliberadamente vacío (mount-only): `attempt`/`steps` se leen una sola
    // vez al montar -- ver el docstring de `attempt` sobre por qué el caller
    // remonta (`key={attempt}`) en vez de que este efecto reaccione a que
    // cambien.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { secondsRemaining, retryNow: fireOnce };
}

function stepFor(attempt: number, steps: readonly number[]): number {
  if (attempt <= 0 || steps.length === 0) return 0;
  return steps[Math.min(attempt - 1, steps.length - 1)];
}
