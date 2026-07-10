import { useState } from "react";
import userEvent from "@testing-library/user-event";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Composer, type ComposerProps } from "./composer";

/**
 * Tests de componente del composer (d13-chat-conversacion, tarea 3.4):
 * cubre los tres estados pedidos por la verificación de la tarea --
 * vacío (botón deshabilitado, hint visible), con texto (Enter envía,
 * Shift+Enter agrega un salto de línea sin enviar) y streaming (el botón
 * muestra "Detener" y el click llama a `onStop`).
 */

const LABELS = {
  placeholder: "Escribile a Chat por Defecto…",
  textareaLabel: "Mensaje",
  send: "Enviar",
  stop: "Detener",
  hint: "Enter envía · Shift+Enter salto de línea",
};

/** Envoltorio controlado: el composer real es un componente controlado
 * (`value`/`onChange`), así que el harness de test necesita dueño de ese
 * estado -- igual que `chat-content.tsx` en producción. */
function ControlledComposer(props: Partial<ComposerProps>) {
  const [value, setValue] = useState(props.value ?? "");
  return (
    <Composer
      labels={LABELS}
      streaming={false}
      onSubmit={vi.fn()}
      onStop={vi.fn()}
      {...props}
      value={value}
      onChange={setValue}
    />
  );
}

describe("Composer — estado vacío (tarea 3.4)", () => {
  it("el botón enviar está deshabilitado y el hint es visible", () => {
    render(<ControlledComposer />);

    const sendButton = screen.getByRole("button", { name: "Enviar" });
    expect(sendButton.hasAttribute("disabled")).toBe(true);
    expect(screen.getByText("Enter envía · Shift+Enter salto de línea")).toBeTruthy();
  });

  it("un texto de solo espacios mantiene el botón deshabilitado", () => {
    render(<ControlledComposer value="   " />);

    expect(
      screen.getByRole("button", { name: "Enviar" }).hasAttribute("disabled"),
    ).toBe(true);
  });
});

describe("Composer — con texto (tarea 3.4)", () => {
  it("Enter (sin Shift) dispara sendTurn con el texto actual", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<ControlledComposer value="hola" onSubmit={onSubmit} />);

    const textarea = screen.getByLabelText("Mensaje");
    await user.click(textarea);
    await user.keyboard("{Enter}");

    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit).toHaveBeenCalledWith("hola");
  });

  it("Shift+Enter agrega un salto de línea sin enviar", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<ControlledComposer value="hola" onSubmit={onSubmit} />);

    const textarea = screen.getByLabelText("Mensaje") as HTMLTextAreaElement;
    await user.click(textarea);
    textarea.setSelectionRange(textarea.value.length, textarea.value.length);
    await user.keyboard("{Shift>}{Enter}{/Shift}");

    expect(onSubmit).not.toHaveBeenCalled();
    expect(textarea.value).toBe("hola\n");
  });

  it("el botón enviar está habilitado con texto no vacío", () => {
    render(<ControlledComposer value="hola" />);
    expect(
      screen.getByRole("button", { name: "Enviar" }).hasAttribute("disabled"),
    ).toBe(false);
  });
});

describe("Composer — streaming (tarea 3.4)", () => {
  it("el botón muestra «Detener» y el click llama a onStop, sin enviar", async () => {
    const user = userEvent.setup();
    const onStop = vi.fn();
    const onSubmit = vi.fn();
    render(<ControlledComposer value="hola" streaming onStop={onStop} onSubmit={onSubmit} />);

    const stopButton = screen.getByRole("button", { name: "Detener" });
    expect(screen.queryByRole("button", { name: "Enviar" })).toBeNull();

    await user.click(stopButton);

    expect(onStop).toHaveBeenCalledTimes(1);
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("el textarea queda deshabilitado (bloquea el doble envío durante el round-trip)", () => {
    render(<ControlledComposer value="hola" streaming />);
    expect(screen.getByLabelText("Mensaje").hasAttribute("disabled")).toBe(true);
  });
});
