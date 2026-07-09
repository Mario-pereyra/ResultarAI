"use client";

import { useRef, type ReactNode, type TouchEvent as ReactTouchEvent } from "react";
import { Tooltip } from "@/components/ui/tooltip";
import type { Section } from "@/lib/capabilities";
import { useSession } from "@/lib/session-context";
import { useFocusTrap } from "@/lib/use-focus-trap";
import {
  AdministracionIcon,
  AprobacionesIcon,
  CatalogoIcon,
  ChatIcon,
  CollapseIcon,
  ConstruccionIcon,
  ExpandIcon,
  MiEspacioIcon,
  SearchIcon,
  WorkflowsIcon,
} from "./icons";

/**
 * Sidebar (tarea 5.3 + drawer móvil de la tarea 5.7, d10-design-system-shell).
 *
 * Orden fijo de ítems = design/mockups/03-shell.html (Catálogo · Chat ·
 * Workflows · Aprobaciones · Mi espacio · divisor kicker "ADMIN" ·
 * Administración · Construcción). Filtrado por `useSession().capabilities`
 * (Decision 7, design.md): una sección no habilitada NO se renderiza en el
 * DOM (ocultar, no deshabilitar — DS §9.7), escenarios "Rol Funcional no ve
 * secciones de Admin" / "Rol Admin ve todas las secciones".
 *
 * El mismo listado de navegación se usa dos veces: como `<aside>` fijo en
 * desktop y, cuando `drawerOpen`, como drawer móvil con trampa de foco
 * (`lib/use-focus-trap.ts`, el mismo hook que usa `Modal`) — escenario
 * "Drawer con trampa de foco en móvil". CSS (`styles/shell.css`) decide cuál
 * de los dos se ve según el viewport.
 *
 * Las rutas de las secciones sin página propia todavía (`/chat`,
 * `/workflows`, …) apuntan a su path final aunque hoy no exista ninguna
 * página ahí (404 hasta que d13-d21 las construyan) — `/` es la única real
 * hoy (Catálogo, tarea de scaffolding movida a `app/(shell)/page.tsx`).
 */

const SECTION_ORDER: Section[] = ["catalogo", "chat", "workflows", "aprobaciones", "mi-espacio"];
const ADMIN_SECTIONS: Section[] = ["administracion", "construccion"];

const SECTION_HREF: Record<Section, string> = {
  catalogo: "/",
  chat: "/chat",
  workflows: "/workflows",
  aprobaciones: "/aprobaciones",
  "mi-espacio": "/mi-espacio",
  administracion: "/administracion",
  construccion: "/construccion",
};

const SECTION_ICON: Record<Section, ReactNode> = {
  catalogo: <CatalogoIcon />,
  chat: <ChatIcon />,
  workflows: <WorkflowsIcon />,
  aprobaciones: <AprobacionesIcon />,
  "mi-espacio": <MiEspacioIcon />,
  administracion: <AdministracionIcon />,
  construccion: <ConstruccionIcon />,
};

/** Única sección con página real hoy — ver comentario de cabecera. */
const ACTIVE_SECTION: Section = "catalogo";

/** Swipe horizontal mínimo (px) para interpretar un gesto como "cerrar drawer". */
const SWIPE_CLOSE_THRESHOLD_PX = 60;

export type SidebarLabels = {
  instanceName: string;
  sectionLabels: Record<Section, string>;
  adminKicker: string;
  collapse: string;
  expand: string;
  navLabel: string;
  drawerLabel: string;
  approvalsAriaLabel: string;
  /** Vista 3, sección Móvil: "el buscador vive dentro del drawer". Visual, sin backend. */
  drawerSearchPlaceholder: string;
};

export type SidebarProps = {
  labels: SidebarLabels;
  collapsed: boolean;
  onToggleCollapse: () => void;
  drawerOpen: boolean;
  onCloseDrawer: () => void;
};

export function Sidebar({ labels, collapsed, onToggleCollapse, drawerOpen, onCloseDrawer }: SidebarProps) {
  const { capabilities, pendingApprovals } = useSession();
  const drawerRef = useRef<HTMLDivElement | null>(null);
  const touchStartX = useRef<number | null>(null);

  useFocusTrap(drawerOpen, drawerRef, { onClose: onCloseDrawer });

  function handleTouchStart(event: ReactTouchEvent<HTMLDivElement>) {
    touchStartX.current = event.touches[0]?.clientX ?? null;
  }

  function handleTouchEnd(event: ReactTouchEvent<HTMLDivElement>) {
    if (touchStartX.current === null) return;
    const endX = event.changedTouches[0]?.clientX ?? touchStartX.current;
    const delta = endX - touchStartX.current;
    touchStartX.current = null;
    // Swipe hacia la izquierda (el drawer vive pegado al borde izquierdo).
    if (delta < -SWIPE_CLOSE_THRESHOLD_PX) {
      onCloseDrawer();
    }
  }

  const nav = (
    <SidebarNav
      labels={labels}
      capabilities={capabilities}
      pendingApprovals={pendingApprovals}
      collapsed={collapsed}
    />
  );

  return (
    <>
      <aside
        className={
          collapsed ? "shell-sidebar shell-sidebar--desktop is-collapsed" : "shell-sidebar shell-sidebar--desktop"
        }
      >
        <div className="shell-sidebar__logo">
          <i className="shell-sidebar__mark" aria-hidden="true">
            R
          </i>
          <b className="shell-sidebar__name">{labels.instanceName}</b>
        </div>
        {nav}
        <div className="shell-sidebar__footer">
          <button
            type="button"
            className="shell-sidebar__collapse-btn"
            aria-pressed={collapsed}
            onClick={onToggleCollapse}
          >
            {collapsed ? <ExpandIcon /> : <CollapseIcon />}
            <span className="shell-sidebar__label">{collapsed ? labels.expand : labels.collapse}</span>
          </button>
        </div>
      </aside>

      {drawerOpen ? (
        <>
          <div className="shell-drawer-scrim" aria-hidden="true" onClick={onCloseDrawer} />
          <div
            className="shell-drawer"
            role="dialog"
            aria-modal="true"
            aria-label={labels.drawerLabel}
            ref={drawerRef}
            onTouchStart={handleTouchStart}
            onTouchEnd={handleTouchEnd}
          >
            <aside className="shell-sidebar">
              <div className="shell-sidebar__logo">
                <i className="shell-sidebar__mark" aria-hidden="true">
                  R
                </i>
                <b className="shell-sidebar__name">{labels.instanceName}</b>
              </div>
              <div className="shell-drawer__search shell-topbar__search">
                <SearchIcon />
                <input
                  type="search"
                  className="shell-topbar__search-input"
                  placeholder={labels.drawerSearchPlaceholder}
                  aria-label={labels.drawerSearchPlaceholder}
                />
              </div>
              <SidebarNav
                labels={labels}
                capabilities={capabilities}
                pendingApprovals={pendingApprovals}
                collapsed={false}
              />
            </aside>
          </div>
        </>
      ) : null}
    </>
  );
}

type SidebarNavProps = {
  labels: SidebarLabels;
  capabilities: Section[];
  pendingApprovals: number;
  collapsed: boolean;
};

function SidebarNav({ labels, capabilities, pendingApprovals, collapsed }: SidebarNavProps) {
  const hasAdminSections = ADMIN_SECTIONS.some((section) => capabilities.includes(section));

  return (
    <nav className="shell-sidebar__nav" aria-label={labels.navLabel}>
      {SECTION_ORDER.filter((section) => capabilities.includes(section)).map((section) => (
        <SidebarLink
          key={section}
          section={section}
          label={labels.sectionLabels[section]}
          collapsed={collapsed}
          badge={section === "aprobaciones" && pendingApprovals > 0 ? formatBadge(pendingApprovals) : null}
          badgeAriaLabel={section === "aprobaciones" ? labels.approvalsAriaLabel : undefined}
        />
      ))}

      {hasAdminSections ? (
        <span className="shell-sidebar__kicker">{labels.adminKicker}</span>
      ) : null}
      {ADMIN_SECTIONS.filter((section) => capabilities.includes(section)).map((section) => (
        <SidebarLink
          key={section}
          section={section}
          label={labels.sectionLabels[section]}
          collapsed={collapsed}
          badge={null}
        />
      ))}
    </nav>
  );
}

type SidebarLinkProps = {
  section: Section;
  label: string;
  collapsed: boolean;
  badge: string | null;
  badgeAriaLabel?: string;
};

function SidebarLink({ section, label, collapsed, badge, badgeAriaLabel }: SidebarLinkProps) {
  const isActive = section === ACTIVE_SECTION;
  const link = (
    <a
      href={SECTION_HREF[section]}
      className={isActive ? "shell-sidebar__link is-active" : "shell-sidebar__link"}
      aria-current={isActive ? "page" : undefined}
      aria-label={badge && badgeAriaLabel ? badgeAriaLabel : undefined}
    >
      {SECTION_ICON[section]}
      <span className="shell-sidebar__label">{label}</span>
      {badge ? (
        <span className="shell-sidebar__badge" aria-hidden="true">
          {badge}
        </span>
      ) : null}
    </a>
  );

  return collapsed ? <Tooltip label={label}>{link}</Tooltip> : link;
}

/** Vista 3, sección "Interacciones y casos borde": badge de aprobaciones >99 -> "99+". */
function formatBadge(count: number): string {
  return count > 99 ? "99+" : String(count);
}
