import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EditMessageButton, MessageEdit, type MessageEditLabels } from "./message-edit";

const LABELS: MessageEditLabels = {
  action: "Editar mensaje (crea una rama nueva)",
  textareaLabel: "Editar mensaje",
  cancel: "Cancelar",
  confirm: "Crear rama",
  reprocessWarningOne: "Crear una rama acá reprocesa {n} mensaje",
  reprocessWarningOther: "Crear una rama acá reprocesa {n} mensajes",
};

describe("MessageEdit — textarea precargado (tarea 5.5)", () => {
  it("arranca con el texto original del mensaje", () => {
    render(
      <MessageEdit
        originalText="¿Cómo configuro MV_AGENTE?"
        reprocessCount={0}
        labels={LABELS}
        onConfirm={() => {}}
        onCancel={() => {}}
      />,
    );
    const textarea = screen.getByLabelText("Editar mensaje") as HTMLTextAreaElement;
    expect(textarea.value).toBe("¿Cómo configuro MV_AGENTE?");
  });
});

describe("MessageEdit — aviso «reprocesa N mensajes» (tarea 5.5)", () => {
  it("N=6 (≥3): el aviso está visible con el texto exacto y «Crear rama» queda HABILITADO", () => {
    render(
      <MessageEdit
        originalText="Pregunta original"
        reprocessCount={6}
        labels={LABELS}
        onConfirm={() => {}}
        onCancel={() => {}}
      />,
    );
    const warning = screen.getByRole("status");
    expect(warning.textContent).toContain("Crear una rama acá reprocesa 6 mensajes");
    const confirmBtn = screen.getByRole("button", { name: "Crear rama" }) as HTMLButtonElement;
    expect(confirmBtn.disabled).toBe(false);
  });

  it("N=1 (<3): el aviso NO aparece", () => {
    render(
      <MessageEdit
        originalText="Pregunta original"
        reprocessCount={1}
        labels={LABELS}
        onConfirm={() => {}}
        onCancel={() => {}}
      />,
    );
    expect(screen.queryByRole("status")).toBeNull();
    expect(screen.queryByText(/reprocesa/)).toBeNull();
  });

  it("N=0 (editar el último mensaje): el aviso NO aparece", () => {
    render(
      <MessageEdit
        originalText="Pregunta original"
        reprocessCount={0}
        labels={LABELS}
        onConfirm={() => {}}
        onCancel={() => {}}
      />,
    );
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("N=3 (umbral exacto): el aviso SÍ aparece", () => {
    render(
      <MessageEdit
        originalText="Pregunta original"
        reprocessCount={3}
        labels={LABELS}
        onConfirm={() => {}}
        onCancel={() => {}}
      />,
    );
    expect(screen.getByText("Crear una rama acá reprocesa 3 mensajes")).toBeTruthy();
  });
});

describe("MessageEdit — cancelar y confirmar (tarea 5.5)", () => {
  it("cancelar invoca onCancel sin llamar a onConfirm", async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();
    const onConfirm = vi.fn();
    render(
      <MessageEdit
        originalText="Texto original"
        reprocessCount={0}
        labels={LABELS}
        onConfirm={onConfirm}
        onCancel={onCancel}
      />,
    );
    await user.type(screen.getByLabelText("Editar mensaje"), " editado");
    await user.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("Esc dentro del textarea también cancela", async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();
    render(
      <MessageEdit
        originalText="Texto original"
        reprocessCount={0}
        labels={LABELS}
        onConfirm={() => {}}
        onCancel={onCancel}
      />,
    );
    const textarea = screen.getByLabelText("Editar mensaje");
    textarea.focus();
    await user.keyboard("{Escape}");
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("confirmar llama a onConfirm con el texto EDITADO (recortado)", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(
      <MessageEdit
        originalText="Texto original"
        reprocessCount={0}
        labels={LABELS}
        onConfirm={onConfirm}
        onCancel={() => {}}
      />,
    );
    const textarea = screen.getByLabelText("Editar mensaje");
    await user.clear(textarea);
    await user.type(textarea, "  Texto corregido  ");
    await user.click(screen.getByRole("button", { name: "Crear rama" }));
    expect(onConfirm).toHaveBeenCalledWith("Texto corregido");
  });

  it("con el texto vacío, «Crear rama» queda deshabilitado", async () => {
    const user = userEvent.setup();
    render(
      <MessageEdit
        originalText="Texto original"
        reprocessCount={0}
        labels={LABELS}
        onConfirm={() => {}}
        onCancel={() => {}}
      />,
    );
    const textarea = screen.getByLabelText("Editar mensaje");
    await user.clear(textarea);
    expect((screen.getByRole("button", { name: "Crear rama" }) as HTMLButtonElement).disabled).toBe(
      true,
    );
  });

  it("`pending`: deshabilita cancelar y el textarea, y el aviso sigue visible (no bloquea)", () => {
    render(
      <MessageEdit
        originalText="Texto original"
        reprocessCount={6}
        pending
        labels={LABELS}
        onConfirm={() => {}}
        onCancel={() => {}}
      />,
    );
    expect((screen.getByLabelText("Editar mensaje") as HTMLTextAreaElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: "Cancelar" }) as HTMLButtonElement).disabled).toBe(
      true,
    );
    expect(screen.getByText("Crear una rama acá reprocesa 6 mensajes")).toBeTruthy();
  });
});

describe("EditMessageButton (tarea 5.5)", () => {
  it("dispara onClick con su aria-label", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(<EditMessageButton label="Editar mensaje (crea una rama nueva)" onClick={onClick} />);
    await user.click(screen.getByRole("button", { name: "Editar mensaje (crea una rama nueva)" }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });
});
