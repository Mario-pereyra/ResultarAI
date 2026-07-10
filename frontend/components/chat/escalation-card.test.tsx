import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EscalationCard, type EscalationCardLabels } from "./escalation-card";

/**
 * Tarea 5.3 de d13-chat-conversacion: tarjeta de escalación manual a Pro
 * (`design/VISTAS/02-chat.md` vista 08). Cubre los 4 estados de la máquina
 * (reposo/loading/escalada/descartada), la idempotencia ante doble clic y la
 * reconstrucción del estado escalado tras recarga. El gate por
 * `escalation_enabled` (la tarjeta no se monta) se prueba en
 * `app/(shell)/chat/chat-content.test.tsx`, que es donde vive ese gate.
 */

const LABELS: EscalationCardLabels = {
  title: "Este caso amerita el modelo Pro",
  consequence: "Se abre una conversación nueva con el contexto de esta.",
  targetProfileLabel: "Perfil de destino:",
  confirm: "Continuar con Pro",
  dismiss: "Seguir con Flash",
  doneLink: "Continuaste esta consulta en Pro — abrir conversación",
  dismissedNote: "Decidiste seguir con Flash",
};

const REASON = "Tu consulta cruza varias localizaciones y amerita el modelo avanzado.";

/** Promesa controlable a mano: para congelar el estado `loading` y para
 * ejercitar el guard de doble clic sin depender de temporizadores reales. */
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((res) => {
    resolve = res;
  });
  return { promise, resolve };
}

describe("EscalationCard — reposo (tarea 5.3)", () => {
  it("muestra título, razón, perfil de destino y ambos botones activos", () => {
    render(
      <EscalationCard
        reason={REASON}
        targetProfile="deepseek-v4-pro"
        labels={LABELS}
        onEscalate={vi.fn()}
        onNavigateEscalated={vi.fn()}
      />,
    );

    expect(screen.getByText(LABELS.title)).toBeTruthy();
    expect(screen.getByText(REASON)).toBeTruthy();
    expect(screen.getByText("deepseek-v4-pro")).toBeTruthy();

    const confirm = screen.getByRole("button", { name: LABELS.confirm }) as HTMLButtonElement;
    const dismiss = screen.getByRole("button", { name: LABELS.dismiss }) as HTMLButtonElement;
    expect(confirm.disabled).toBe(false);
    expect(dismiss.disabled).toBe(false);
  });

  it("sin perfil de destino (target_profile null) no renderiza el tag", () => {
    render(
      <EscalationCard
        reason={REASON}
        targetProfile={null}
        labels={LABELS}
        onEscalate={vi.fn()}
        onNavigateEscalated={vi.fn()}
      />,
    );
    expect(screen.queryByText("deepseek-v4-pro")).toBeNull();
    // Los botones siguen presentes: la falta del tag no rompe la tarjeta.
    expect(screen.getByRole("button", { name: LABELS.confirm })).toBeTruthy();
  });
});

describe("EscalationCard — loading (tarea 5.3)", () => {
  it("al confirmar, ambos botones quedan deshabilitados con spinner en el primario", async () => {
    const user = userEvent.setup();
    const control = deferred<{ escalatedSessionId: string }>();
    const onEscalate = vi.fn(() => control.promise);

    render(
      <EscalationCard
        reason={REASON}
        targetProfile="deepseek-v4-pro"
        labels={LABELS}
        onEscalate={onEscalate}
        onNavigateEscalated={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: LABELS.confirm }));

    expect(onEscalate).toHaveBeenCalledTimes(1);
    const confirm = screen.getByRole("button", { name: LABELS.confirm }) as HTMLButtonElement;
    expect(confirm.disabled).toBe(true);
    expect(confirm.getAttribute("aria-busy")).toBe("true");
    expect((screen.getByRole("button", { name: LABELS.dismiss }) as HTMLButtonElement).disabled).toBe(
      true,
    );
    // Se deja `control` sin resolver: la tarjeta se desmonta en el cleanup sin
    // una actualización de estado tardía (no hay warning de act).
  });
});

describe("EscalationCard — escalada (tarea 5.3)", () => {
  it("al resolver navega a la sesión devuelta y colapsa a nota-enlace, sin reposo", async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();
    const onEscalate = vi.fn(async () => ({ escalatedSessionId: "session-2" }));

    render(
      <EscalationCard
        reason={REASON}
        targetProfile="deepseek-v4-pro"
        labels={LABELS}
        onEscalate={onEscalate}
        onNavigateEscalated={onNavigate}
      />,
    );

    await user.click(screen.getByRole("button", { name: LABELS.confirm }));

    expect(await screen.findByText(LABELS.doneLink)).toBeTruthy();
    expect(onNavigate).toHaveBeenCalledWith("session-2");
    // La tarjeta ya no puede re-usarse (idempotencia): sin botones de reposo
    // ni la razón original.
    expect(screen.queryByRole("button", { name: LABELS.confirm })).toBeNull();
    expect(screen.queryByText(REASON)).toBeNull();
  });

  it("segunda activación idempotente (mismo id, otra pestaña): navega a la MISMA sesión, sin error", async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();
    // El backend idempotente (created:false) devuelve la sesión YA existente:
    // el componente navega a ella igual, sin distinguir el caso ni mostrar error.
    const onEscalate = vi.fn(async () => ({ escalatedSessionId: "session-existente" }));

    render(
      <EscalationCard
        reason={REASON}
        targetProfile="deepseek-v4-pro"
        labels={LABELS}
        onEscalate={onEscalate}
        onNavigateEscalated={onNavigate}
      />,
    );

    await user.click(screen.getByRole("button", { name: LABELS.confirm }));

    expect(onNavigate).toHaveBeenCalledWith("session-existente");
    expect(await screen.findByText(LABELS.doneLink)).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("la nota-enlace es clickable y re-navega a la sesión escalada", async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();
    const onEscalate = vi.fn(async () => ({ escalatedSessionId: "session-2" }));

    render(
      <EscalationCard
        reason={REASON}
        targetProfile="deepseek-v4-pro"
        labels={LABELS}
        onEscalate={onEscalate}
        onNavigateEscalated={onNavigate}
      />,
    );

    await user.click(screen.getByRole("button", { name: LABELS.confirm }));
    await screen.findByText(LABELS.doneLink);
    onNavigate.mockClear();

    await user.click(screen.getByRole("button", { name: /Continuaste esta consulta/ }));
    expect(onNavigate).toHaveBeenCalledWith("session-2");
  });
});

describe("EscalationCard — descartada (tarea 5.3)", () => {
  it("«Seguir con Flash» colapsa a línea atenuada, sin llamar a /escalate ni navegar", async () => {
    const user = userEvent.setup();
    const onEscalate = vi.fn();
    const onNavigate = vi.fn();
    const onDismiss = vi.fn();

    render(
      <EscalationCard
        reason={REASON}
        targetProfile="deepseek-v4-pro"
        labels={LABELS}
        onEscalate={onEscalate}
        onNavigateEscalated={onNavigate}
        onDismiss={onDismiss}
      />,
    );

    await user.click(screen.getByRole("button", { name: LABELS.dismiss }));

    expect(screen.getByText(LABELS.dismissedNote)).toBeTruthy();
    expect(onEscalate).not.toHaveBeenCalled();
    expect(onNavigate).not.toHaveBeenCalled();
    expect(onDismiss).toHaveBeenCalledTimes(1);
    // La conversación sigue: sin botones de escalación en el DOM.
    expect(screen.queryByRole("button", { name: LABELS.confirm })).toBeNull();
  });
});

describe("EscalationCard — idempotencia ante doble clic (tarea 5.3)", () => {
  it("dos clicks sincrónicos en «Continuar con Pro» disparan UNA sola llamada a onEscalate", () => {
    const control = deferred<{ escalatedSessionId: string }>();
    const onEscalate = vi.fn(() => control.promise);

    render(
      <EscalationCard
        reason={REASON}
        targetProfile="deepseek-v4-pro"
        labels={LABELS}
        onEscalate={onEscalate}
        onNavigateEscalated={vi.fn()}
      />,
    );

    const confirm = screen.getByRole("button", { name: LABELS.confirm });
    // Dos disparos ANTES de cualquier re-render (el guard sincrónico, no solo
    // el `disabled`, es lo que garantiza una sola llamada).
    fireEvent.click(confirm);
    fireEvent.click(confirm);

    expect(onEscalate).toHaveBeenCalledTimes(1);
  });
});

describe("EscalationCard — persistencia tras recarga (tarea 5.3)", () => {
  it("initialStatus escalado: arranca en nota-enlace (sin reposo) y navega al hacer click", async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();

    render(
      <EscalationCard
        reason={REASON}
        targetProfile="deepseek-v4-pro"
        labels={LABELS}
        initialStatus="escalated"
        escalatedSessionId="session-9"
        onEscalate={vi.fn()}
        onNavigateEscalated={onNavigate}
      />,
    );

    expect(screen.queryByRole("button", { name: LABELS.confirm })).toBeNull();
    await user.click(screen.getByRole("button", { name: /Continuaste esta consulta/ }));
    expect(onNavigate).toHaveBeenCalledWith("session-9");
  });
});

describe("EscalationCard — error al escalar (tarea 5.3)", () => {
  it("si /escalate rechaza, vuelve a reposo (sin tarjeta de error) y no navega", async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();
    const onEscalate = vi.fn(async () => {
      throw new Error("fallo de red");
    });

    render(
      <EscalationCard
        reason={REASON}
        targetProfile="deepseek-v4-pro"
        labels={LABELS}
        onEscalate={onEscalate}
        onNavigateEscalated={onNavigate}
      />,
    );

    await user.click(screen.getByRole("button", { name: LABELS.confirm }));

    // De nuevo en reposo: ambos botones disponibles, sin role="alert".
    const confirm = (await screen.findByRole("button", {
      name: LABELS.confirm,
    })) as HTMLButtonElement;
    expect(confirm.disabled).toBe(false);
    expect(onNavigate).not.toHaveBeenCalled();
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
