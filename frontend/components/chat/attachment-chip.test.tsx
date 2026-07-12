import userEvent from "@testing-library/user-event";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { AttachmentItem } from "@/lib/chat/attachment-adapter";
import { AttachmentChip, type AttachmentChipLabels } from "./attachment-chip";

/**
 * Tests unitarios del chip de adjunto (d14-attachments, tarea 8.2) --
 * `composer.test.tsx` cubre la integración vía `Composer`; acá se aísla el
 * componente para cubrir puntualmente lo que ese nivel de integración no
 * ejercita cómodamente: el `role` ARIA por urgencia (`alert` vs `status`,
 * ANEXO §6 "nunca... silencioso") y el punto de integración opcional de la
 * tarea 8.3 (`onOpenPreview`).
 */

const LABELS: AttachmentChipLabels = {
  states: {
    uploading: "Subiendo… {percent}%",
    processing: "Procesando contenido…",
    readyTechAdmin: "Listo · {tokens} tokens",
    readyFunctional: "Listo · usa {percent}% del espacio del mensaje",
    readyTruncated: "Listo · incluye el {percent}% del archivo — tocá para ver qué verá el agente",
    warning: "Revisá antes de enviar",
    blocked: "Bloqueado — contiene credenciales",
    error: "No se pudo procesar",
  },
  removeAttachment: "Quitar adjunto {file}",
  piiConfirmation: "Confirmo que son datos de prueba",
  piiCancel: "Cancelar",
};

function makeItem(overrides: Partial<AttachmentItem> = {}): AttachmentItem {
  return {
    id: "attachment-local-1",
    attachmentId: "real-id-1",
    file: new File(["contenido"], "balance.xlsx"),
    originalName: "balance.xlsx",
    status: "ready",
    sendable: true,
    requiresTestDataConfirmation: false,
    tokenCount: 8200,
    includedPercent: 100,
    truncated: false,
    message: null,
    confirming: false,
    ...overrides,
  };
}

describe("AttachmentChip — data-attachment-status y aria por urgencia", () => {
  it.each([
    ["uploading", "status"],
    ["processing", "status"],
    ["ready", "status"],
    ["warning", "status"],
    ["blocked", "alert"],
    ["error", "alert"],
  ] as const)("estado %s usa role=%s en el texto de estado", (status, expectedRole) => {
    const item = makeItem({ status, sendable: status === "ready" });
    render(
      <ul>
        <AttachmentChip
          item={item}
          role="funcional"
          labels={LABELS}
          onRemove={vi.fn()}
          onConfirmTestData={vi.fn()}
        />
      </ul>,
    );

    expect(screen.getByRole(expectedRole)).toBeTruthy();
  });

  it("expone data-attachment-status para estilos/tests futuros", () => {
    const item = makeItem({ status: "blocked" });
    const { container } = render(
      <ul>
        <AttachmentChip item={item} role="admin" labels={LABELS} onRemove={vi.fn()} onConfirmTestData={vi.fn()} />
      </ul>,
    );

    expect(container.querySelector('[data-attachment-status="blocked"]')).toBeTruthy();
  });
});

describe("AttachmentChip — punto de integración de 8.3 (Ver lo que verá el agente)", () => {
  it("sin onOpenPreview: el texto truncado es texto plano, sin botón", () => {
    const item = makeItem({ status: "ready", truncated: true, includedPercent: 62 });
    render(
      <ul>
        <AttachmentChip item={item} role="admin" labels={LABELS} onRemove={vi.fn()} onConfirmTestData={vi.fn()} />
      </ul>,
    );

    expect(
      screen.getByText("Listo · incluye el 62% del archivo — tocá para ver qué verá el agente"),
    ).toBeTruthy();
    expect(screen.queryByRole("button", { name: /incluye el 62%/ })).toBeNull();
  });

  it("con onOpenPreview: el texto truncado es un botón que dispara el callback con el id", async () => {
    const user = userEvent.setup();
    const onOpenPreview = vi.fn();
    const item = makeItem({ status: "ready", truncated: true, includedPercent: 62 });
    render(
      <ul>
        <AttachmentChip
          item={item}
          role="admin"
          labels={LABELS}
          onRemove={vi.fn()}
          onConfirmTestData={vi.fn()}
          onOpenPreview={onOpenPreview}
        />
      </ul>,
    );

    const trigger = screen.getByRole("button", { name: /incluye el 62%/ });
    await user.click(trigger);
    expect(onOpenPreview).toHaveBeenCalledWith(item.id);
  });

  it("listo sin truncar: onOpenPreview no agrega ningún botón (el disparador es solo del truncado)", () => {
    const item = makeItem({ status: "ready", truncated: false, tokenCount: 100 });
    render(
      <ul>
        <AttachmentChip
          item={item}
          role="tecnico"
          labels={LABELS}
          onRemove={vi.fn()}
          onConfirmTestData={vi.fn()}
          onOpenPreview={vi.fn()}
        />
      </ul>,
    );

    expect(screen.getByText("Listo · 100 tokens")).toBeTruthy();
  });
});

describe("AttachmentChip — quitar", () => {
  it("el × general siempre está presente y llama a onRemove(id)", async () => {
    const user = userEvent.setup();
    const onRemove = vi.fn();
    const item = makeItem();
    render(
      <ul>
        <AttachmentChip item={item} role="funcional" labels={LABELS} onRemove={onRemove} onConfirmTestData={vi.fn()} />
      </ul>,
    );

    await user.click(screen.getByRole("button", { name: "Quitar adjunto balance.xlsx" }));
    expect(onRemove).toHaveBeenCalledWith(item.id);
  });
});
