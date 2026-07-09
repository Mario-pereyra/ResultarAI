"use client";

import { cloneElement, isValidElement, type ReactElement } from "react";

/**
 * Tooltip (tarea 4.8, d10-design-system-shell).
 * Envoltorio sobre el patrón `[data-tip]` (styles/components/tooltip.css,
 * portado verbatim de design/mockups/tokens.css §5.17): la burbuja y su
 * visibilidad en hover Y focus-visible son 100% CSS (`[data-tip]:hover::after,
 * [data-tip]:focus-visible::after`). Este componente solo estampa el
 * atributo `data-tip` sobre su único hijo, para no tener que escribir
 * `data-tip="..."` a mano en cada sitio de uso.
 *
 * design/DESIGN-SYSTEM.md §8.10: "Contenido máximo ~8 palabras; más que eso
 * es un popover/sheet" y "complementa, no sustituye: el dato esencial debe
 * estar accesible sin hover" — el hijo debe ya tener su propio nombre
 * accesible (texto visible o aria-label); el tooltip es un plus visual, no
 * la única vía al contenido (por eso no gestiona foco ni aria-describedby).
 */

export type TooltipProps = {
  /** Texto de la burbuja. Idealmente ≤8 palabras (design/DESIGN-SYSTEM.md §8.10). */
  label: string;
  /** Único hijo, debe ser un elemento enfocable (botón, link, input...). */
  children: ReactElement<Record<string, unknown>>;
};

export function Tooltip({ label, children }: TooltipProps) {
  if (!isValidElement(children)) return children;

  return cloneElement(children, {
    "data-tip": label,
  });
}
