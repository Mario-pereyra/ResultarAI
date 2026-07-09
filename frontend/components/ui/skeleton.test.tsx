import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Skeleton } from "./skeleton";

describe("Skeleton", () => {
  it("renderiza un bloque skeleton--title con aria-busy y aria-label", () => {
    render(<Skeleton variant="title" label="Cargando título" />);

    const status = screen.getByRole("status", { name: "Cargando título" });
    expect(status.getAttribute("aria-busy")).toBe("true");
    expect(status.querySelectorAll(".skeleton--title")).toHaveLength(1);
  });

  it("renderiza N líneas skeleton--text cuando variant=text y lines>1", () => {
    render(<Skeleton variant="text" lines={3} label="Cargando líneas" />);

    const status = screen.getByRole("status", { name: "Cargando líneas" });
    expect(status.querySelectorAll(".skeleton--text")).toHaveLength(3);
  });

  it("ignora `lines` para variantes distintas de text", () => {
    render(<Skeleton variant="block" lines={5} label="Cargando bloque" />);

    const status = screen.getByRole("status", { name: "Cargando bloque" });
    expect(status.querySelectorAll(".skeleton--block")).toHaveLength(1);
  });
});
