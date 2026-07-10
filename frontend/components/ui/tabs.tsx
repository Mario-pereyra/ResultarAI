"use client";

import { useRef, type KeyboardEvent } from "react";

export interface TabItem {
  id: string;
  label: string;
  /** Contador opcional mostrado en un `.tag` a la derecha del label (ej.
   * "Activas 12", `design/mockups/tokens.css` §5.16). `undefined` no
   * renderiza ningún contador. */
  count?: number;
}

export interface TabsProps {
  /** `aria-label` del `role="tablist"` (nombre accesible del grupo). */
  label: string;
  items: TabItem[];
  activeId: string;
  onChange: (id: string) => void;
}

/**
 * `.tabs`/`.tab` -- envoltorio fino sobre design/mockups/tokens.css §5.16
 * (d13-chat-conversacion, tarea 7.1, `design/VISTAS/02-chat.md` vista 12:
 * tabs "Activas/Archivadas" con contador). Sin consumidor previo en el
 * frontend -- primer componente `role="tablist"` del proyecto -- así que
 * sigue el patrón WAI-ARIA APG de "tabs" con activación automática: las
 * flechas ←/→ mueven el foco Y activan el tab (sin necesitar Enter/Espacio
 * aparte), con `tabIndex` en rueda (roving tabindex: solo el tab activo es
 * parte del orden de tabulación).
 *
 * Presentacional/controlado: no posee el estado de qué tab está activo (lo
 * decide `activeId`, que el caller controla) -- mismo criterio que el resto
 * de `components/ui/*`.
 */
export function Tabs({ label, items, activeId, onChange }: TabsProps) {
  const buttonRefs = useRef<Record<string, HTMLButtonElement | null>>({});

  function focusAndSelect(index: number) {
    const target = items[(index + items.length) % items.length];
    if (!target) return;
    onChange(target.id);
    buttonRefs.current[target.id]?.focus();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    if (event.key === "ArrowRight") {
      event.preventDefault();
      focusAndSelect(index + 1);
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      focusAndSelect(index - 1);
    } else if (event.key === "Home") {
      event.preventDefault();
      focusAndSelect(0);
    } else if (event.key === "End") {
      event.preventDefault();
      focusAndSelect(items.length - 1);
    }
  }

  return (
    <div className="tabs" role="tablist" aria-label={label}>
      {items.map((item, index) => {
        const isActive = item.id === activeId;
        return (
          <button
            key={item.id}
            ref={(el) => {
              buttonRefs.current[item.id] = el;
            }}
            type="button"
            role="tab"
            id={`tab-${item.id}`}
            aria-selected={isActive}
            aria-controls={`tabpanel-${item.id}`}
            tabIndex={isActive ? 0 : -1}
            className={["tab", isActive ? "is-active" : ""].filter(Boolean).join(" ")}
            onClick={() => onChange(item.id)}
            onKeyDown={(event) => handleKeyDown(event, index)}
          >
            {item.label}
            {/* Espacio literal antes del contador: sin él, JSX no deja
                ningún carácter separador entre dos expresiones en líneas
                distintas y el nombre accesible del botón queda pegado
                ("Activas12" en vez de "Activas 12"). */}
            {item.count !== undefined ? <> <span className="tag">{item.count}</span></> : null}
          </button>
        );
      })}
    </div>
  );
}
