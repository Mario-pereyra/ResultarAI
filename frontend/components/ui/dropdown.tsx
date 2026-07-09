"use client";

import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
} from "react";

/**
 * Dropdown genérico (tarea 4.7, d10-design-system-shell).
 * Base para el menú de usuario y la campana del shell (design/DESIGN-SYSTEM.md
 * §56 "Inventario de componentes base"). No hay clase `.dropdown` en
 * design/mockups/tokens.css §5 (ver la nota de trazabilidad al inicio de
 * styles/components/dropdown.css) — este componente es el único dueño de
 * ese patrón visual y de comportamiento.
 *
 * Patrón WAI-ARIA "menu button": disparador con aria-haspopup/aria-expanded,
 * panel `role="menu"` con ítems `role="menuitem"`, navegación con flechas +
 * Home/End, Esc cierra y devuelve el foco, click fuera cierra.
 */

export type DropdownItem = {
  id: string;
  label: string;
  onSelect: () => void;
  disabled?: boolean;
  /** Ítem destructivo (ej. "Cerrar sesión"): usa `.dropdown-menu__item--danger`. */
  danger?: boolean;
  icon?: ReactNode;
};

export type DropdownProps = {
  /** Nombre accesible del disparador. Visible como texto si no se pasa `triggerIcon`. */
  triggerLabel: string;
  items: DropdownItem[];
  /** Ícono del disparador (p. ej. campana); si se pasa, va junto a `aria-label`. */
  triggerIcon?: ReactNode;
  /** Alineación del menú respecto del disparador. */
  align?: "start" | "end";
};

export function Dropdown({ triggerLabel, items, triggerIcon, align = "start" }: DropdownProps) {
  const [open, setOpen] = useState(false);
  const openFocusTarget = useRef<"first" | "last">("first");
  const rootRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const itemRefs = useRef(new Map<string, HTMLButtonElement>());
  const triggerId = useId();
  const menuId = useId();

  const enabledItems = items.filter((item) => !item.disabled);

  const focusItem = useCallback((id: string) => {
    itemRefs.current.get(id)?.focus();
  }, []);

  const focusFirst = useCallback(() => {
    const first = enabledItems[0];
    if (first) focusItem(first.id);
  }, [enabledItems, focusItem]);

  const focusLast = useCallback(() => {
    const last = enabledItems[enabledItems.length - 1];
    if (last) focusItem(last.id);
  }, [enabledItems, focusItem]);

  const focusOffset = useCallback(
    (currentId: string, offset: number) => {
      if (enabledItems.length === 0) return;
      const index = enabledItems.findIndex((item) => item.id === currentId);
      if (index === -1) {
        focusFirst();
        return;
      }
      const nextIndex = (index + offset + enabledItems.length) % enabledItems.length;
      focusItem(enabledItems[nextIndex].id);
    },
    [enabledItems, focusFirst, focusItem],
  );

  function openMenu(target: "first" | "last") {
    openFocusTarget.current = target;
    setOpen(true);
  }

  function close(returnFocus: boolean) {
    setOpen(false);
    if (returnFocus) {
      triggerRef.current?.focus();
    }
  }

  // Al abrir, foco inicial en el primer o último ítem (según cómo se abrió:
  // click/Enter -> primero, ArrowUp en el disparador -> último).
  useEffect(() => {
    if (!open) return;
    if (openFocusTarget.current === "last") {
      focusLast();
    } else {
      focusFirst();
    }
  }, [open, focusFirst, focusLast]);

  // Click fuera del dropdown (disparador + menú) cierra sin devolver el
  // foco (design/DESIGN-SYSTEM.md §8.21: distinto de Esc, que sí lo devuelve).
  useEffect(() => {
    if (!open) return;

    function handlePointerDown(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, [open]);

  function handleTriggerClick() {
    if (open) {
      close(false);
    } else {
      openMenu("first");
    }
  }

  function handleTriggerKeyDown(event: ReactKeyboardEvent<HTMLButtonElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      openMenu("first");
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      openMenu("last");
    }
  }

  function handleMenuKeyDown(event: ReactKeyboardEvent<HTMLDivElement>) {
    const currentId = (event.target as HTMLElement).dataset.itemId;

    switch (event.key) {
      case "ArrowDown":
        event.preventDefault();
        if (currentId) focusOffset(currentId, 1);
        else focusFirst();
        break;
      case "ArrowUp":
        event.preventDefault();
        if (currentId) focusOffset(currentId, -1);
        else focusLast();
        break;
      case "Home":
        event.preventDefault();
        focusFirst();
        break;
      case "End":
        event.preventDefault();
        focusLast();
        break;
      case "Escape":
        event.preventDefault();
        close(true);
        break;
      case "Tab":
        // Un menú WAI-ARIA no es parte del tab order: Tab lo cierra y deja
        // que el foco siga su curso natural hacia el siguiente elemento.
        setOpen(false);
        break;
      default:
        break;
    }
  }

  function handleItemSelect(item: DropdownItem) {
    if (item.disabled) return;
    item.onSelect();
    close(true);
  }

  return (
    <div className="dropdown" ref={rootRef}>
      <button
        type="button"
        id={triggerId}
        ref={triggerRef}
        className="dropdown__trigger"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={menuId}
        aria-label={triggerIcon ? triggerLabel : undefined}
        onClick={handleTriggerClick}
        onKeyDown={handleTriggerKeyDown}
      >
        {triggerIcon ? <span aria-hidden="true">{triggerIcon}</span> : triggerLabel}
      </button>
      {open ? (
        <div
          id={menuId}
          role="menu"
          aria-labelledby={triggerId}
          className={align === "end" ? "dropdown-menu dropdown-menu--end" : "dropdown-menu"}
          onKeyDown={handleMenuKeyDown}
        >
          {items.map((item) => (
            <button
              key={item.id}
              type="button"
              role="menuitem"
              data-item-id={item.id}
              tabIndex={-1}
              disabled={item.disabled}
              className={
                item.danger ? "dropdown-menu__item dropdown-menu__item--danger" : "dropdown-menu__item"
              }
              ref={(node) => {
                if (node) itemRefs.current.set(item.id, node);
                else itemRefs.current.delete(item.id);
              }}
              onClick={() => handleItemSelect(item)}
            >
              {item.icon ? (
                <span aria-hidden="true">{item.icon}</span>
              ) : null}
              {item.label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
