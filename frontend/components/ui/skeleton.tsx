/**
 * Skeleton (tarea 4.8, d10-design-system-shell).
 * Envoltorio fino sobre `.skeleton`/`.skeleton--text`/`.skeleton--title`/
 * `.skeleton--block` (styles/components/skeleton.css, portado verbatim de
 * design/mockups/tokens.css §5.11). design/DESIGN-SYSTEM.md §8.23: "solo
 * para cargas estimadas >300ms" y "contenedor aria-busy='true'".
 *
 * No es un Client Component: no usa hooks ni eventos, así que puede
 * renderizarse también desde un Server Component.
 */

export type SkeletonVariant = "text" | "title" | "block";

const VARIANT_CLASS: Record<SkeletonVariant, string> = {
  text: "skeleton skeleton--text",
  title: "skeleton skeleton--title",
  block: "skeleton skeleton--block",
};

export type SkeletonProps = {
  variant: SkeletonVariant;
  /** Número de líneas a repetir (solo variant="text"). Default 1. */
  lines?: number;
  /** Nombre accesible anunciado mientras carga, ej. "Cargando…". */
  label: string;
};

export function Skeleton({ variant, lines = 1, label }: SkeletonProps) {
  const count = variant === "text" ? Math.max(1, lines) : 1;

  return (
    <span className="skeleton-group" role="status" aria-busy="true" aria-label={label}>
      {Array.from({ length: count }, (_, index) => (
        <span key={index} className={VARIANT_CLASS[variant]} />
      ))}
    </span>
  );
}
