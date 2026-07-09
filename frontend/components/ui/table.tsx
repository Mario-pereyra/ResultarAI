import type {
  HTMLAttributes,
  ReactNode,
  TableHTMLAttributes,
  TdHTMLAttributes,
  ThHTMLAttributes,
} from "react";

export interface TableProps
  extends Omit<TableHTMLAttributes<HTMLTableElement>, "children"> {
  /** Texto del `<caption>`. Requerido (design/DESIGN-SYSTEM.md §8.4: "<caption> (visible u oculta)"). */
  caption: string;
  /** Oculta visualmente el caption manteniéndolo accesible (`.table-caption--hidden`). */
  captionHidden?: boolean;
  /** `.table--dense`: padding vertical de celda 6px (design/DESIGN-SYSTEM.md §6.1/§8.4). */
  dense?: boolean;
  children: ReactNode;
}

/**
 * `.table-wrap` + `.table` — envoltorio fino sobre design/mockups/tokens.css
 * §5.6. Usar junto con `TableHead`/`TableBody`/`TableRow`/`TableHeaderCell`/
 * `TableCell` para armar filas y columnas con la semántica/ARIA correcta.
 */
export function Table({
  caption,
  captionHidden = false,
  dense = false,
  className,
  children,
  ...rest
}: TableProps) {
  return (
    <div className="table-wrap">
      <table
        className={["table", dense ? "table--dense" : "", className]
          .filter(Boolean)
          .join(" ")}
        {...rest}
      >
        <caption className={captionHidden ? "table-caption--hidden" : undefined}>
          {caption}
        </caption>
        {children}
      </table>
    </div>
  );
}

export function TableHead({
  children,
  ...rest
}: HTMLAttributes<HTMLTableSectionElement>) {
  return <thead {...rest}>{children}</thead>;
}

export function TableBody({
  children,
  ...rest
}: HTMLAttributes<HTMLTableSectionElement>) {
  return <tbody {...rest}>{children}</tbody>;
}

export interface TableRowProps extends HTMLAttributes<HTMLTableRowElement> {
  /** `.is-selected` — fila seleccionada (fondo `--accent-soft`). */
  selected?: boolean;
  children: ReactNode;
}

export function TableRow({
  selected = false,
  className,
  children,
  ...rest
}: TableRowProps) {
  return (
    <tr
      className={[selected ? "is-selected" : "", className]
        .filter(Boolean)
        .join(" ") || undefined}
      {...rest}
    >
      {children}
    </tr>
  );
}

export interface TableHeaderCellProps
  extends ThHTMLAttributes<HTMLTableCellElement> {
  children: ReactNode;
}

/** `<th>` con `scope="col"` por defecto (design/DESIGN-SYSTEM.md §8.4). */
export function TableHeaderCell({
  scope = "col",
  children,
  ...rest
}: TableHeaderCellProps) {
  return (
    <th scope={scope} {...rest}>
      {children}
    </th>
  );
}

export interface TableCellProps extends TdHTMLAttributes<HTMLTableCellElement> {
  /** `.num`: datos operativos alineados a la derecha, mono, tabular-nums. */
  numeric?: boolean;
  children: ReactNode;
}

export function TableCell({
  numeric = false,
  className,
  children,
  ...rest
}: TableCellProps) {
  return (
    <td
      className={[numeric ? "num" : "", className].filter(Boolean).join(" ") || undefined}
      {...rest}
    >
      {children}
    </td>
  );
}
