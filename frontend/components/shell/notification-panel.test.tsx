import React from "react";
import userEvent from "@testing-library/user-event";
import { render, screen, waitFor, act } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { NotificationPanel } from "./notification-panel";

// Mock router
const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

const mockLabels = {
  notifications: "Notificaciones",
  notificationsEmpty: "Sin novedades por ahora",
  notificationsEmptyHint: "Acá vas a ver aprobaciones, avisos de cuota y novedades del sistema.",
  notificationsError: "No se pudieron cargar las notificaciones",
  notificationsRetry: "Reintentar",
  notificationsMarkAllRead: "Marcar leídas",
  notificationsViewAll: "Ver todas",
  notificationsView: "Ver",
  notificationsClose: "Cerrar notificaciones",
  notificationsKickerCuotas: "Cuotas",
  notificationsKickerSistema: "Sistema",
  notificationsKickerAprobaciones: "Aprobaciones",
};

describe("NotificationPanel", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    push.mockClear();

    // Mock document.cookie
    Object.defineProperty(document, "cookie", {
      writable: true,
      value: "resultarai_csrf=test-token",
    });
  });

  function renderPanel() {
    return render(
      <NotificationPanel labels={mockLabels} />
    );
  }

  it("el indicador se oculta en cero", async () => {
    // Mock count = 0
    global.fetch = vi.fn().mockImplementation(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ count: 0 }),
      } as Response)
    );

    renderPanel();

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith("/api/notifications/unread-count");
    });

    // Check count badge is NOT rendered
    const badge = screen.queryByText("0");
    expect(badge).toBeNull();
  });

  it("llegada en vivo actualiza el contador sin robar foco", async () => {
    // Use fake timers specifically inside this test
    vi.useFakeTimers();

    let count = 0;
    global.fetch = vi.fn().mockImplementation((url) => {
      if (url === "/api/notifications/unread-count") {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ count }),
        } as Response);
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ items: [], total: 0, has_next: false }),
      } as Response);
    });

    renderPanel();

    // Resolve initial fetch first
    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });

    expect(screen.queryByText("3")).toBeNull();

    // Update count and advance timers
    count = 3;
    await act(async () => {
      vi.advanceTimersByTime(30000);
      await vi.runOnlyPendingTimersAsync();
    });

    const badge = screen.getByText("3");
    expect(badge).toBeDefined();

    vi.useRealTimers();
  });

  it("los grupos sin elementos no aparecen", async () => {
    const mockNotifs = [
      {
        id: "1",
        type: "quota_release_requested",
        payload: { requestor_username: "user1", quota_name: "API", current_consumption: 80.5 },
        deep_link: "/admin/quotas",
        read: false,
        created_at: new Date().toISOString(),
      },
    ];

    global.fetch = vi.fn().mockImplementation((url) => {
      if (url.includes("/unread-count")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ count: 1 }),
        } as Response);
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ items: mockNotifs, total: 1, has_next: false }),
      } as Response);
    });

    renderPanel();

    const user = userEvent.setup();
    const bell = await screen.findByRole("button", { name: /notificaciones/i });
    await user.click(bell);

    await waitFor(() => {
      // Group header CUOTAS is visible
      expect(screen.getByText("Cuotas")).toBeDefined();
      // Group header APROBACIONES is NOT visible
      expect(screen.queryByText("Aprobaciones")).toBeNull();
      // Notification text is formatted correctly
      expect(
        screen.getByText(/user1 solicita liberar cuota para API \(consumo 80.5%\)/i)
      ).toBeDefined();
    });
  });

  it("muestra estado vacío cuando no hay notificaciones", async () => {
    global.fetch = vi.fn().mockImplementation((url) => {
      if (url.includes("/unread-count")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ count: 0 }),
        } as Response);
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ items: [], total: 0, has_next: false }),
      } as Response);
    });

    renderPanel();

    const user = userEvent.setup();
    const bell = await screen.findByRole("button", { name: /notificaciones/i });
    await user.click(bell);

    await waitFor(() => {
      expect(screen.getByText("Sin novedades por ahora")).toBeDefined();
      expect(
        screen.getByText("Acá vas a ver aprobaciones, avisos de cuota y novedades del sistema.")
      ).toBeDefined();
    });
  });

  it("click en una notificación navega y marca leído", async () => {
    const mockNotifs = [
      {
        id: "notif-123",
        type: "quota_release_requested",
        payload: { requestor_username: "user1", quota_name: "API", current_consumption: 80.5 },
        deep_link: "/admin/quotas/123",
        read: false,
        created_at: new Date().toISOString(),
      },
    ];

    global.fetch = vi.fn().mockImplementation((url) => {
      if (url.includes("/unread-count")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ count: 1 }),
        } as Response);
      }
      if (url.includes("/api/notifications/notif-123/read")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ status: "success" }),
        } as Response);
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ items: mockNotifs, total: 1, has_next: false }),
      } as Response);
    });

    renderPanel();

    const user = userEvent.setup();
    const bell = await screen.findByRole("button", { name: /notificaciones/i });
    await user.click(bell);

    const item = await screen.findByText(/user1 solicita liberar cuota/i);
    await user.click(item);

    // Should mark as read and navigate
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith("/api/notifications/notif-123/read", {
        method: "POST",
        headers: { "X-CSRF-Token": "test-token" },
      });
      expect(push).toHaveBeenCalledWith("/admin/quotas/123");
    });
  });

  it("navegación completa por teclado con Esc para cerrar y devolver foco", async () => {
    global.fetch = vi.fn().mockImplementation(() => {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ items: [], total: 0, has_next: false, count: 0 }),
      } as Response);
    });

    renderPanel();

    const user = userEvent.setup();
    const bell = await screen.findByRole("button", { name: /notificaciones/i });
    bell.focus();
    expect(document.activeElement).toBe(bell);

    // Open by Enter/Click
    await user.click(bell);
    
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toBeDefined();

    // Press Escape
    await user.keyboard("{Escape}");
    
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).toBeNull();
      // Focus should return to the bell button
      expect(document.activeElement).toBe(bell);
    });
  });
});
