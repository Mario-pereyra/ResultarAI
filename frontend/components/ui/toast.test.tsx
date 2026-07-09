import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useToasts, ToastStack } from "./toast";

function TestHarness() {
  const { toasts, show, dismiss } = useToasts();
  return (
    <div>
      <button onClick={() => show({ variant: "info", title: "Sesión exportada" })}>show-info</button>
      <button onClick={() => show({ variant: "warn", title: "Cuota al 82%" })}>show-warn</button>
      <button onClick={() => show({ variant: "danger", title: "La aprobación expiró" })}>show-danger</button>
      <ToastStack toasts={toasts} onDismiss={dismiss} label="Notificaciones" dismissLabel="Cerrar notificación" />
    </div>
  );
}

describe("Toast", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("auto-cierra un toast info tras el tiempo de auto-cierre por defecto", async () => {
    render(<TestHarness />);

    await act(async () => {
      screen.getByText("show-info").click();
    });
    expect(screen.getByText("Sesión exportada")).not.toBeNull();

    await act(async () => {
      vi.advanceTimersByTime(6000);
    });

    expect(screen.queryByText("Sesión exportada")).toBeNull();
  });

  it("NO auto-cierra toasts warn ni danger, incluso mucho después del tiempo por defecto", async () => {
    render(<TestHarness />);

    await act(async () => {
      screen.getByText("show-warn").click();
      screen.getByText("show-danger").click();
    });

    await act(async () => {
      vi.advanceTimersByTime(60_000);
    });

    expect(screen.queryByText("Cuota al 82%")).not.toBeNull();
    expect(screen.queryByText("La aprobación expiró")).not.toBeNull();
  });

  it("permite cerrar cualquier toast manualmente con el botón de cierre", async () => {
    render(<TestHarness />);

    await act(async () => {
      screen.getByText("show-warn").click();
    });

    const dismissButtons = screen.getAllByRole("button", { name: "Cerrar notificación" });
    await act(async () => {
      dismissButtons[0].click();
    });

    expect(screen.queryByText("Cuota al 82%")).toBeNull();
  });

  it("usa role=alert (assertive implícito) solo para danger y role=status para el resto", async () => {
    render(<TestHarness />);

    await act(async () => {
      screen.getByText("show-info").click();
      screen.getByText("show-warn").click();
      screen.getByText("show-danger").click();
    });

    expect(screen.getAllByRole("alert")).toHaveLength(1);
    expect(screen.getAllByRole("status")).toHaveLength(2);
  });

  it("el contenedor expone un nombre accesible vía aria-label", () => {
    render(<TestHarness />);
    expect(screen.getByRole("region", { name: "Notificaciones" })).not.toBeNull();
  });
});
