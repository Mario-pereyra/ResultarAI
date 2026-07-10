"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";

interface NotificationItem {
  id: string;
  type: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload: Record<string, any>;
  deep_link: string | null;
  read: boolean;
  created_at: string;
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

export default function NotificationsPage() {
  const t = useTranslations("Shell.topbar");
  const router = useRouter();

  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [hasNext, setHasNext] = useState(false);
  const [filter, setFilter] = useState<"all" | "unread" | "read">("all");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);

  const fetchNotifications = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const res = await fetch(
        `/api/notifications?status=${filter}&page=${page}&page_size=15`
      );
      if (res.ok) {
        const data = await res.json();
        setNotifications(data.items);
        setTotal(data.total);
        setHasNext(data.has_next);
      } else {
        setError(true);
      }
    } catch (err) {
      console.error("Error fetching notifications:", err);
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [filter, page]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchNotifications();
  }, [fetchNotifications]);

  const handleMarkRead = async (notif: NotificationItem) => {
    if (notif.read) {
      if (notif.deep_link) {
        router.push(notif.deep_link);
      }
      return;
    }

    try {
      const csrf = document.cookie
        .split("; ")
        .find((row) => row.startsWith("resultarai_csrf="))
        ?.split("=")[1];

      const headers: Record<string, string> = {};
      if (csrf) {
        headers["X-CSRF-Token"] = csrf;
      }

      const res = await fetch(`/api/notifications/${notif.id}/read`, {
        method: "POST",
        headers,
      });

      if (res.ok) {
        setNotifications((prev) =>
          prev.map((n) => (n.id === notif.id ? { ...n, read: true } : n))
        );
        if (filter === "unread") {
          setTotal((prev) => Math.max(0, prev - 1));
        }
      }
    } catch (err) {
      console.error("Error marking notification read:", err);
    }

    if (notif.deep_link) {
      router.push(notif.deep_link);
    }
  };

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
        setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
        if (filter === "unread") {
          setNotifications([]);
        }
        setTotal(0);
      }
    } catch (err) {
      console.error("Error marking all read:", err);
    }
  };

  return (
    <div style={{ padding: "var(--sp-6)", maxWidth: "800px", margin: "0 auto" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "var(--sp-6)",
        }}
      >
        <h1 className="panel-title" style={{ fontSize: "24px", margin: 0 }}>
          {t("notifications")}
        </h1>
        {notifications.some((n) => !n.read) && (
          <button
            type="button"
            className="notif-panel__mark-all"
            onClick={handleMarkAllRead}
            style={{ fontSize: "14px" }}
          >
            {t("notificationsMarkAllRead")}
          </button>
        )}
      </div>

      {/* Filter Tabs */}
      <div
        style={{
          display: "flex",
          gap: "var(--sp-2)",
          marginBottom: "var(--sp-4)",
          borderBottom: "1px solid var(--line)",
          paddingBottom: "var(--sp-2)",
        }}
      >
        {(["all", "unread", "read"] as const).map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => {
              setFilter(tab);
              setPage(1);
            }}
            style={{
              padding: "var(--sp-2) var(--sp-4)",
              background: filter === tab ? "var(--accent-faint)" : "transparent",
              color: filter === tab ? "var(--accent)" : "var(--ink-dim)",
              border: "none",
              borderRadius: "var(--r-sm)",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            {tab === "all" ? "Todas" : tab === "unread" ? "No leídas" : "Leídas"}
          </button>
        ))}
      </div>

      {/* Notifications list */}
      <div className="panel panel--flush --raised">
        {loading ? (
          <div style={{ padding: "var(--sp-6)" }}>
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
          </div>
        ) : error ? (
          <div className="notif-panel__error">
            <p className="notif-panel__error-msg">{t("notificationsError")}</p>
            <button
              type="button"
              className="notif-panel__error-retry"
              onClick={fetchNotifications}
            >
              {t("notificationsRetry")}
            </button>
          </div>
        ) : notifications.length === 0 ? (
          <div className="notif-panel__empty">
            <p className="notif-panel__empty-title">{t("notificationsEmpty")}</p>
            <p className="notif-panel__empty-hint">{t("notificationsEmptyHint")}</p>
          </div>
        ) : (
          <div>
            {notifications.map((notif) => (
              <a
                key={notif.id}
                href={notif.deep_link || "#"}
                className={`notif-panel__item ${
                  !notif.read ? "notif-panel__item--unread" : ""
                }`}
                onClick={(e) => {
                  e.preventDefault();
                  handleMarkRead(notif);
                }}
              >
                {!notif.read ? (
                  <span className="notif-panel__dot" aria-hidden="true" />
                ) : (
                  <span className="notif-panel__dot--placeholder" aria-hidden="true" />
                )}
                <div className="notif-panel__item-body">
                  <p className="notif-panel__item-text" style={{ fontSize: "14px" }}>
                    {formatNotificationText(notif.type, notif.payload)}
                  </p>
                  <span className="notif-panel__item-meta" style={{ fontSize: "11px" }}>
                    {new Date(notif.created_at).toLocaleString("es-AR")}
                  </span>
                </div>
                <span className="notif-panel__item-action" aria-hidden="true">
                  {t("notificationsView")}
                </span>
              </a>
            ))}
          </div>
        )}
      </div>

      {/* Pagination Controls */}
      {total > 0 && (
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginTop: "var(--sp-4)",
          }}
        >
          <span style={{ fontSize: "13px", color: "var(--ink-dim)" }}>
            Total: {total}
          </span>
          <div style={{ display: "flex", gap: "var(--sp-2)" }}>
            <button
              type="button"
              disabled={page === 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              style={{
                padding: "var(--sp-2) var(--sp-4)",
                background: "transparent",
                border: "1px solid var(--line)",
                borderRadius: "var(--r-sm)",
                cursor: page === 1 ? "not-allowed" : "pointer",
                opacity: page === 1 ? 0.5 : 1,
                color: "var(--ink)",
              }}
            >
              Anterior
            </button>
            <button
              type="button"
              disabled={!hasNext}
              onClick={() => setPage((p) => p + 1)}
              style={{
                padding: "var(--sp-2) var(--sp-4)",
                background: "transparent",
                border: "1px solid var(--line)",
                borderRadius: "var(--r-sm)",
                cursor: !hasNext ? "not-allowed" : "pointer",
                opacity: !hasNext ? 0.5 : 1,
                color: "var(--ink)",
              }}
            >
              Siguiente
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
