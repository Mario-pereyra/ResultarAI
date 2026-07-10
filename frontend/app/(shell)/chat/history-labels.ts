import type { getTranslations } from "next-intl/server";
import type { HistoryContentLabels } from "./history-content";

type Translator = Awaited<ReturnType<typeof getTranslations>>;

/** Arma `HistoryContentLabels` desde el namespace `History` de
 * `messages/es.json` (tareas 7.1-7.4, `chat/page.tsx`, el historial de vista
 * 12). Mismo patrón que `buildChatLabels` de `./labels.ts`: plantillas con
 * placeholder literal `{n}`/`{q}` para los datos que solo existen en
 * runtime del cliente (conteos, término buscado) -- ver el docstring de
 * `HistoryContentLabels` en `history-content.tsx`. */
export function buildHistoryLabels(t: Translator): HistoryContentLabels {
  return {
    title: t("title"),
    newSession: t("newSession"),
    search: {
      label: t("search.label"),
      placeholder: t("search.placeholder"),
    },
    agentFilter: {
      label: t("agentFilter.label"),
      all: t("agentFilter.all"),
    },
    tabs: {
      label: t("tabs.label"),
      active: t("tabs.active"),
      archived: t("tabs.archived"),
    },
    columns: {
      session: t("columns.session"),
      lastActivity: t("columns.lastActivity"),
    },
    row: {
      untitled: t("row.untitled"),
      messageCountOne: t("row.messageCountOne", { n: "{n}" }),
      messageCountOther: t("row.messageCountOther", { n: "{n}" }),
      branchesAriaLabelOne: t("row.branchesAriaLabelOne", { n: "{n}" }),
      branchesAriaLabelOther: t("row.branchesAriaLabelOther", { n: "{n}" }),
      matchInTitle: t("row.matchInTitle"),
      matchInMessage: t("row.matchInMessage"),
    },
    cost: {
      columnLabel: t("cost.columnLabel"),
      unavailableTooltip: t("cost.unavailableTooltip"),
      periodTotalPrefix: t("cost.periodTotalPrefix"),
      periodSessionsOne: t("cost.periodSessionsOne", { n: "{n}" }),
      periodSessionsOther: t("cost.periodSessionsOther", { n: "{n}" }),
    },
    empty: {
      firstTime: {
        title: t("empty.firstTime.title"),
        hint: t("empty.firstTime.hint"),
        cta: t("empty.firstTime.cta"),
      },
      noResults: {
        title: t("empty.noResults.title", { q: "{q}" }),
        titleGeneric: t("empty.noResults.titleGeneric"),
        hint: t("empty.noResults.hint"),
        clear: t("empty.noResults.clear"),
      },
      archived: {
        title: t("empty.archived.title"),
        hint: t("empty.archived.hint"),
      },
    },
    error: {
      title: t("error.title"),
      why: t("error.why"),
      retry: t("error.retry"),
    },
    loading: t("loading"),
  };
}
