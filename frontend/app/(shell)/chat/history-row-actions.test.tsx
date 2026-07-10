import { createRef } from "react";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { HistoryRowActions, type HistoryRowActionsHandle } from "./history-row-actions";

/**
 * Tests de componente de la tarea 8.2 (d13-chat-conversacion, vista 12
 * §Móvil): el menú de acciones de una fila del historial, aislado de
 * `HistoryTableRow`/`history-content.tsx` -- ver `history-content.test.tsx`
 * para el flujo de long-press completo sobre una fila real.
 */

const LABELS = {
  menuLabel: "Acciones de la sesión",
  resume: "Retomar",
};

describe("HistoryRowActions (tarea 8.2)", () => {
  it('el disparador "⋮" es un botón con aria-label propio, cerrado por defecto', () => {
    render(<HistoryRowActions labels={LABELS} onResume={vi.fn()} />);

    const trigger = screen.getByRole("button", { name: LABELS.menuLabel });
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByRole("menu")).toBeNull();
  });

  it('click en el disparador abre el menú con el ítem "Retomar"; clickearlo llama a onResume', async () => {
    const user = userEvent.setup();
    const onResume = vi.fn();
    render(<HistoryRowActions labels={LABELS} onResume={onResume} />);

    await user.click(screen.getByRole("button", { name: LABELS.menuLabel }));
    const item = screen.getByRole("menuitem", { name: LABELS.resume });

    await user.click(item);
    expect(onResume).toHaveBeenCalledTimes(1);
  });

  it("openMenu() (ref imperativo) abre el menú programáticamente -- lo usa el long-press de la fila", () => {
    const ref = createRef<HistoryRowActionsHandle>();
    render(<HistoryRowActions ref={ref} labels={LABELS} onResume={vi.fn()} />);

    expect(screen.queryByRole("menu")).toBeNull();
    act(() => {
      ref.current?.openMenu();
    });
    expect(screen.getByRole("menu")).toBeTruthy();
    expect(screen.getByRole("menuitem", { name: LABELS.resume })).toBeTruthy();
  });
});
