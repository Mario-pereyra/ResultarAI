import userEvent from "@testing-library/user-event";
import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { Modal } from "./modal";

function Harness() {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button onClick={() => setOpen(true)}>abrir</button>
      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="Eliminar usuario"
        closeLabel="Cerrar"
        footer={<button>Confirmar</button>}
      >
        <input aria-label="comentario" />
      </Modal>
    </div>
  );
}

describe("Modal", () => {
  it('escenario "Modal con trampa de foco": Tab desde el último elemento vuelve al primero, Shift+Tab hace el ciclo inverso', async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.click(screen.getByRole("button", { name: "abrir" }));

    const dialog = screen.getByRole("dialog");
    expect(dialog.getAttribute("aria-modal")).toBe("true");
    const labelledBy = dialog.getAttribute("aria-labelledby");
    expect(document.getElementById(labelledBy ?? "")?.textContent).toBe("Eliminar usuario");

    const closeButton = screen.getByRole("button", { name: "Cerrar" });
    const input = screen.getByLabelText("comentario");
    const confirmButton = screen.getByRole("button", { name: "Confirmar" });

    // Foco inicial: primer elemento enfocable del modal.
    expect(document.activeElement).toBe(closeButton);

    await user.tab();
    expect(document.activeElement).toBe(input);

    await user.tab();
    expect(document.activeElement).toBe(confirmButton);

    // Tab desde el último vuelve al primero (trampa de foco).
    await user.tab();
    expect(document.activeElement).toBe(closeButton);

    // Shift+Tab desde el primero va al último.
    await user.tab({ shift: true });
    expect(document.activeElement).toBe(confirmButton);
  });

  it("Esc cierra el modal y devuelve el foco al disparador", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    const trigger = screen.getByRole("button", { name: "abrir" });
    await user.click(trigger);
    expect(screen.getByRole("dialog")).not.toBeNull();

    await user.keyboard("{Escape}");

    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  it("closeOnEscape=false ignora Esc (variante destructiva a mitad de confirmación)", async () => {
    const user = userEvent.setup();

    function DestructiveHarness() {
      const [open, setOpen] = useState(true);
      return (
        <Modal
          open={open}
          onClose={() => setOpen(false)}
          title="Eliminar usuario"
          closeLabel="Cerrar"
          closeOnEscape={false}
        >
          <p>Escribí ELIMINAR para confirmar.</p>
        </Modal>
      );
    }

    render(<DestructiveHarness />);
    expect(screen.getByRole("dialog")).not.toBeNull();

    await user.keyboard("{Escape}");

    expect(screen.getByRole("dialog")).not.toBeNull();
  });

  it("el click en el overlay cierra el modal y devuelve el foco al disparador", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    const trigger = screen.getByRole("button", { name: "abrir" });
    await user.click(trigger);

    const dialog = screen.getByRole("dialog");
    // El overlay es el padre inmediato de `.modal`. Se usa fireEvent en vez
    // de userEvent.click: el handler del componente escucha `mousedown`
    // (Modal.tsx), y userEvent.click() encadena mousedown→mouseup→click
    // sobre la MISMA referencia de nodo; como el mousedown ya desmonta el
    // overlay (onClose -> open=false), los eventos posteriores del combo
    // caen sobre un nodo ya destechado y confunden el foco en jsdom.
    const overlay = dialog.parentElement as HTMLElement;
    fireEvent.mouseDown(overlay, { target: overlay });

    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });
});
