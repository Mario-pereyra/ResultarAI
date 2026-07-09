import type { HTMLAttributes } from "react";

export type Role = "admin" | "tecnico" | "funcional";

export interface RoleBadgeProps extends Omit<HTMLAttributes<HTMLSpanElement>, "children"> {
  role: Role;
  /** Texto visible del rol (p. ej. "Admin"), provisto por quien lo usa — nunca hardcodeado acá. */
  label: string;
}

/**
 * `.badge-rol` — envoltorio fino sobre design/mockups/tokens.css §5.4
 * (design/DESIGN-SYSTEM.md §8.6). Los 3 roles del producto: admin (acento) ·
 * tecnico (info) · funcional (neutral).
 */
export function RoleBadge({ role, label, className, ...rest }: RoleBadgeProps) {
  return (
    <span
      className={["badge-rol", `badge-rol--${role}`, className]
        .filter(Boolean)
        .join(" ")}
      {...rest}
    >
      {label}
    </span>
  );
}
