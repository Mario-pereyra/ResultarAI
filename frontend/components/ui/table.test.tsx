import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "./table";

describe("Table", () => {
  // Escenario "Tabla densa con datos monoespaciados" —
  // openspec/changes/d10-design-system-shell/specs/design-system/spec.md
  it('escenario "Tabla densa con datos monoespaciados": .table--dense y columna numérica con .num', () => {
    render(
      <Table caption="Parámetros MV comparados" dense>
        <TableHead>
          <TableRow>
            <TableHeaderCell>Parámetro</TableHeaderCell>
            <TableHeaderCell>Monto</TableHeaderCell>
          </TableRow>
        </TableHead>
        <TableBody>
          <TableRow>
            <TableCell>MV_PAISLOC</TableCell>
            <TableCell numeric>USD 0,0008</TableCell>
          </TableRow>
        </TableBody>
      </Table>,
    );

    const table = screen.getByRole("table", { name: "Parámetros MV comparados" });
    expect(table.className).toContain("table");
    expect(table.className).toContain("table--dense");

    const numericCell = screen.getByText("USD 0,0008");
    expect(numericCell.tagName).toBe("TD");
    expect(numericCell.className).toContain("num");
  });

  it("envuelve la tabla en .table-wrap para el scroll propio", () => {
    const { container } = render(
      <Table caption="Tabla">
        <TableBody>
          <TableRow>
            <TableCell>valor</TableCell>
          </TableRow>
        </TableBody>
      </Table>,
    );

    const wrap = container.querySelector(".table-wrap");
    expect(wrap).not.toBeNull();
    expect(wrap?.querySelector("table.table")).not.toBeNull();
  });

  it("las celdas de encabezado usan scope=col", () => {
    render(
      <Table caption="Tabla">
        <TableHead>
          <TableRow>
            <TableHeaderCell>Columna A</TableHeaderCell>
          </TableRow>
        </TableHead>
        <TableBody>
          <TableRow>
            <TableCell>valor</TableCell>
          </TableRow>
        </TableBody>
      </Table>,
    );

    const th = screen.getByRole("columnheader", { name: "Columna A" });
    expect(th.getAttribute("scope")).toBe("col");
  });

  it("una fila seleccionada agrega la clase is-selected", () => {
    render(
      <Table caption="Tabla">
        <TableBody>
          <TableRow selected data-testid="row">
            <TableCell>valor</TableCell>
          </TableRow>
        </TableBody>
      </Table>,
    );

    expect(screen.getByTestId("row").className).toContain("is-selected");
  });

  it("captionHidden aplica la clase de ocultamiento visual sin quitar el caption del DOM", () => {
    render(
      <Table caption="Tabla oculta visualmente" captionHidden>
        <TableBody>
          <TableRow>
            <TableCell>valor</TableCell>
          </TableRow>
        </TableBody>
      </Table>,
    );

    const table = screen.getByRole("table", { name: "Tabla oculta visualmente" });
    const caption = table.querySelector("caption");
    expect(caption?.textContent).toBe("Tabla oculta visualmente");
    expect(caption?.className).toContain("table-caption--hidden");
  });
});
