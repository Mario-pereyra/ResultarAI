import userEvent from "@testing-library/user-event";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SessionProvider, type SessionContextValue } from "@/lib/session-context";
import { HistoryContent, type HistoryContentLabels } from "./history-content";

/**
 * Tests de componente de las tareas 7.1/7.2/7.4 de d13-chat-conversacion
 * (`design/VISTAS/02-chat.md` vista 12, historial de sesiones). Mismo patrón
 * que `chat-content.test.tsx`: `<SessionProvider>` porque `HistoryContent`
 * lee `useSession().user.role` (tarea 7.4, columna de costo solo Admin), y
 * un `fetch` global stubeado por test (sin MSW, ver `chat-content.test.tsx`
 * para el precedente).
 */

const { pushMock } = vi.hoisted(() => ({ pushMock: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: vi.fn(),
    push: pushMock,
  }),
}));

const LABELS: HistoryContentLabels = {
  title: "Historial",
  newSession: "Nueva consulta",
  search: {
    label: "Buscar en tus conversaciones",
    placeholder: "Buscar en tus conversaciones…",
  },
  agentFilter: {
    label: "Filtrar por agente",
    all: "Todos los agentes",
  },
  tabs: {
    label: "Estado de las sesiones",
    active: "Activas",
    archived: "Archivadas",
  },
  columns: {
    session: "Sesión",
    lastActivity: "Última actividad",
  },
  row: {
    untitled: "Conversación sin título",
    messageCountOne: "{n} mensaje",
    messageCountOther: "{n} mensajes",
    branchesAriaLabelOne: "esta sesión tiene {n} rama",
    branchesAriaLabelOther: "esta sesión tiene {n} ramas",
    matchInTitle: "coincidencia en el título",
    matchInMessage: "coincidencia en un mensaje",
  },
  cost: {
    columnLabel: "Costo",
    unavailableTooltip: "El costo por sesión todavía no está disponible.",
    periodTotalPrefix: "Este mes:",
    periodSessionsOne: "{n} sesión activa",
    periodSessionsOther: "{n} sesiones activas",
  },
  empty: {
    firstTime: {
      title: "Todavía no tenés conversaciones",
      hint: "Elegí un agente del catálogo para empezar tu primera consulta.",
      cta: "Ir al catálogo",
    },
    noResults: {
      title: "Sin resultados para «{q}»",
      titleGeneric: "Sin resultados con los filtros aplicados",
      hint: "Probá con otro término o quitá el filtro de agente.",
      clear: "Limpiar búsqueda",
    },
    archived: {
      title: "No archivaste ninguna conversación",
      hint: "Archivar guarda la conversación fuera de la lista activa — nunca se borra nada.",
    },
  },
  error: {
    title: "No pudimos cargar tu historial",
    why: "El servicio respondió con un error temporal. Tus conversaciones están a salvo.",
    retry: "Reintentar",
  },
  loading: "Cargando tu historial…",
};

// Fecha bien en el pasado a propósito: `formatRelativeTime` cae siempre al
// formato absoluto `dd/mm/aaaa` (>24 h de diferencia) sin importar el reloj
// real del entorno de test -- evita depender de `vi.setSystemTime` para las
// aserciones que no versan sobre el formato de fecha en sí.
const OLD_DATE = "2020-01-01T00:00:00Z";

const SESSION_WITH_BRANCHES = {
  id: "session-1",
  agent_id: "default_chat",
  title: "Parametrización MV_PAISLOC Bolivia",
  model_profile: "deepseek-v4-flash",
  last_activity_at: OLD_DATE,
  message_count: 14,
  branch_count: 2,
};

const SESSION_DEFAULT_CHAT = {
  id: "session-1",
  agent_id: "default_chat",
  title: "Parametrización MV_PAISLOC Bolivia",
  model_profile: "deepseek-v4-flash",
  last_activity_at: OLD_DATE,
  message_count: 14,
  branch_count: 0,
};

const SESSION_OTHER_AGENT = {
  id: "session-2",
  agent_id: "otro_agente",
  title: "Checklist contable Comercial Andina",
  model_profile: "deepseek-v4-flash",
  last_activity_at: OLD_DATE,
  message_count: 5,
  branch_count: 0,
};

const SEARCH_HIT_1 = {
  session_id: "session-1",
  agent_id: "default_chat",
  title: "Parametrización MV_PAISLOC Bolivia",
  last_activity_at: OLD_DATE,
  match_type: "title" as const,
  message_id: null,
  snippet: "Parametrización MV_PAISLOC Bolivia",
  match_start: 14,
  match_end: 21,
};

function sessionFor(role: SessionContextValue["user"]["role"]): SessionContextValue {
  return {
    user: { name: "lucia", role },
    gateway: { status: "ok" },
    pendingApprovals: 0,
    unreadNotifications: 0,
    capabilities: [],
  };
}

function renderHistory(role: SessionContextValue["user"]["role"] = "funcional") {
  return render(
    <SessionProvider value={sessionFor(role)}>
      <HistoryContent labels={LABELS} />
    </SessionProvider>,
  );
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** Stub de `fetch` para `GET /api/sessions` y `GET /api/sessions/search` --
 * responde según el prefijo de la URL (la ruta literal `/search` se
 * distingue de la paramétrica, mismo criterio que el backend real). */
function stubHistoryFetch(options: { list?: unknown[]; search?: unknown[] } = {}) {
  const { list = [], search = [] } = options;
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = typeof input === "string" ? input : input.toString();
    if (url.startsWith("/api/sessions/search")) {
      return jsonResponse({ items: search, limit: 25, offset: 0 });
    }
    if (url.startsWith("/api/sessions")) {
      return jsonResponse({ items: list, limit: 25, offset: 0 });
    }
    throw new Error(`fetch inesperado en este test: ${url}`);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
  pushMock.mockClear();
});

describe("HistoryContent — lista de sesiones (tarea 7.1)", () => {
  it("una sesión con branch_count 2 muestra el contador de ramas correcto (⑂ 2)", async () => {
    stubHistoryFetch({ list: [SESSION_WITH_BRANCHES] });
    renderHistory();

    await screen.findByText("Parametrización MV_PAISLOC Bolivia");
    expect(screen.getByText("⑂ 2")).toBeTruthy();
    expect(screen.getByText("14 mensajes")).toBeTruthy();
  });

  it("filtro por agente: deja solo las filas del agente elegido", async () => {
    stubHistoryFetch({ list: [SESSION_DEFAULT_CHAT, SESSION_OTHER_AGENT] });
    renderHistory();

    await screen.findByText("Parametrización MV_PAISLOC Bolivia");
    expect(screen.getByText("Checklist contable Comercial Andina")).toBeTruthy();

    const select = screen.getByLabelText("Filtrar por agente") as HTMLSelectElement;
    fireEvent.change(select, { target: { value: "otro_agente" } });

    expect(screen.queryByText("Parametrización MV_PAISLOC Bolivia")).toBeNull();
    expect(screen.getByText("Checklist contable Comercial Andina")).toBeTruthy();
  });

  it("click en una fila navega a /chat/{id}", async () => {
    stubHistoryFetch({ list: [SESSION_WITH_BRANCHES] });
    renderHistory();

    const title = await screen.findByText("Parametrización MV_PAISLOC Bolivia");
    await userEvent.click(title);

    expect(pushMock).toHaveBeenCalledWith("/chat/session-1");
  });

  it('tabs con roles ARIA: "Activas N" refleja la cantidad cargada, "Archivadas" siempre en 0', async () => {
    stubHistoryFetch({ list: [SESSION_DEFAULT_CHAT, SESSION_OTHER_AGENT] });
    renderHistory();

    await screen.findByText("Parametrización MV_PAISLOC Bolivia");
    const tablist = screen.getByRole("tablist", { name: "Estado de las sesiones" });
    expect(tablist).toBeTruthy();
    expect(screen.getByRole("tab", { name: "Activas 2" })).toBeTruthy();
    expect(screen.getByRole("tab", { name: "Archivadas 0" })).toBeTruthy();
  });
});

describe("HistoryContent — buscador con debounce 300 ms (tarea 7.1)", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("tipear no dispara fetch hasta pasados 300 ms; a los 300 ms llama a /api/sessions/search", async () => {
    const fetchMock = stubHistoryFetch({ list: [SESSION_WITH_BRANCHES], search: [SEARCH_HIT_1] });

    renderHistory();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    const callsAfterInitialLoad = fetchMock.mock.calls.length;

    const search = screen.getByLabelText("Buscar en tus conversaciones");
    fireEvent.change(search, { target: { value: "PAISLOC" } });

    // Antes de los 300 ms: ningún fetch nuevo (ni de búsqueda ni de listado).
    await act(async () => {
      await vi.advanceTimersByTimeAsync(200);
    });
    expect(fetchMock.mock.calls.length).toBe(callsAfterInitialLoad);

    // A los 300 ms: dispara la búsqueda server-side con el término tipeado.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(fetchMock.mock.calls.length).toBe(callsAfterInitialLoad + 1);
    const lastUrl = String(fetchMock.mock.calls.at(-1)?.[0]);
    expect(lastUrl).toContain("/api/sessions/search?q=PAISLOC");
  });
});

describe("HistoryContent — estados (tarea 7.2)", () => {
  it("carga: skeleton visible mientras el fetch está en vuelo", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>(() => {})),
    );
    renderHistory();

    expect(screen.getAllByRole("status").length).toBeGreaterThan(0);
  });

  it("vacío (primera vez): título + hint + CTA «Ir al catálogo»", async () => {
    stubHistoryFetch({ list: [] });
    renderHistory();

    await screen.findByText("Todavía no tenés conversaciones");
    expect(
      screen.getByText("Elegí un agente del catálogo para empezar tu primera consulta."),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: "Ir al catálogo" })).toBeTruthy();
  });

  it("sin resultados de búsqueda: título con el término buscado + hint + «Limpiar búsqueda»", async () => {
    vi.useFakeTimers();
    stubHistoryFetch({ list: [SESSION_WITH_BRANCHES], search: [] });
    renderHistory();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    const search = screen.getByLabelText("Buscar en tus conversaciones") as HTMLInputElement;
    fireEvent.change(search, { target: { value: "MV_XYZ" } });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(300);
    });

    expect(screen.getByText("Sin resultados para «MV_XYZ»")).toBeTruthy();
    expect(
      screen.getByText("Probá con otro término o quitá el filtro de agente."),
    ).toBeTruthy();

    // "Limpiar búsqueda" vacía el campo -- vuelve a mostrar el listado
    // completo (0 caracteres = lista completa, vista 12 §Interacciones).
    // `getByText` (no `findByText`): con timers falsos activos, el `act`
    // de abajo ya asienta el estado sincrónicamente -- `findByText` agenda
    // su propio polling interno que nunca avanza sin timers reales.
    fireEvent.click(screen.getByRole("button", { name: "Limpiar búsqueda" }));
    expect(search.value).toBe("");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(300);
    });
    expect(screen.getByText("Parametrización MV_PAISLOC Bolivia")).toBeTruthy();

    vi.useRealTimers();
  });

  it("sin archivadas: tab Archivadas siempre vacía, sin disparar ningún fetch nuevo", async () => {
    const fetchMock = stubHistoryFetch({ list: [SESSION_WITH_BRANCHES] });
    renderHistory();

    await screen.findByText("Parametrización MV_PAISLOC Bolivia");
    const callsBefore = fetchMock.mock.calls.length;

    await userEvent.click(screen.getByRole("tab", { name: "Archivadas 0" }));

    expect(screen.getByText("No archivaste ninguna conversación")).toBeTruthy();
    expect(
      screen.getByText(
        "Archivar guarda la conversación fuera de la lista activa — nunca se borra nada.",
      ),
    ).toBeTruthy();
    expect(fetchMock.mock.calls.length).toBe(callsBefore);
  });

  it("error: tarjeta con «Reintentar» que vuelve a pedir el listado y muestra las sesiones", async () => {
    let failNext = true;
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (!url.startsWith("/api/sessions")) throw new Error(`fetch inesperado: ${url}`);
      if (failNext) {
        failNext = false;
        return new Response("", { status: 500 });
      }
      return jsonResponse({ items: [SESSION_WITH_BRANCHES], limit: 25, offset: 0 });
    });
    vi.stubGlobal("fetch", fetchMock);
    renderHistory();

    await screen.findByText("No pudimos cargar tu historial");
    expect(
      screen.getByText("El servicio respondió con un error temporal. Tus conversaciones están a salvo."),
    ).toBeTruthy();

    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    await screen.findByText("Parametrización MV_PAISLOC Bolivia");
  });
});

describe("HistoryContent — columna de costo solo Admin (tarea 7.4)", () => {
  it("Admin: columna de costo presente (placeholder ~) y total del período visible", async () => {
    stubHistoryFetch({ list: [SESSION_WITH_BRANCHES] });
    renderHistory("admin");

    await screen.findByText("Parametrización MV_PAISLOC Bolivia");
    expect(screen.getByRole("columnheader", { name: "Costo" })).toBeTruthy();
    // El placeholder "~" aparece dos veces a propósito (celda de la fila +
    // total del período) -- se apunta a la celda por su tooltip, que es
    // único, para no depender de cuántas filas hay.
    expect(screen.getByTitle("El costo por sesión todavía no está disponible.")).toBeTruthy();
    expect(screen.getByText(/Este mes:/)).toBeTruthy();
  });

  it.each(["tecnico", "funcional"] as const)(
    "%s: la columna de costo está AUSENTE del DOM",
    async (role) => {
      stubHistoryFetch({ list: [SESSION_WITH_BRANCHES] });
      renderHistory(role);

      await screen.findByText("Parametrización MV_PAISLOC Bolivia");
      expect(screen.queryByRole("columnheader", { name: "Costo" })).toBeNull();
      expect(screen.queryByTitle("El costo por sesión todavía no está disponible.")).toBeNull();
      expect(screen.queryByText(/Este mes:/)).toBeNull();
    },
  );
});
