"use client";

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "@/components/ui/table";
import { Tabs, type TabItem } from "@/components/ui/tabs";
import { Tag } from "@/components/ui/tag";
import { formatAbsoluteTime, formatRelativeTime } from "@/lib/chat/format-time";
import type {
  ListSessionsResponse,
  SearchSessionsResponse,
  SessionSearchHit,
  SessionSummary,
} from "@/lib/chat/types";
import { useSession } from "@/lib/session-context";
import { DEFAULT_CHAT_AGENT_DISPLAY_NAME, DEFAULT_CHAT_AGENT_ID } from "./labels";

/** Debounce del buscador (tarea 7.1, vista 12 §Interacciones: "debounce 300 ms"). */
const SEARCH_DEBOUNCE_MS = 300;
/** Ventana de página (vista 12 §Estados: "lista paginada por scroll, ventanas de
 * 25") -- este change carga la PRIMERA ventana; el scroll infinito queda para
 * una iteración futura (ver `openspec/BACKLOG-DESCUBRIMIENTOS.md`). */
const PAGE_SIZE = 25;

type HistoryTabId = "active" | "archived";

export interface HistoryContentLabels {
  title: string;
  newSession: string;
  search: { label: string; placeholder: string };
  agentFilter: { label: string; all: string };
  tabs: { label: string; active: string; archived: string };
  /** Encabezados `<th>` de la tabla -- el `<caption>` va oculto
   * (`Table captionHidden`, el título "Historial" ya es visible fuera de la
   * tabla), pero los `<th>` de columna siguen siendo la anatomía accesible
   * mínima de una tabla real (design/DESIGN-SYSTEM.md §8.4). */
  columns: { session: string; lastActivity: string };
  row: {
    untitled: string;
    /** Plantillas ICU-lite con placeholder literal `{n}` (mismo patrón que
     * `Chat.branch.reprocessWarningOne/Other`, ver `message-edit.tsx`): el
     * conteo es un dato de runtime del cliente, así que la categoría ICU
     * ("one"/"other") se elige acá con `Intl.PluralRules`, no vía next-intl. */
    messageCountOne: string;
    messageCountOther: string;
    branchesAriaLabelOne: string;
    branchesAriaLabelOther: string;
    matchInTitle: string;
    matchInMessage: string;
  };
  cost: {
    columnLabel: string;
    unavailableTooltip: string;
    periodTotalPrefix: string;
    periodSessionsOne: string;
    periodSessionsOther: string;
  };
  empty: {
    firstTime: { title: string; hint: string; cta: string };
    /** `title`/`titleGeneric`: `title` lleva el placeholder literal `{q}`
     * (ICU-lite, mismo patrón que arriba) para cuando hay término de
     * búsqueda; `titleGeneric` cubre el caso "el filtro de agente dejó la
     * lista en cero" sin término de búsqueda -- ver `HistoryContent`. */
    noResults: { title: string; titleGeneric: string; hint: string; clear: string };
    archived: { title: string; hint: string };
  };
  error: { title: string; why: string; retry: string };
  loading: string;
}

export interface HistoryContentProps {
  labels: HistoryContentLabels;
}

/** Una fila del historial, ya normalizada desde `GET /sessions` (listado) o
 * `GET /sessions/search` (búsqueda) -- ver `toSessionRow`/`toSearchRow`.
 * `messageCount`/`branchCount` son `null` en modo búsqueda: `SessionSearchHit`
 * no los trae (el backend prioriza UN match por sesión, ver el docstring de
 * `search_sessions` en `resultarai/app/use_cases/chat/history.py`) -- la fila
 * muestra en su lugar dónde matcheó (`matchType`) y el fragmento resaltado
 * (`snippet`/`matchStart`/`matchEnd`).
 */
interface HistoryRow {
  sessionId: string;
  agentId: string | null;
  title: string | null;
  lastActivityAt: string | null;
  messageCount: number | null;
  branchCount: number | null;
  isSearchHit: boolean;
  matchType?: "title" | "message";
  snippet?: string;
  matchStart?: number;
  matchEnd?: number;
}

function toSessionRow(session: SessionSummary): HistoryRow {
  return {
    sessionId: session.id,
    agentId: session.agent_id,
    title: session.title,
    lastActivityAt: session.last_activity_at,
    messageCount: session.message_count,
    branchCount: session.branch_count,
    isSearchHit: false,
  };
}

function toSearchRow(hit: SessionSearchHit): HistoryRow {
  return {
    sessionId: hit.session_id,
    agentId: hit.agent_id,
    title: hit.title,
    lastActivityAt: hit.last_activity_at,
    messageCount: null,
    branchCount: null,
    isSearchHit: true,
    matchType: hit.match_type,
    snippet: hit.snippet,
    matchStart: hit.match_start,
    matchEnd: hit.match_end,
  };
}

/** Elige la categoría de plural ICU ("one"/"other") con la misma tabla CLDR
 * que usa next-intl, sin depender de `useTranslations` -- mismo patrón que
 * `pluralWarningText` de `components/chat/message-edit.tsx` (`n` es un dato
 * de runtime del cliente, no resoluble al armar `labels` server-side). */
function pluralText(one: string, other: string, n: number): string {
  const category = new Intl.PluralRules("es").select(n);
  return (category === "one" ? one : other).replace("{n}", String(n));
}

/** Nombre visible del agente de una fila. Hoy el único agente del catálogo es
 * `default_chat` (selector de catálogo real: `d15`, ver
 * `openspec/BACKLOG-DESCUBRIMIENTOS.md`) -- para cualquier otro id (agente
 * futuro todavía sin nombre resuelto acá) se muestra el id crudo como
 * resguardo defensivo antes que dejar la celda vacía. */
function agentDisplayName(agentId: string | null): string {
  if (agentId === DEFAULT_CHAT_AGENT_ID) return DEFAULT_CHAT_AGENT_DISPLAY_NAME;
  return agentId ?? "—";
}

/** Resalta `snippet[matchStart:matchEnd]` con `<mark>` -- nunca vía
 * `dangerouslySetInnerHTML` (regla dura del proyecto, misma razón que la
 * sanitización de markdown de `components/chat/markdown-content.tsx`):
 * `snippet` es SIEMPRE texto plano server-side (`_build_snippet` en
 * `resultarai/app/use_cases/chat/history.py`), así que separarlo en nodos de
 * texto de React es seguro Y suficiente. */
function renderHighlightedSnippet(snippet: string, start: number, end: number): ReactNode {
  if (start < 0 || end > snippet.length || start >= end) return snippet;
  return (
    <>
      {snippet.slice(0, start)}
      <mark>{snippet.slice(start, end)}</mark>
      {snippet.slice(end)}
    </>
  );
}

/**
 * Historial de sesiones (tareas 7.1-7.4 de d13-chat-conversacion,
 * `design/VISTAS/02-chat.md` vista 12): lista de sesiones propias con
 * buscador, filtro por agente, tabs Activas/Archivadas y (solo Admin) costo
 * por sesión + total del período.
 *
 * DECISIÓN DE ROUTING (documentada acá porque este componente es el punto de
 * entrada de la sección "chat" del shell): `/chat` pasa a ser este listado
 * -- antes era la conversación nueva. La conversación nueva se movió a
 * `/chat/nueva` (botón "Nueva consulta" de acá abajo); `/chat/{id}` (retomar
 * una sesión) no cambió. El link del sidebar (`components/shell/sidebar.tsx`,
 * `SECTION_HREF.chat: "/chat"`) sigue apuntando al lugar correcto sin
 * necesitar ningún cambio ahí.
 *
 * DECISIÓN DE DATOS -- "Archivadas": el backend de este change (2.1/2.4) NO
 * tiene todavía el concepto de sesión archivada (llega con `d18-mi-espacio`,
 * ver `openspec/BACKLOG-DESCUBRIMIENTOS.md`). La tab "Archivadas" existe en
 * la UI (fiel a la vista 12) pero SIEMPRE muestra su estado vacío, con
 * contador fijo en 0 -- no dispara ningún fetch.
 *
 * DECISIÓN DE DATOS -- costo por sesión (tarea 7.4): `GET /sessions` no
 * expone `cost_usd` por sesión (hueco documentado en
 * `openspec/BACKLOG-DESCUBRIMIENTOS.md`: el endpoint debería agregarlo,
 * probablemente sumado de `turn_metadata` por sesión). La columna de costo
 * (y el total del período) SÍ se renderizan para Admin -- la tarea pide la
 * COLUMNA visible, no el dato -- con el placeholder `~` (mismo criterio que
 * el estado degradado del taxímetro, tarea 4.4 de `session-taximeter.tsx`)
 * hasta que el backend lo exponga.
 *
 * DECISIÓN DE DATOS -- filtro por agente: ni `GET /sessions` ni
 * `GET /sessions/search` aceptan un parámetro de agente -- el filtro se
 * aplica CLIENTE-SIDE sobre la ventana ya cargada (`PAGE_SIZE`), con las
 * opciones derivadas de los `agent_id` presentes en esa misma ventana (hoy
 * siempre un único agente, `default_chat`). Si el catálogo de agentes crece
 * (`d15`) y la paginación deja de alcanzar para un filtro correcto, el
 * backend necesitará un parámetro `agent_id` real.
 */
export function HistoryContent({ labels }: HistoryContentProps) {
  const router = useRouter();
  const { user } = useSession();
  const isAdmin = user.role === "admin";

  const [activeTab, setActiveTab] = useState<HistoryTabId>("active");
  const [searchInput, setSearchInput] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [agentFilter, setAgentFilter] = useState<string>("all");
  const [rows, setRows] = useState<HistoryRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  // Debounce 300 ms (tarea 7.1): el fetch de abajo depende de
  // `debouncedQuery`, no de `searchInput` -- tipear no dispara ningún
  // request hasta que el usuario deja de escribir por 300 ms.
  useEffect(() => {
    const handle = setTimeout(() => {
      setDebouncedQuery(searchInput.trim());
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(handle);
  }, [searchInput]);

  const fetchSessions = useCallback(async () => {
    // Tab "Archivadas": sin backend todavía (ver docstring de arriba) -- no
    // hay nada que pedir, la tab siempre resuelve a su estado vacío fijo.
    if (activeTab !== "active") return;
    setLoading(true);
    setError(false);
    try {
      const url = debouncedQuery
        ? `/api/sessions/search?q=${encodeURIComponent(debouncedQuery)}&limit=${PAGE_SIZE}`
        : `/api/sessions?limit=${PAGE_SIZE}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error("No se pudo cargar el historial.");
      if (debouncedQuery) {
        const data = (await res.json()) as SearchSessionsResponse;
        setRows(data.items.map(toSearchRow));
      } else {
        const data = (await res.json()) as ListSessionsResponse;
        setRows(data.items.map(toSessionRow));
      }
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [activeTab, debouncedQuery]);

  useEffect(() => {
    // `fetchSessions` sincroniza con un sistema externo (el backend, vía
    // `fetch`) -- mismo patrón ya aceptado en `loadSession` de
    // `chat-content.tsx` (que también llama `setLoading`/`setError` de
    // entrada, antes del primer `await`).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void fetchSessions();
  }, [fetchSessions]);

  const agentOptions = useMemo(() => {
    const ids = new Set<string>();
    for (const row of rows) {
      if (row.agentId) ids.add(row.agentId);
    }
    return Array.from(ids);
  }, [rows]);

  const visibleRows = useMemo(
    () => (agentFilter === "all" ? rows : rows.filter((row) => row.agentId === agentFilter)),
    [rows, agentFilter],
  );

  const hasQuery = debouncedQuery.length > 0;
  // "Sin resultados" cubre DOS causas (misma pantalla, vista 12 §Estados: el
  // hint ya invita a "quitar el filtro de agente"): 0 resultados de la
  // búsqueda server-side, O el filtro de agente vació una lista no vacía.
  const showNoResults = !loading && !error && rows.length > 0 && visibleRows.length === 0;
  const showFirstTimeEmpty = !loading && !error && rows.length === 0 && !hasQuery;
  // Con búsqueda activa y CERO hits del servidor (no por el filtro de
  // agente, que ya lo cubre `showNoResults` de arriba) también es "sin
  // resultados" -- se unifica con el mismo flag.
  const showNoSearchResults = !loading && !error && rows.length === 0 && hasQuery;

  function clearFilters() {
    setSearchInput("");
    setAgentFilter("all");
  }

  function handleRowActivate(sessionId: string) {
    router.push(`/chat/${sessionId}`);
  }

  function handleRowClick(event: React.MouseEvent<HTMLTableRowElement>, sessionId: string) {
    // El título de la fila ya es un `<button>` enfocable (ver más abajo) --
    // si el click vino de ahí, su propio `onClick` ya navegó; evita un
    // segundo `router.push` al mismo destino.
    if (event.target instanceof HTMLElement && event.target.closest("button")) return;
    handleRowActivate(sessionId);
  }

  const tabItems: TabItem[] = [
    { id: "active", label: labels.tabs.active, count: rows.length },
    { id: "archived", label: labels.tabs.archived, count: 0 },
  ];

  return (
    <div className="history">
      <div className="history-header">
        <h1>{labels.title}</h1>
        <Button variant="primary" onClick={() => router.push("/chat/nueva")}>
          {labels.newSession}
        </Button>
      </div>

      <div className="history-toolbar">
        <div className="history-toolbar__search">
          <Input
            label={labels.search.label}
            type="search"
            placeholder={labels.search.placeholder}
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
          />
        </div>
        <div className="history-toolbar__agent">
          <Select
            label={labels.agentFilter.label}
            value={agentFilter}
            onChange={(event) => setAgentFilter(event.target.value)}
          >
            <option value="all">{labels.agentFilter.all}</option>
            {agentOptions.map((agentId) => (
              <option key={agentId} value={agentId}>
                {agentDisplayName(agentId)}
              </option>
            ))}
          </Select>
        </div>
      </div>

      <div className="history-tabs">
        <Tabs label={labels.tabs.label} items={tabItems} activeId={activeTab} onChange={(id) => setActiveTab(id as HistoryTabId)} />
      </div>

      {isAdmin && activeTab === "active" && !loading && !error && rows.length > 0 ? (
        <p className="history-total">
          {labels.cost.periodTotalPrefix} <span className="money">~</span> ·{" "}
          {pluralText(labels.cost.periodSessionsOne, labels.cost.periodSessionsOther, rows.length)}
        </p>
      ) : null}

      <div role="tabpanel" id={`tabpanel-${activeTab}`} aria-labelledby={`tab-${activeTab}`}>
        {loading ? (
          <div aria-busy="true">
            <Table caption={labels.title} captionHidden>
              <TableHead>
                <TableRow>
                  <TableHeaderCell>{labels.columns.session}</TableHeaderCell>
                  <TableHeaderCell>{labels.columns.lastActivity}</TableHeaderCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {[0, 1, 2, 3].map((index) => (
                  <TableRow key={index} className="history-skeleton-row">
                    <TableCell>
                      <div className="history-skeleton-row__lines">
                        <Skeleton variant="title" label={labels.loading} />
                        <Skeleton variant="text" label={labels.loading} />
                      </div>
                    </TableCell>
                    <TableCell>
                      <Skeleton variant="text" label={labels.loading} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        ) : error ? (
          <div className="error-card" role="alert">
            <span className="error-card__icon" aria-hidden="true">
              ⛔
            </span>
            <div>
              <p className="error-card__title">{labels.error.title}</p>
              <p className="error-card__why">{labels.error.why}</p>
              <div className="error-card__actions">
                <Button variant="secondary" size="sm" onClick={() => void fetchSessions()}>
                  {labels.error.retry}
                </Button>
              </div>
            </div>
          </div>
        ) : activeTab === "archived" ? (
          <EmptyState
            icon={<span aria-hidden="true">🗄</span>}
            title={labels.empty.archived.title}
            description={labels.empty.archived.hint}
          />
        ) : showFirstTimeEmpty ? (
          <EmptyState
            title={labels.empty.firstTime.title}
            description={labels.empty.firstTime.hint}
            action={
              <Button variant="primary" onClick={() => router.push("/")}>
                {labels.empty.firstTime.cta}
              </Button>
            }
          />
        ) : showNoResults || showNoSearchResults ? (
          <EmptyState
            title={
              hasQuery
                ? labels.empty.noResults.title.replace("{q}", debouncedQuery)
                : labels.empty.noResults.titleGeneric
            }
            description={labels.empty.noResults.hint}
            action={
              <Button variant="secondary" size="sm" onClick={clearFilters}>
                {labels.empty.noResults.clear}
              </Button>
            }
          />
        ) : (
          <Table caption={labels.title} captionHidden>
            <TableHead>
              <TableRow>
                <TableHeaderCell>{labels.columns.session}</TableHeaderCell>
                <TableHeaderCell>{labels.columns.lastActivity}</TableHeaderCell>
                {isAdmin ? <TableHeaderCell>{labels.cost.columnLabel}</TableHeaderCell> : null}
              </TableRow>
            </TableHead>
            <TableBody>
              {visibleRows.map((row) => {
                const title = row.title?.trim() ? row.title : labels.row.untitled;
                return (
                  <TableRow
                    key={row.sessionId}
                    className="history-row"
                    onClick={(event) => handleRowClick(event, row.sessionId)}
                  >
                    <TableCell>
                      <Tag variant="neutral" outline>
                        {agentDisplayName(row.agentId)}
                      </Tag>
                      <button
                        type="button"
                        className="history-row__title-link"
                        onClick={() => handleRowActivate(row.sessionId)}
                      >
                        {row.isSearchHit && row.matchType === "title" && row.snippet
                          ? renderHighlightedSnippet(
                              row.snippet,
                              row.matchStart ?? 0,
                              row.matchEnd ?? 0,
                            )
                          : title}
                      </button>
                      <div className="history-row__meta">
                        {row.isSearchHit ? (
                          <>
                            <span>
                              {row.matchType === "title"
                                ? labels.row.matchInTitle
                                : labels.row.matchInMessage}
                            </span>
                            {row.matchType === "message" && row.snippet ? (
                              <span>
                                {renderHighlightedSnippet(
                                  row.snippet,
                                  row.matchStart ?? 0,
                                  row.matchEnd ?? 0,
                                )}
                              </span>
                            ) : null}
                          </>
                        ) : (
                          <>
                            {row.messageCount !== null ? (
                              <span>
                                {pluralText(
                                  labels.row.messageCountOne,
                                  labels.row.messageCountOther,
                                  row.messageCount,
                                )}
                              </span>
                            ) : null}
                            {row.branchCount !== null && row.branchCount > 0 ? (
                              <span
                                className="history-row__branch"
                                title={pluralText(
                                  labels.row.branchesAriaLabelOne,
                                  labels.row.branchesAriaLabelOther,
                                  row.branchCount,
                                )}
                              >
                                ⑂ {row.branchCount}
                              </span>
                            ) : null}
                          </>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      {row.lastActivityAt ? (
                        <time dateTime={row.lastActivityAt} title={formatAbsoluteTime(row.lastActivityAt)}>
                          {formatRelativeTime(row.lastActivityAt)}
                        </time>
                      ) : null}
                    </TableCell>
                    {isAdmin ? (
                      <TableCell numeric>
                        <span className="money" title={labels.cost.unavailableTooltip}>
                          ~
                        </span>
                      </TableCell>
                    ) : null}
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  );
}
