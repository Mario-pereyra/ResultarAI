import type { HTMLAttributes, ReactNode } from "react";

export type PanelVariant = "default" | "flush" | "raised";

export interface PanelProps extends HTMLAttributes<HTMLDivElement> {
  /** `--flush` (tablas embebidas, sin padding) · `--raised` (destacada, sombra mayor). */
  variant?: PanelVariant;
  children: ReactNode;
}

/**
 * `.panel` — envoltorio fino sobre design/mockups/tokens.css §5.1
 * (design/DESIGN-SYSTEM.md §8.5). Superficie contenedora estándar:
 * cards, fichas, secciones de formulario.
 */
export function Panel({
  variant = "default",
  className,
  children,
  ...rest
}: PanelProps) {
  const variantClass = variant === "default" ? "" : `panel--${variant}`;

  return (
    <div className={["panel", variantClass, className].filter(Boolean).join(" ")} {...rest}>
      {children}
    </div>
  );
}
