import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useRetryBackoff } from "./use-retry-backoff";

/**
 * Tests de la tarea 6.1 (d13-chat-conversacion): matemática pura del
 * countdown/backoff, aislada de `GatewayOfflineCard`/`chat-content.tsx` --
 * ver `chat-content.test.tsx` para el flujo end-to-end (fetch real
 * fallando, mensaje del usuario no duplicado).
 *
 * `attempt` es mount-only (ver el docstring del hook): cada caso que
 * simula un fallo NUEVO monta una instancia nueva con `renderHook`, igual
 * que `GatewayOfflineCard` remonta vía `key={attempt}` en producción.
 */
describe("useRetryBackoff", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("primer intento: arranca en 5 s y descuenta de a uno por segundo", () => {
    const onRetry = vi.fn();
    const { result } = renderHook(() => useRetryBackoff({ attempt: 1, onRetry }));

    expect(result.current.secondsRemaining).toBe(5);

    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(result.current.secondsRemaining).toBe(4);
  });

  it("countdown llegando a cero dispara EXACTAMENTE un reintento", () => {
    const onRetry = vi.fn();
    const { result } = renderHook(() => useRetryBackoff({ attempt: 1, onRetry }));

    act(() => {
      vi.advanceTimersByTime(5000);
    });

    expect(result.current.secondsRemaining).toBe(0);
    expect(onRetry).toHaveBeenCalledTimes(1);

    // Tiempo adicional no dispara un segundo reintento (guard `firedRef`).
    act(() => {
      vi.advanceTimersByTime(10_000);
    });
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("segundo intento consecutivo usa el paso 15 s (backoff 5→15→60)", () => {
    const onRetry = vi.fn();
    const { result } = renderHook(() => useRetryBackoff({ attempt: 2, onRetry }));

    expect(result.current.secondsRemaining).toBe(15);
  });

  it("tercer intento y siguientes se quedan en el tope de 60 s", () => {
    const onRetryThird = vi.fn();
    const third = renderHook(() => useRetryBackoff({ attempt: 3, onRetry: onRetryThird }));
    expect(third.result.current.secondsRemaining).toBe(60);

    const onRetryFifth = vi.fn();
    const fifth = renderHook(() => useRetryBackoff({ attempt: 5, onRetry: onRetryFifth }));
    expect(fifth.result.current.secondsRemaining).toBe(60);
  });

  it('"Reintentar ahora" (retryNow) dispara el reintento de inmediato, sin esperar el countdown', () => {
    const onRetry = vi.fn();
    const { result } = renderHook(() => useRetryBackoff({ attempt: 1, onRetry }));

    act(() => {
      result.current.retryNow();
    });

    expect(onRetry).toHaveBeenCalledTimes(1);

    // El intervalo quedó cancelado -- avanzar el tiempo no dispara un
    // segundo reintento ni sigue descontando en el fondo.
    act(() => {
      vi.advanceTimersByTime(10_000);
    });
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("retryNow llamado dos veces (doble click) dispara un único reintento", () => {
    const onRetry = vi.fn();
    const { result } = renderHook(() => useRetryBackoff({ attempt: 1, onRetry }));

    act(() => {
      result.current.retryNow();
      result.current.retryNow();
    });

    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("attempt <= 0 no arranca ningún countdown", () => {
    const onRetry = vi.fn();
    const { result } = renderHook(() => useRetryBackoff({ attempt: 0, onRetry }));

    expect(result.current.secondsRemaining).toBe(0);

    act(() => {
      vi.advanceTimersByTime(60_000);
    });
    expect(onRetry).not.toHaveBeenCalled();
  });
});
