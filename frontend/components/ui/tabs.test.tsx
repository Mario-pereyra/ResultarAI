import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Tabs } from "./tabs";

const ITEMS = [
  { id: "active", label: "Activas", count: 12 },
  { id: "archived", label: "Archivadas", count: 3 },
];

describe("Tabs", () => {
  it("renderiza role=tablist/tab con aria-selected y el contador de cada tab", () => {
    render(<Tabs label="Estado de las sesiones" items={ITEMS} activeId="active" onChange={vi.fn()} />);

    const tablist = screen.getByRole("tablist", { name: "Estado de las sesiones" });
    expect(tablist).toBeTruthy();

    const active = screen.getByRole("tab", { name: "Activas 12" });
    const archived = screen.getByRole("tab", { name: "Archivadas 3" });
    expect(active.getAttribute("aria-selected")).toBe("true");
    expect(archived.getAttribute("aria-selected")).toBe("false");
    expect(active.tabIndex).toBe(0);
    expect(archived.tabIndex).toBe(-1);
  });

  it("click en un tab inactivo dispara onChange con su id", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Tabs label="Estado de las sesiones" items={ITEMS} activeId="active" onChange={onChange} />);

    await user.click(screen.getByRole("tab", { name: "Archivadas 3" }));
    expect(onChange).toHaveBeenCalledWith("archived");
  });

  it("ArrowRight/ArrowLeft mueve el foco y activa el tab siguiente/anterior (WAI-ARIA APG)", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Tabs label="Estado de las sesiones" items={ITEMS} activeId="active" onChange={onChange} />);

    screen.getByRole("tab", { name: "Activas 12" }).focus();
    await user.keyboard("{ArrowRight}");
    expect(onChange).toHaveBeenCalledWith("archived");

    await user.keyboard("{ArrowLeft}");
    expect(onChange).toHaveBeenCalledWith("active");
  });
});
