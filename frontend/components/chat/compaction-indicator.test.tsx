import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { CompactionIndicator } from "./compaction-indicator";

describe("CompactionIndicator (tarea 5.6)", () => {
  it("renderiza el texto informativo dentro de un role='note' (no bloquea, no interrumpe)", () => {
    render(<CompactionIndicator label="Resumimos el historial de esta conversación." />);
    const note = screen.getByRole("note");
    expect(note.textContent).toContain("Resumimos el historial de esta conversación.");
  });
});
