"use client";

export interface VersionSelectorLabels {
  /** Plantilla del `aria-label` del selector con placeholders `{n}` y `{m}`
   * (design/VISTAS/02-chat.md §5, `branch.version_label` ICU «versión {n} de
   * {m}»): lo lee el lector de pantalla en vez del "N/M" visual, que NO se
   * traduce (DS §4.2). Se interpola acá con los valores en vivo porque `n`/`m`
   * son datos de runtime del cliente, no resolubles al construir las labels. */
  versionAriaLabel: string;
  /** `aria-label` de la flecha ‹ (versión anterior, más vieja). */
  previousVersion: string;
  /** `aria-label` de la flecha › (versión siguiente, más nueva). */
  nextVersion: string;
}

export interface VersionSelectorProps {
  /** Posición 1-based de la versión mostrada entre sus hermanas. */
  index: number;
  /** Cantidad total de versiones hermanas. */
  count: number;
  /** Alterna a la versión anterior; `undefined` deshabilita la flecha ‹ (extremo). */
  onPrev?: () => void;
  /** Alterna a la versión siguiente; `undefined` deshabilita la flecha › (extremo). */
  onNext?: () => void;
  labels: VersionSelectorLabels;
}

/**
 * Selector "‹ N/M ›" que se ancla junto al mensaje ramificado -- mensaje de
 * usuario editado o respuesta del agente regenerada (d13-chat-conversacion,
 * tarea 5.4, `design/VISTAS/02-chat.md` vista 09, `design/FLUJOS.md` Flujo G).
 *
 * Componente PRESENTACIONAL y controlado: no conoce el árbol de la sesión ni el
 * `BranchChoices`. Quien lo renderiza (`chat-content.tsx` vía el render-prop
 * `renderVersionSelector` de `MessageColumn`) resuelve la posición con
 * `versionNav` (`lib/chat/session-tree.ts`), le pasa `index`/`count` y conecta
 * `onPrev`/`onNext` para que alternar SOLO reemplace la versión elegida en el
 * estado local (el árbol nunca se muta) y re-renderice la porción posterior de la
 * rama. Las flechas quedan deshabilitadas en los extremos (sin `onPrev`/`onNext`).
 *
 * El objetivo táctil ≥44 px de las flechas (vista 09 §Móvil) se ajusta en la
 * tarea 8.1; acá se dejan botones-ícono accesibles con `aria-label` propio y el
 * "N/M" visual marcado `aria-hidden` (el grupo ya anuncia "versión N de M").
 */
export function VersionSelector({ index, count, onPrev, onNext, labels }: VersionSelectorProps) {
  const ariaLabel = labels.versionAriaLabel
    .replace("{n}", String(index))
    .replace("{m}", String(count));

  return (
    <div className="branch-sel" role="group" aria-label={ariaLabel} data-testid="version-selector">
      <button
        type="button"
        className="branch-sel__arrow"
        aria-label={labels.previousVersion}
        disabled={!onPrev}
        onClick={onPrev}
      >
        ‹
      </button>
      <span className="branch-sel__count" aria-hidden="true">
        {index}/{count}
      </span>
      <button
        type="button"
        className="branch-sel__arrow"
        aria-label={labels.nextVersion}
        disabled={!onNext}
        onClick={onNext}
      >
        ›
      </button>
    </div>
  );
}
