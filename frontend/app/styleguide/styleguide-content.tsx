"use client";

import { useEffect, useId, useState } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { Dropdown } from "@/components/ui/dropdown";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Panel } from "@/components/ui/panel";
import { RoleBadge } from "@/components/ui/role-badge";
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
import { Tag, type TagVariant } from "@/components/ui/tag";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip } from "@/components/ui/tooltip";
import { ToastStack, useToasts, type ToastVariant } from "@/components/ui/toast";
import { AprobacionesIcon, ChatIcon } from "@/components/shell/icons";
import {
  formatAggregatedAmountBO,
  formatDateBO,
  formatDateTimeBO,
  formatLlmCostBO,
  formatPercentBO,
  formatTokensBO,
} from "@/lib/format-bo";
import "../../styles/shell.css";
import "./styleguide.css";

/**
 * Contenido interactivo de /styleguide (tarea 7.3, d10-design-system-shell).
 * Ver app/styleguide/page.tsx para por qué esta página vive fuera del
 * grupo (shell) y por qué este componente usa `useTranslations` en vez de
 * recibir `labels` por props.
 */

type ThemeName = "dark" | "light";
type Brand = "default" | "totvs";

/**
 * Fecha de ejemplo fija (11/06/2026 14:32) — misma que
 * design/DESIGN-SYSTEM.md §9.8 y lib/format-bo.test.ts, para que la
 * demostración de formatos es-BO sea determinista (no `new Date()` real).
 */
const SAMPLE_DATE = new Date(2026, 5, 11, 14, 32);

const TAG_DEMO: Array<{ key: string; variant?: TagVariant; outline?: boolean }> = [
  { key: "neutral" },
  { key: "active", variant: "accent" },
  { key: "evalScore", variant: "money" },
  { key: "modeloAlterno", variant: "info" },
  { key: "truncado", variant: "warn" },
  { key: "bloqueado", variant: "danger" },
  { key: "needsPro", variant: "alt" },
];

const RISK_TAG_DEMO: Array<{ key: string; variant: TagVariant }> = [
  { key: "riesgoBajo", variant: "money" },
  { key: "riesgoMedio", variant: "warn" },
  { key: "riesgoAlto", variant: "alt" },
  { key: "riesgoCritico", variant: "danger" },
];

export function StyleguideContent() {
  const t = useTranslations("Styleguide");
  const [theme, setTheme] = useState<ThemeName>("dark");
  const [brand, setBrand] = useState<Brand>("default");
  const [modalOpen, setModalOpen] = useState(false);
  const toasts = useToasts();
  const formId = useId();

  // Switcher client-side puro (escenario "Styleguide renderiza los 4
  // sets"): manipula data-theme/data-brand de <html> directamente, SIN
  // tocar la cookie `theme` (app/api/theme/route.ts) — a propósito, para
  // no interferir con la preferencia real persistida del usuario ni con
  // el switcher de producción del topbar (ver nota en page.tsx).
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.dataset.brand = brand;
  }, [theme, brand]);

  function showToast(variant: ToastVariant) {
    const copy: Record<ToastVariant, { title: string; message: string }> = {
      info: { title: t("toast.infoTitle"), message: t("toast.infoMessage") },
      success: { title: t("toast.successTitle"), message: t("toast.successMessage") },
      warn: { title: t("toast.warnTitle"), message: t("toast.warnMessage") },
      danger: { title: t("toast.dangerTitle"), message: t("toast.dangerMessage") },
    };
    toasts.show({ variant, ...copy[variant] });
  }

  return (
    <div className="sg-page">
      <div className="sg-switcher" role="group" aria-label={t("switcher.groupLabel")}>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={() => setTheme((current) => (current === "dark" ? "light" : "dark"))}
        >
          {t("switcher.themeButton", { theme: t(`themeNames.${theme}`) })}
        </Button>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={() => setBrand((current) => (current === "totvs" ? "default" : "totvs"))}
        >
          {t("switcher.brandButton", { brand: t(`brandNames.${brand}`) })}
        </Button>
      </div>

      <header>
        <span className="sg-label">{t("kicker")}</span>
        <h1 style={{ fontFamily: "var(--font-display)", fontSize: "var(--fs-h1)" }}>{t("title")}</h1>
        <p>{t("intro")}</p>
        <p className="sg-caption">
          {t("activeCombo", { theme: t(`themeNames.${theme}`), brand: t(`brandNames.${brand}`) })}
        </p>
        <span className="sg-dev-notice">{t("devNotice")}</span>
      </header>

      {/* ── Botones ─────────────────────────────────────────────────── */}
      <section className="sg-section">
        <h2>{t("sections.buttons")}</h2>
        <span className="sg-label">{t("buttons.default")}</span>
        <div className="sg-row">
          <Button variant="primary">{t("buttons.primary")}</Button>
          <Button variant="secondary">{t("buttons.secondary")}</Button>
          <Button variant="danger">{t("buttons.danger")}</Button>
          <Button variant="ghost">{t("buttons.ghost")}</Button>
        </div>
        <span className="sg-label">{t("buttons.disabled")}</span>
        <div className="sg-row">
          <Button variant="primary" disabled>
            {t("buttons.primary")}
          </Button>
          <Button variant="secondary" disabled>
            {t("buttons.secondary")}
          </Button>
          <Button variant="danger" disabled>
            {t("buttons.danger")}
          </Button>
        </div>
        <span className="sg-label">{t("buttons.loading")}</span>
        <div className="sg-row">
          <Button variant="primary" loading>
            {t("buttons.primary")}
          </Button>
          <Button variant="secondary" loading>
            {t("buttons.secondary")}
          </Button>
        </div>
        <span className="sg-label">{t("buttons.sizes")}</span>
        <div className="sg-row">
          <Button size="sm">{t("buttons.small")}</Button>
          <Button>{t("buttons.standard")}</Button>
          <Button size="lg">{t("buttons.large")}</Button>
        </div>
      </section>

      {/* ── Formularios ─────────────────────────────────────────────── */}
      <section className="sg-section">
        <h2>{t("sections.fields")}</h2>
        <div className="sg-grid sg-grid--wide">
          <Panel>
            <Input
              label={t("fields.nameLabel")}
              placeholder={t("fields.namePlaceholder")}
              hint={t("fields.nameHint")}
              required
            />
            <Input label={t("fields.paramLabel")} mono defaultValue="MV_PAISLOC" />
            <Input
              label={t("fields.emailLabel")}
              type="email"
              defaultValue="lucia@resultar"
              error={t("fields.emailError")}
            />
            <Input label={t("fields.disabledLabel")} defaultValue={t("fields.disabledValue")} disabled />
          </Panel>
          <Panel>
            <Select label={t("fields.envLabel")} required defaultValue="">
              <option value="" disabled>
                {t("fields.envPlaceholder")}
              </option>
              <option value="test">{t("fields.envTest")}</option>
              <option value="prod">{t("fields.envProd")}</option>
            </Select>
            <span className="sg-caption">{t("fields.envHint")}</span>
            <Textarea label={t("fields.commentLabel")} placeholder={t("fields.commentPlaceholder")} required />
          </Panel>
        </div>
      </section>

      {/* ── Tabla de datos ──────────────────────────────────────────── */}
      <section className="sg-section">
        <h2>{t("sections.table")}</h2>
        <Table caption={t("table.caption")} dense>
          <TableHead>
            <TableRow>
              <TableHeaderCell>{t("table.colParam")}</TableHeaderCell>
              <TableHeaderCell>{t("table.colDescription")}</TableHeaderCell>
              <TableHeaderCell>{t("table.colExpected")}</TableHeaderCell>
              <TableHeaderCell>{t("table.colFound")}</TableHeaderCell>
              <TableHeaderCell>{t("table.colStatus")}</TableHeaderCell>
              <TableHeaderCell>{t("table.colCost")}</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            <TableRow>
              <TableCell className="mono">MV_PAISLOC</TableCell>
              <TableCell>{t("table.descLocalizacion")}</TableCell>
              <TableCell className="mono">BOL</TableCell>
              <TableCell className="mono">BOL</TableCell>
              <TableCell>
                <Tag variant="money">{t("table.statusOk")}</Tag>
              </TableCell>
              <TableCell numeric>{formatLlmCostBO(0.0008)}</TableCell>
            </TableRow>
            <TableRow selected>
              <TableCell className="mono">MV_TIMBRE</TableCell>
              <TableCell>{t("table.descTimbrado")}</TableCell>
              <TableCell className="mono">2026-1</TableCell>
              <TableCell className="mono">2025-2</TableCell>
              <TableCell>
                <Tag variant="danger">{t("table.statusDiff")}</Tag>
              </TableCell>
              <TableCell numeric>{formatLlmCostBO(0.0011)}</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </section>

      {/* ── Panel, tags y badges de rol ─────────────────────────────── */}
      <section className="sg-section">
        <h2>{t("sections.panelTagBadge")}</h2>
        <Panel>
          <h3 style={{ fontFamily: "var(--font-display)", fontSize: "var(--fs-h4)" }}>{t("panel.title")}</h3>
          <p>{t("panel.body")}</p>
        </Panel>
        <span className="sg-label" style={{ marginTop: "var(--sp-4)" }}>
          {t("sections.panelTagBadge")}
        </span>
        <div className="sg-row">
          {TAG_DEMO.map(({ key, variant }) => (
            <Tag key={key} variant={variant}>
              {t(`tags.${key}`)}
            </Tag>
          ))}
        </div>
        <div className="sg-row">
          {RISK_TAG_DEMO.map(({ key, variant }) => (
            <Tag key={key} variant={variant}>
              {t(`tags.${key}`)}
            </Tag>
          ))}
        </div>
        <div className="sg-row">
          <RoleBadge role="admin" label="Admin" />
          <RoleBadge role="tecnico" label="Técnico" />
          <RoleBadge role="funcional" label="Funcional" />
        </div>
      </section>

      {/* ── Toasts ──────────────────────────────────────────────────── */}
      <section className="sg-section">
        <h2>{t("sections.toast")}</h2>
        <div className="sg-row">
          <Button variant="secondary" size="sm" onClick={() => showToast("info")}>
            {t("toast.triggerInfo")}
          </Button>
          <Button variant="secondary" size="sm" onClick={() => showToast("success")}>
            {t("toast.triggerSuccess")}
          </Button>
          <Button variant="secondary" size="sm" onClick={() => showToast("warn")}>
            {t("toast.triggerWarn")}
          </Button>
          <Button variant="secondary" size="sm" onClick={() => showToast("danger")}>
            {t("toast.triggerDanger")}
          </Button>
        </div>
        <ToastStack
          toasts={toasts.toasts}
          onDismiss={toasts.dismiss}
          label={t("toast.stackLabel")}
          dismissLabel={t("toast.dismissLabel")}
        />
      </section>

      {/* ── Modal ───────────────────────────────────────────────────── */}
      <section className="sg-section">
        <h2>{t("sections.modal")}</h2>
        <Button variant="danger" size="sm" onClick={() => setModalOpen(true)}>
          {t("modal.openButton")}
        </Button>
        <Modal
          open={modalOpen}
          onClose={() => setModalOpen(false)}
          title={t("modal.title")}
          closeLabel={t("modal.closeLabel")}
          footer={
            <>
              <Button variant="ghost" onClick={() => setModalOpen(false)}>
                {t("modal.cancel")}
              </Button>
              <Button variant="danger" onClick={() => setModalOpen(false)}>
                {t("modal.confirmDanger")}
              </Button>
            </>
          }
        >
          <p>{t("modal.body")}</p>
        </Modal>
      </section>

      {/* ── Dropdown ────────────────────────────────────────────────── */}
      <section className="sg-section">
        <h2>{t("sections.dropdown")}</h2>
        <Dropdown
          triggerLabel={t("dropdown.triggerLabel")}
          items={[
            { id: "one", label: t("dropdown.itemOne"), onSelect: () => {} },
            { id: "two", label: t("dropdown.itemTwo"), onSelect: () => {} },
            { id: "danger", label: t("dropdown.itemDanger"), onSelect: () => {}, danger: true },
          ]}
        />
      </section>

      {/* ── Tooltip ─────────────────────────────────────────────────── */}
      <section className="sg-section">
        <h2>{t("sections.tooltip")}</h2>
        <Tooltip label={t("tooltip.tipText")}>
          <Button variant="secondary" size="sm">
            {t("tooltip.triggerLabel")}
          </Button>
        </Tooltip>
      </section>

      {/* ── Skeleton y empty state ──────────────────────────────────── */}
      <section className="sg-section">
        <h2>{t("sections.skeletonEmpty")}</h2>
        <div className="sg-grid sg-grid--wide">
          <Panel>
            <Skeleton variant="title" label={t("skeleton.loadingLabel")} />
            <div style={{ marginTop: "var(--sp-3)" }}>
              <Skeleton variant="text" lines={3} label={t("skeleton.loadingLabel")} />
            </div>
            <div style={{ marginTop: "var(--sp-4)" }}>
              <Skeleton variant="block" label={t("skeleton.loadingLabel")} />
            </div>
          </Panel>
          <EmptyState
            icon={<AprobacionesIcon />}
            title={t("emptyState.title")}
            description={t("emptyState.hint")}
          />
          <EmptyState
            icon={<ChatIcon />}
            title={t("emptyState.ctaTitle")}
            description={t("emptyState.ctaHint")}
            action={
              <Button size="sm" variant="primary">
                {t("emptyState.ctaAction")}
              </Button>
            }
          />
        </div>
      </section>

      {/* ── Formatos es-BO (tarea 6.3) ──────────────────────────────── */}
      <section className="sg-section">
        <h2>{t("sections.formats")}</h2>
        <p className="sg-caption">{t("formats.implementationNote")}</p>
        <dl className="sg-formats-list" id={formId}>
          <dt>{t("formats.dateLabel")}</dt>
          <dd className="mono">{formatDateBO(SAMPLE_DATE)}</dd>

          <dt>{t("formats.dateTimeLabel")}</dt>
          <dd className="mono">{formatDateTimeBO(SAMPLE_DATE)}</dd>

          <dt>{t("formats.llmCostLabel")}</dt>
          <dd className="money">{formatLlmCostBO(0.0042)}</dd>

          <dt>{t("formats.aggregatedLabel")}</dt>
          <dd className="money">{formatAggregatedAmountBO(1284.5)}</dd>

          <dt>{t("formats.percentLabel")}</dt>
          <dd className="mono">{formatPercentBO(0.82)}</dd>

          <dt>{t("formats.tokensLabel")}</dt>
          <dd className="mono">{formatTokensBO(12400)}</dd>
        </dl>
      </section>
    </div>
  );
}
