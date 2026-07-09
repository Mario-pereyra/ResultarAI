/**
 * SkipLink (tarea 5.7, d10-design-system-shell).
 * `.skip-link` (styles/shell.css): sr-only hasta enfocarse, primer elemento
 * enfocable del documento (escenario "Skip-link es el primer foco",
 * openspec/changes/d10-design-system-shell/specs/app-shell/spec.md) — para
 * eso debe ser literalmente el primer nodo renderizado por
 * `components/shell/shell-frame.tsx`, antes del banner IA y del sidebar.
 * No es un Client Component: es un `<a href="#id">` puro, sin estado ni
 * eventos.
 */

export type SkipLinkProps = {
  /** Texto visible al enfocarse (catálogo i18n, Shell.skipLink). */
  label: string;
  /** id del `<main>` al que salta (ver components/shell/shell-frame.tsx). */
  targetId: string;
};

export function SkipLink({ label, targetId }: SkipLinkProps) {
  return (
    <a href={`#${targetId}`} className="skip-link">
      {label}
    </a>
  );
}
