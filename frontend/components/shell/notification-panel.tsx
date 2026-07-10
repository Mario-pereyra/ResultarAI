"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { BellIcon } from "./icons";

export interface NotificationItem {
  id: string;
  type: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload: Record<string, any>;
  deep_link: string | null;
  read: boolean;
  created_at: string;
}

export interface NotificationPanelLabels {
  notifications: string;
  notificationsEmpty: string;
  notificationsEmptyHint: string;
  notificationsError: string;
  notificationsRetry: string;
  notificationsMarkAllRead: string;
  notificationsViewAll: string;
  notificationsView: string;
  notificationsClose: string;
  notificationsKickerCuotas: string;
  notificationsKickerSistema: string;
  notificationsKickerAprobaciones: string;
}

export interface NotificationPanelProps {
  labels: NotificationPanelLabels;
  initialCount?: number;
}

const QuotaIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="notif-panel__item-icon">
    <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
    <line x1="12" y1="9" x2="12" y2="13" />
    <line x1="12" y1="17" x2="12.01" y2="17" />
  </svg>
);

const CheckIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="notif-panel__item-icon">
    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
    <polyline points="22 4 12 14.01 9 11.01" />
  </svg>
);

const InfoIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="notif-panel__item-icon">
    <circle cx="12" cy="12" r="10" />
    <line x1="12" y1="16" x2="12" y2="12" />
    <line x1="12" y1="8" x2="12.01" y2="8" />
  </svg>
);

// Ícono de cierre accesible: mismo patrón que components/ui/modal.tsx
// (aria-label del botón contenedor + ícono `aria-hidden`, sin glifo de
// texto "&times;" literal).
const CloseIcon = () => (
  <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" focusable="false">
    <path d="M3 3l10 10M13 3L3 13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" fill="none" />
  </svg>
);

function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSecs = Math.floor(diffMs / 1000);
  const diffMins = Math.floor(diffSecs / 60);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  const rtf = new Intl.RelativeTimeFormat("es", { numeric: "auto" });

  if (diffSecs < 60) {
    return "hace unos segundos";
  } else if (diffMins < 60) {
    return rtf.format(-diffMins, "minute");
  } else if (diffHours < 24) {
    return rtf.format(-diffHours, "hour");
  } else {
    return rtf.format(-diffDays, "day");
  }
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function formatNotificationText(type: string, payload: Record<string, any>): string {
  if (type === "quota_release_requested") {
    const requester = payload.requestor_username || payload.requester_name || "Un usuario";
    const quota = payload.quota_name || "sin nombre";
    const usage = payload.current_consumption || payload.current_usage_pct || 0;
    return `${requester} solicita liberar cuota para ${quota} (consumo ${usage}%)`;
  }
  if (type === "quota_release_resolved") {
    const quota = payload.quota_name || "sin nombre";
    const decision = payload.decision || payload.resolution || "resolved";
    const decisionText = decision === "approved" ? "aprobada" : "denegada";
    const reason = payload.reason || payload.comment ? ` - ${payload.reason || payload.comment}` : "";
    return `Tu solicitud de liberación para ${quota} fue ${decisionText}${reason}`;
  }
  return `Notificación de tipo ${type}`;
}

function getNotificationKicker(type: string, labels: NotificationPanelLabels): string {
  if (type.startsWith("quota_")) return labels.notificationsKickerCuotas;
  if (type.startsWith("hitl_")) return labels.notificationsKickerAprobaciones;
  return labels.notificationsKickerSistema;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function getNotificationIcon(type: string, payload: Record<string, any>) {
  if (type === "quota_release_requested") return <QuotaIcon />;
  if (type === "quota_release_resolved") {
    const decision = payload.decision || payload.resolution || "";
    return decision === "approved" ? <CheckIcon /> : <InfoIcon />;
  }
  return <InfoIcon />;
}

export function NotificationPanel({ labels, initialCount = 0 }: NotificationPanelProps) {
  const router = useRouter();

  const [open, setOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(initialCount);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // Polling unread count
  const fetchUnreadCount = useCallback(async () => {
    if (document.visibilityState === "hidden") return;
    try {
      const res = await fetch("/api/notifications/unread-count");
      if (res.ok) {
        const data = await res.json();
        setUnreadCount(data.count);
      }
    } catch (err) {
      console.error("Error fetching unread count:", err);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchUnreadCount();
    const interval = setInterval(fetchUnreadCount, 30000);

    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        fetchUnreadCount();
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      clearInterval(interval);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [fetchUnreadCount]);

  // Fetch list of notifications (max 7 for preview dropdown)
  const fetchNotifications = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const res = await fetch("/api/notifications?status=all&page=1&page_size=7");
      if (res.ok) {
        const data = await res.json();
        setNotifications(data.items);
      } else {
        setError(true);
      }
    } catch (err) {
      console.error("Error fetching notifications list:", err);
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  // Open/Close toggle
  const togglePanel = () => {
    if (open) {
      setOpen(false);
      triggerRef.current?.focus();
    } else {
      setOpen(true);
      fetchNotifications();
    }
  };

  // Close panel and return focus
  const closePanel = (returnFocus = true) => {
    setOpen(false);
    if (returnFocus) {
      triggerRef.current?.focus();
    }
  };

  // Click outside to close
  useEffect(() => {
    if (!open) return;
    const handleOutsideClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        closePanel(false);
      }
    };
    document.addEventListener("mousedown", handleOutsideClick);
    return () => document.removeEventListener("mousedown", handleOutsideClick);
  }, [open]);

  // Actions
  const handleMarkAllRead = async () => {
    try {
      const csrf = document.cookie
        .split("; ")
        .find((row) => row.startsWith("resultarai_csrf="))
        ?.split("=")[1];

      const headers: Record<string, string> = {};
      if (csrf) {
        headers["X-CSRF-Token"] = csrf;
      }

      const res = await fetch("/api/notifications/read-all", {
        method: "POST",
        headers,
      });

      if (res.ok) {
        setUnreadCount(0);
        setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
      }
    } catch (err) {
      console.error("Error marking all read:", err);
    }
  };

  const handleItemClick = async (notif: NotificationItem, e: React.MouseEvent) => {
    e.preventDefault();
    closePanel(false);

    if (!notif.read) {
      try {
        const csrf = document.cookie
          .split("; ")
          .find((row) => row.startsWith("resultarai_csrf="))
          ?.split("=")[1];

        const headers: Record<string, string> = {};
        if (csrf) {
          headers["X-CSRF-Token"] = csrf;
        }

        await fetch(`/api/notifications/${notif.id}/read`, {
          method: "POST",
          headers,
        });
        fetchUnreadCount();
      } catch (err) {
        console.error("Error marking notification read:", err);
      }
    }

    if (notif.deep_link) {
      router.push(notif.deep_link);
    }
  };

  // Keyboard navigation helpers
  const getFocusableItems = (): HTMLElement[] => {
    if (!listRef.current) return [];
    const items: HTMLElement[] = [];
    const markAllBtn = containerRef.current?.querySelector(".notif-panel__mark-all") as HTMLElement;
    if (markAllBtn) items.push(markAllBtn);

    const rows = Array.from(listRef.current.querySelectorAll(".notif-panel__item")) as HTMLElement[];
    items.push(...rows);

    const viewAllLink = containerRef.current?.querySelector(".notif-panel__view-all") as HTMLElement;
    if (viewAllLink) items.push(viewAllLink);

    return items;
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      e.preventDefault();
      closePanel(true);
      return;
    }

    if (!open) return;

    const focusables = getFocusableItems();
    if (focusables.length === 0) return;

    const currentIndex = focusables.indexOf(document.activeElement as HTMLElement);

    if (e.key === "ArrowDown") {
      e.preventDefault();
      const nextIndex = (currentIndex + 1) % focusables.length;
      focusables[nextIndex]?.focus();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      const prevIndex = (currentIndex - 1 + focusables.length) % focusables.length;
      focusables[prevIndex]?.focus();
    }
  };

  // Group notifications by kicker
  const groupedNotifications: Record<string, NotificationItem[]> = {};
  notifications.forEach((notif) => {
    const kicker = getNotificationKicker(notif.type, labels);
    if (!groupedNotifications[kicker]) {
      groupedNotifications[kicker] = [];
    }
    groupedNotifications[kicker].push(notif);
  });

  // Simple and precise plural formatting for aria-label without next-intl context dependency
  const getAriaLabel = (count: number): string => {
    if (count === 0) return "Notificaciones, sin novedades";
    if (count === 1) return "Notificaciones, 1 no leída";
    return `Notificaciones, ${count} no leídas`;
  };

  const ariaLabelText = getAriaLabel(unreadCount);

  return (
    <div className="dropdown" ref={containerRef} onKeyDown={handleKeyDown}>
      <button
        ref={triggerRef}
        type="button"
        className="dropdown__trigger notif-bell"
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label={ariaLabelText}
        onClick={togglePanel}
      >
        <BellIcon />
        {unreadCount > 0 ? (
          <span className="notif-bell__count" aria-hidden="true">
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        ) : null}
      </button>

      {/* Screen reader notification of unread count update */}
      <span className="sr-only" aria-live="polite" id="notif-aria-live">
        {unreadCount > 0 ? `${unreadCount} notificaciones no leídas` : "Sin notificaciones"}
      </span>

      {open ? (
        <div className="notif-panel notif-panel--sheet" role="dialog" aria-modal="true" aria-labelledby="notif-title">
          <div className="notif-panel__header">
            <h2 id="notif-title" className="notif-panel__title">
              {labels.notifications}
            </h2>
            <div style={{ display: "flex", gap: "var(--sp-2)", alignItems: "center" }}>
              {unreadCount > 0 && (
                <button
                  type="button"
                  className="notif-panel__mark-all"
                  onClick={handleMarkAllRead}
                >
                  {labels.notificationsMarkAllRead}
                </button>
              )}
              <button
                type="button"
                className="notif-panel__close"
                style={{ display: "none" }}
                aria-label={labels.notificationsClose}
                onClick={() => closePanel(true)}
              >
                <CloseIcon />
              </button>
            </div>
          </div>

          <div className="notif-panel__list" ref={listRef}>
            {loading ? (
              <>
                <div className="notif-panel__skeleton-item" data-testid="skeleton-item">
                  <div className="notif-panel__skeleton-circle"></div>
                  <div className="notif-panel__skeleton-lines">
                    <div className="notif-panel__skeleton-line1"></div>
                    <div className="notif-panel__skeleton-line2"></div>
                  </div>
                </div>
                <div className="notif-panel__skeleton-item">
                  <div className="notif-panel__skeleton-circle"></div>
                  <div className="notif-panel__skeleton-lines">
                    <div className="notif-panel__skeleton-line1"></div>
                    <div className="notif-panel__skeleton-line2"></div>
                  </div>
                </div>
                <div className="notif-panel__skeleton-item">
                  <div className="notif-panel__skeleton-circle"></div>
                  <div className="notif-panel__skeleton-lines">
                    <div className="notif-panel__skeleton-line1"></div>
                    <div className="notif-panel__skeleton-line2"></div>
                  </div>
                </div>
              </>
            ) : error ? (
              <div className="notif-panel__error">
                <p className="notif-panel__error-msg">{labels.notificationsError}</p>
                <button
                  type="button"
                  className="notif-panel__error-retry"
                  onClick={fetchNotifications}
                >
                  {labels.notificationsRetry}
                </button>
              </div>
            ) : notifications.length === 0 ? (
              <div className="notif-panel__empty">
                <p className="notif-panel__empty-title">{labels.notificationsEmpty}</p>
                <p className="notif-panel__empty-hint">{labels.notificationsEmptyHint}</p>
              </div>
            ) : (
              Object.entries(groupedNotifications).map(([kicker, items]) => (
                <div key={kicker}>
                  <div className="notif-panel__kicker">
                    {kicker}
                  </div>
                  {items.map((notif) => (
                    <a
                      key={notif.id}
                      href={notif.deep_link || "#"}
                      data-item-id={notif.id}
                      className={`notif-panel__item ${
                        !notif.read ? "notif-panel__item--unread" : ""
                      }`}
                      // eslint-disable-next-line react-hooks/refs
                      onClick={(e) => handleItemClick(notif, e)}
                    >
                      {!notif.read ? (
                        <span className="notif-panel__dot" aria-hidden="true" />
                      ) : (
                        <span className="notif-panel__dot--placeholder" aria-hidden="true" />
                      )}
                      {getNotificationIcon(notif.type, notif.payload)}
                      <div className="notif-panel__item-body">
                        <p className="notif-panel__item-text">
                          {formatNotificationText(notif.type, notif.payload)}
                        </p>
                        <span className="notif-panel__item-meta">
                          {formatRelativeTime(notif.created_at)}
                        </span>
                      </div>
                      <span className="notif-panel__item-action" aria-hidden="true">
                        {labels.notificationsView}
                      </span>
                    </a>
                  ))}
                </div>
              ))
            )}
          </div>

          <div className="notif-panel__footer">
            <a
              href="/notificaciones"
              className="notif-panel__view-all"
              onClick={(e) => {
                e.preventDefault();
                closePanel(false);
                router.push("/notificaciones");
              }}
            >
              {labels.notificationsViewAll}
            </a>
          </div>
        </div>
      ) : null}
    </div>
  );
}
