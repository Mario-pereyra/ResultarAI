import { useState } from "react";
import userEvent from "@testing-library/user-event";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { AttachmentItem } from "@/lib/chat/attachment-adapter";
import { Composer, type ComposerProps } from "./composer";

/**
 * Tests de componente del composer (d13-chat-conversacion, tarea 3.4;
 * adjuntos de d14-attachments, tareas 8.1/8.2): cubre los tres estados
 * pedidos por la verificación de la tarea 3.4 -- vacío (botón deshabilitado,
 * hint visible), con texto (Enter envía, Shift+Enter agrega un salto de
 * línea sin enviar) y streaming (el botón muestra "Detener" y el click llama
 * a `onStop`) -- más la integración de adjuntos: click en "Adjuntar archivo"
 * dispara `onAttachFiles`, "Quitar" dispara `onRemoveAttachment`, y el envío
 * queda bloqueado mientras algún adjunto no sea `sendable` (ANEXO §6/§10,
 * "nunca... silencioso", tarea 8.1) + el chip de estado real por adjunto
 * (spinner, texto por estado/rol, causa específica, confirmación N2
 * auditada -- tarea 8.2, ver `attachment-chip.test.tsx` para la cobertura
 * detallada del chip en sí; acá solo se cubre la integración vía `Composer`).
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
  // Valores REALES de `Chat.attachments.states`/`warnings` (tarea 8.2).
  attachmentStates: {
    uploading: "Subiendo… {percent}%",
    processing: "Procesando contenido…",
    readyTechAdmin: "Listo · {tokens} tokens",
    readyFunctional: "Listo · usa {percent}% del espacio del mensaje",
    readyTruncated: "Listo · incluye el {percent}% del archivo — tocá para ver qué verá el agente",
    warning: "Revisá antes de enviar",
    blocked: "Bloqueado — contiene credenciales",
    error: "No se pudo procesar",
  },
  attachmentPiiConfirmation: "Confirmo que son datos de prueba",
  attachmentPiiCancel: "Cancelar",
  attachmentPreviewAction: "Ver lo que verá el agente",
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
    confirming: false,
    ...overrides,
  };
}

/** Envoltorio controlado: el composer real es un componente controlado
 * (`value`/`onChange`), así que el harness de test necesita dueño de ese
 * estado -- igual que `chat-content.tsx` en producción. `role="funcional"`
 * por default (el más restrictivo de transparencia, ver tarea 8.2) -- los
 * tests que necesitan Técnico/Admin lo pasan explícito. */
function ControlledComposer(props: Partial<ComposerProps>) {
  const [value, setValue] = useState(props.value ?? "");
  return (
    <Composer
      labels={LABELS}
      streaming={false}
      onSubmit={vi.fn()}
      onStop={vi.fn()}
      attachments={[]}
      role="funcional"
      onAttachFiles={vi.fn()}
      onRemoveAttachment={vi.fn()}
      onConfirmAttachmentTestData={vi.fn()}
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

describe("Composer — chip de estado (d14-attachments, tarea 8.2)", () => {
  it('escenario "Error de extracción muestra causa accionable": chip en error con causa, nunca silencioso', () => {
    const errored = makeAttachment({
      status: "error",
      sendable: false,
      message:
        "No pudimos procesar este archivo (puede estar dañado). Probá guardarlo de nuevo desde la aplicación original.",
    });
    render(<ControlledComposer attachments={[errored]} />);

    expect(screen.getByText("No se pudo procesar")).toBeTruthy();
    expect(
      screen.getByText(
        "No pudimos procesar este archivo (puede estar dañado). Probá guardarlo de nuevo desde la aplicación original.",
      ),
    ).toBeTruthy();
  });

  it('escenario "Adjunto bloqueado se ve como no enviable": chip bloqueado + envío deshabilitado', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    const blocked = makeAttachment({
      status: "blocked",
      sendable: false,
      message: 'Este archivo contiene lo que parece una contraseña o clave de acceso ("Password=***" en la línea 23).',
    });
    render(<ControlledComposer value="hola" attachments={[blocked]} onSubmit={onSubmit} />);

    expect(screen.getByText("Bloqueado — contiene credenciales")).toBeTruthy();
    const sendButton = screen.getByRole("button", { name: "Enviar" });
    expect(sendButton.hasAttribute("disabled")).toBe(true);

    await user.click(sendButton);
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("subiendo: spinner + texto neutro (sin tracking de % real, ver el docstring de AttachmentChip)", () => {
    const uploading = makeAttachment({ status: "uploading" });
    render(<ControlledComposer attachments={[uploading]} />);

    expect(screen.getByText("Subiendo…")).toBeTruthy();
  });

  it("procesando: texto de extracción en curso", () => {
    const processing = makeAttachment({ status: "processing" });
    render(<ControlledComposer attachments={[processing]} />);

    expect(screen.getByText("Procesando contenido…")).toBeTruthy();
  });

  it('listo (Funcional): "usa {percent}% del espacio del mensaje"', () => {
    const ready = makeAttachment({ status: "ready", sendable: true, includedPercent: 34 });
    render(<ControlledComposer attachments={[ready]} role="funcional" />);

    expect(screen.getByText("Listo · usa 34% del espacio del mensaje")).toBeTruthy();
  });

  it('listo (Técnico/Admin): "{tokens} tokens" con separador de miles es-BO', () => {
    const ready = makeAttachment({ status: "ready", sendable: true, tokenCount: 8200 });
    render(<ControlledComposer attachments={[ready]} role="tecnico" />);

    expect(screen.getByText("Listo · 8.200 tokens")).toBeTruthy();
  });

  it("listo truncado: texto universal (mismo para cualquier rol), invita a la vista previa (8.3)", () => {
    const truncated = makeAttachment({
      status: "ready",
      sendable: true,
      truncated: true,
      includedPercent: 62,
    });
    render(<ControlledComposer attachments={[truncated]} role="admin" />);

    expect(
      screen.getByText("Listo · incluye el 62% del archivo — tocá para ver qué verá el agente"),
    ).toBeTruthy();
  });

  it('escenario "Vista previa de un adjunto truncado" (integración vía Composer, tarea 8.3): el texto truncado dispara onOpenAttachmentPreview(id)', async () => {
    const user = userEvent.setup();
    const onOpenAttachmentPreview = vi.fn();
    const truncated = makeAttachment({
      status: "ready",
      sendable: true,
      truncated: true,
      includedPercent: 62,
    });
    render(
      <ControlledComposer
        attachments={[truncated]}
        role="admin"
        onOpenAttachmentPreview={onOpenAttachmentPreview}
      />,
    );

    await user.click(screen.getByRole("button", { name: /incluye el 62%/ }));
    expect(onOpenAttachmentPreview).toHaveBeenCalledWith(truncated.id);
  });

  it("listo sin truncar (integración vía Composer, tarea 8.3): el botón propio «Ver lo que verá el agente» dispara onOpenAttachmentPreview(id)", async () => {
    const user = userEvent.setup();
    const onOpenAttachmentPreview = vi.fn();
    const ready = makeAttachment({ status: "ready", sendable: true, tokenCount: 8200 });
    render(
      <ControlledComposer
        attachments={[ready]}
        role="tecnico"
        onOpenAttachmentPreview={onOpenAttachmentPreview}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Ver lo que verá el agente" }));
    expect(onOpenAttachmentPreview).toHaveBeenCalledWith(ready.id);
  });

  it("advertencia N2: checkbox auditado visible, checkearlo llama a onConfirmAttachmentTestData(id)", async () => {
    const user = userEvent.setup();
    const onConfirmAttachmentTestData = vi.fn();
    const warning = makeAttachment({
      status: "warning",
      sendable: false,
      requiresTestDataConfirmation: true,
      message: "Detectamos posibles datos personales en este archivo (2 emails, 1 número de carnet).",
    });
    render(
      <ControlledComposer
        attachments={[warning]}
        onConfirmAttachmentTestData={onConfirmAttachmentTestData}
      />,
    );

    expect(screen.getByText("Revisá antes de enviar")).toBeTruthy();
    const checkbox = screen.getByRole("checkbox", { name: "Confirmo que son datos de prueba" });
    expect((checkbox as HTMLInputElement).checked).toBe(false);

    await user.click(checkbox);
    expect(onConfirmAttachmentTestData).toHaveBeenCalledWith(warning.id);
  });

  it('advertencia N2: "Cancelar" quita el adjunto (onRemoveAttachment)', async () => {
    const user = userEvent.setup();
    const onRemoveAttachment = vi.fn();
    const warning = makeAttachment({
      status: "warning",
      sendable: false,
      requiresTestDataConfirmation: true,
      message: "Detectamos posibles datos personales en este archivo (2 emails).",
    });
    render(
      <ControlledComposer attachments={[warning]} onRemoveAttachment={onRemoveAttachment} />,
    );

    await user.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(onRemoveAttachment).toHaveBeenCalledWith(warning.id);
  });

  it("advertencia por instrucción embebida (sin confirmación N2 pendiente): sin checkbox", () => {
    const warning = makeAttachment({
      status: "warning",
      sendable: false,
      requiresTestDataConfirmation: false,
      message: 'Este documento contiene texto que parece dirigido a la IA ("ignorá las instrucciones…").',
    });
    render(<ControlledComposer attachments={[warning]} />);

    expect(screen.queryByRole("checkbox")).toBeNull();
  });

  it("confirmando (POST en vuelo): el checkbox queda marcado y deshabilitado", () => {
    const warning = makeAttachment({
      status: "warning",
      sendable: false,
      requiresTestDataConfirmation: true,
      confirming: true,
      message: "Detectamos posibles datos personales en este archivo (2 emails).",
    });
    render(<ControlledComposer attachments={[warning]} />);

    const checkbox = screen.getByRole("checkbox", {
      name: "Confirmo que son datos de prueba",
    }) as HTMLInputElement;
    expect(checkbox.checked).toBe(true);
    expect(checkbox.disabled).toBe(true);
  });
});
