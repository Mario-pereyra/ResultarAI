import { renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useLongPress } from "./use-long-press";

/**
 * Tests de la tarea 8.2 (d13-chat-conversacion): mecánica pura del
 * long-press, aislada de `HistoryRowActions`/`HistoryTableRow` -- ver
 * `app/(shell)/chat/history-content.test.tsx` para el flujo de componente
 * completo (long-press de una fila real abriendo el menú).
 *
 * Los handlers devueltos ignoran el `PointerEvent` que reciben (no leen
 * `clientX`/`pointerType`/etc., ver el docstring del hook) -- por eso acá
 * se invocan directo, sin simular un evento DOM real.
 */
describe("useLongPress", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("pointerdown + 500ms dispara onLongPress exactamente una vez", () => {
    const onLongPress = vi.fn();
    const { result } = renderHook(() => useLongPress({ onLongPress }));

    result.current.handlers.onPointerDown({} as never);
    expect(onLongPress).not.toHaveBeenCalled();

    vi.advanceTimersByTime(499);
    expect(onLongPress).not.toHaveBeenCalled();

    vi.advanceTimersByTime(1);
    expect(onLongPress).toHaveBeenCalledTimes(1);

    // Tiempo adicional no dispara un segundo long-press del mismo gesto.
    vi.advanceTimersByTime(10_000);
    expect(onLongPress).toHaveBeenCalledTimes(1);
  });

  it("soltar antes del umbral (pointerup) cancela el temporizador -- sin long-press", () => {
    const onLongPress = vi.fn();
    const { result } = renderHook(() => useLongPress({ onLongPress }));

    result.current.handlers.onPointerDown({} as never);
    vi.advanceTimersByTime(300);
    result.current.handlers.onPointerUp({} as never);
    vi.advanceTimersByTime(500);

    expect(onLongPress).not.toHaveBeenCalled();
  });

  it("salir del elemento (pointerleave) cancela el temporizador -- sin long-press", () => {
    const onLongPress = vi.fn();
    const { result } = renderHook(() => useLongPress({ onLongPress }));

    result.current.handlers.onPointerDown({} as never);
    vi.advanceTimersByTime(200);
    result.current.handlers.onPointerLeave({} as never);
    vi.advanceTimersByTime(500);

    expect(onLongPress).not.toHaveBeenCalled();
  });

  it("cancelar el pointer (pointercancel) cancela el temporizador -- sin long-press", () => {
    const onLongPress = vi.fn();
    const { result } = renderHook(() => useLongPress({ onLongPress }));

    result.current.handlers.onPointerDown({} as never);
    vi.advanceTimersByTime(200);
    result.current.handlers.onPointerCancel({} as never);
    vi.advanceTimersByTime(500);

    expect(onLongPress).not.toHaveBeenCalled();
  });

  it("respeta un delayMs custom", () => {
    const onLongPress = vi.fn();
    const { result } = renderHook(() => useLongPress({ onLongPress, delayMs: 800 }));

    result.current.handlers.onPointerDown({} as never);
    vi.advanceTimersByTime(500);
    expect(onLongPress).not.toHaveBeenCalled();

    vi.advanceTimersByTime(300);
    expect(onLongPress).toHaveBeenCalledTimes(1);
  });

  it("consumeLongPress(): false antes de un long-press, true una vez tras dispararse, false después (se resetea)", () => {
    const onLongPress = vi.fn();
    const { result } = renderHook(() => useLongPress({ onLongPress }));

    expect(result.current.consumeLongPress()).toBe(false);

    result.current.handlers.onPointerDown({} as never);
    vi.advanceTimersByTime(500);
    expect(onLongPress).toHaveBeenCalledTimes(1);

    expect(result.current.consumeLongPress()).toBe(true);
    expect(result.current.consumeLongPress()).toBe(false);
  });

  it("un pointerdown nuevo reinicia el temporizador (no acumula gestos previos)", () => {
    const onLongPress = vi.fn();
    const { result } = renderHook(() => useLongPress({ onLongPress }));

    // Primer gesto: soltado antes del umbral.
    result.current.handlers.onPointerDown({} as never);
    vi.advanceTimersByTime(300);
    result.current.handlers.onPointerUp({} as never);

    // Segundo gesto, completo: dispara desde CERO (no hereda los 300ms del anterior).
    result.current.handlers.onPointerDown({} as never);
    vi.advanceTimersByTime(499);
    expect(onLongPress).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(onLongPress).toHaveBeenCalledTimes(1);
  });
});
