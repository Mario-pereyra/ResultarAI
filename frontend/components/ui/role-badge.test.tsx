import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { RoleBadge } from "./role-badge";

describe("RoleBadge", () => {
  it.each([
    ["admin", "Admin", "badge-rol--admin"],
    ["tecnico", "Técnico", "badge-rol--tecnico"],
    ["funcional", "Funcional", "badge-rol--funcional"],
  ] as const)("renderiza el rol %s con su clase y label", (role, label, expectedClass) => {
    render(<RoleBadge role={role} label={label} />);

    const badge = screen.getByText(label);
    expect(badge.className.split(" ")).toEqual(
      expect.arrayContaining(["badge-rol", expectedClass]),
    );
  });

  it("el texto del rol llega por props, nunca hardcodeado en el componente", () => {
    render(<RoleBadge role="admin" label="Administradora" />);

    expect(screen.getByText("Administradora")).toBeTruthy();
  });
});
