import { useState } from "react";
import userEvent from "@testing-library/user-event";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { AttachmentItem } from "@/lib/chat/attachment-adapter";
import { Composer, type ComposerProps } from "./composer";

/**
 * Tests de componente del composer (d13-chat-conversacion, tarea 3.4;
 * adjuntos de d14-attachments, tarea 8.1): cubre los tres estados pedidos
 * por la verificación de la tarea 3.4 -- vacío (botón deshabilitado, hint
 * visible), con texto (Enter envía, Shift+Enter agrega un salto de línea sin
 * enviar) y streaming (el botón muestra "Detener" y el click llama a
 * `onStop`) -- más la integración mínima de adjuntos de la tarea 8.1: click
 * en "Adjuntar archivo" dispara `onAttachFiles`, "Quitar" dispara
 * `onRemoveAttachment`, y el envío queda bloqueado mientras algún adjunto no
 * sea `sendable` (ANEXO §6/§10, "nunca... silencioso").
 */

const LABELS = {
  placeholder: "Escribile a Chat por Defecto…",
  textareaLabel: "Mensaje",
  send: "Enviar",
  stop: "Detener",
  hint: "Enter envía · Shift+Enter salto de línea",
  attach: "Adjuntar archivo",
  attachmentsListLabel: "Archivos adjuntos",
  removeAttachment: "Quitar adjunto {file}",
};

function makeAttachment(overrides: Partial<AttachmentItem> = {}): AttachmentItem {
  return {
    id: "attachment-local-1",
    attachmentId: null,
    file: new File(["contenido"], "balance.xlsx"),
    originalName: "balance.xlsx",
    status: "uploading",
    sendable: false,
    requiresTestDataConfirmation: false,
    tokenCount: null,
    includedPercent: null,
    truncated: null,
    message: null,
    ...overrides,
  };
}

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
      attachments={[]}
      onAttachFiles={vi.fn()}
      onRemoveAttachment={vi.fn()}
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

describe("Composer — adjuntos (d14-attachments, tarea 8.1)", () => {
  it('click en "Adjuntar archivo" abre el selector de archivos (dispara onAttachFiles al elegir)', async () => {
    const user = userEvent.setup();
    const onAttachFiles = vi.fn();
    render(<ControlledComposer onAttachFiles={onAttachFiles} />);

    const file = new File(["contenido"], "reporte.pdf", { type: "application/pdf" });
    // El `<input type="file">` está oculto (`hidden`) -- se ejercita
    // directamente, mismo patrón que el resto de la suite de attachments
    // para inputs de archivo ocultos tras un botón visible.
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await user.upload(input, file);

    expect(onAttachFiles).toHaveBeenCalledTimes(1);
    expect(onAttachFiles).toHaveBeenCalledWith([file]);
  });

  it('el botón "Adjuntar archivo" respeta attachDisabled', () => {
    render(<ControlledComposer attachDisabled />);
    expect(screen.getByRole("button", { name: "Adjuntar archivo" }).hasAttribute("disabled")).toBe(
      true,
    );
  });

  it("lista un adjunto con su nombre y expone el mensaje §10 ya resuelto", () => {
    const blocked = makeAttachment({
      status: "blocked",
      message: 'Este archivo contiene lo que parece una contraseña ("Password=***" en la línea 23).',
    });
    render(<ControlledComposer attachments={[blocked]} />);

    expect(screen.getByText("balance.xlsx")).toBeTruthy();
    expect(
      screen.getByText('Este archivo contiene lo que parece una contraseña ("Password=***" en la línea 23).'),
    ).toBeTruthy();
  });

  it('"Quitar" de un adjunto dispara onRemoveAttachment(id)', async () => {
    const user = userEvent.setup();
    const onRemoveAttachment = vi.fn();
    const item = makeAttachment();
    render(<ControlledComposer attachments={[item]} onRemoveAttachment={onRemoveAttachment} />);

    await user.click(screen.getByRole("button", { name: "Quitar adjunto balance.xlsx" }));

    expect(onRemoveAttachment).toHaveBeenCalledWith(item.id);
  });

  it("el envío queda deshabilitado mientras algún adjunto no sea sendable (nunca silencioso)", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    const uploading = makeAttachment({ status: "uploading", sendable: false });
    render(<ControlledComposer value="hola" attachments={[uploading]} onSubmit={onSubmit} />);

    const sendButton = screen.getByRole("button", { name: "Enviar" });
    expect(sendButton.hasAttribute("disabled")).toBe(true);

    await user.click(sendButton);
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("el envío se habilita de nuevo con un adjunto sendable (listo/confirmado)", () => {
    const ready = makeAttachment({ status: "ready", sendable: true });
    render(<ControlledComposer value="hola" attachments={[ready]} />);

    expect(screen.getByRole("button", { name: "Enviar" }).hasAttribute("disabled")).toBe(false);
  });
});
