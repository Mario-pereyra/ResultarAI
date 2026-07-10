import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { VersionSelector, type VersionSelectorLabels } from "./version-selector";

const LABELS: VersionSelectorLabels = {
  versionAriaLabel: "versión {n} de {m}",
  previousVersion: "Versión anterior",
  nextVersion: "Versión siguiente",
};

describe("VersionSelector (tarea 5.4)", () => {
  it('muestra el "N/M" visual y anuncia "versión N de M" en el aria-label del grupo', () => {
    render(<VersionSelector index={2} count={2} onPrev={() => {}} onNext={() => {}} labels={LABELS} />);
    expect(screen.getByText("2/2")).toBeTruthy();
    expect(screen.getByRole("group", { name: "versión 2 de 2" })).toBeTruthy();
  });

  it("las flechas ‹ › tienen aria-label propio y disparan onPrev/onNext", async () => {
    const user = userEvent.setup();
    const onPrev = vi.fn();
    const onNext = vi.fn();
    render(<VersionSelector index={1} count={3} onPrev={onPrev} onNext={onNext} labels={LABELS} />);

    await user.click(screen.getByRole("button", { name: "Versión anterior" }));
    await user.click(screen.getByRole("button", { name: "Versión siguiente" }));
    expect(onPrev).toHaveBeenCalledTimes(1);
    expect(onNext).toHaveBeenCalledTimes(1);
  });

  it("deshabilita ‹ en la primera versión y › en la última (extremos)", () => {
    const prevBtn = () => screen.getByRole("button", { name: "Versión anterior" }) as HTMLButtonElement;
    const nextBtn = () => screen.getByRole("button", { name: "Versión siguiente" }) as HTMLButtonElement;

    const { rerender } = render(<VersionSelector index={1} count={2} onNext={() => {}} labels={LABELS} />);
    expect(prevBtn().disabled).toBe(true);
    expect(nextBtn().disabled).toBe(false);

    rerender(<VersionSelector index={2} count={2} onPrev={() => {}} labels={LABELS} />);
    expect(prevBtn().disabled).toBe(false);
    expect(nextBtn().disabled).toBe(true);
  });
});
