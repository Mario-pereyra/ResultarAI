import { cookies } from "next/headers";
import { getTranslations } from "next-intl/server";
import { PrimerAccesoContent } from "./primer-acceso-content";

export default async function PrimerAccesoPage() {
  const cookieStore = await cookies();
  const role = cookieStore.get("role")?.value || "funcional";

  const t = await getTranslations("PrimerAcceso");

  const labels = {
    title: t("title"),
    // t.raw: la plantilla lleva {current}/{total} y quien interpola es el
    // componente cliente (conoce el paso actual); t("step") sin valores
    // renderiza la clave literal "PrimerAcceso.step".
    step: t.raw("step"),
    step1Title: t("step1Title"),
    step1Sub: t("step1Sub"),
    currentPassword: t("currentPassword"),
    newPassword: t("newPassword"),
    repeatPassword: t("repeatPassword"),
    strength: {
      label: t("strength.label"),
      debil: t("strength.debil"),
      regular: t("strength.regular"),
      buena: t("strength.buena"),
      fuerte: t("strength.fuerte"),
    },
    rules: {
      length: t("rules.length"),
      cases: t("rules.cases"),
      number: t("rules.number"),
      symbol: t("rules.symbol"),
    },
    changePasswordBtn: t("changePasswordBtn"),
    step2Title: t("step2Title"),
    step2Sub: t("step2Sub"),
    scanQr: t("scanQr"),
    manualKey: t("manualKey"),
    codeLabel: t("codeLabel"),
    codePlaceholder: t("codePlaceholder"),
    verifyBtn: t("verifyBtn"),
    skipBtn: t("skipBtn"),
    adminWarning: t("adminWarning"),
    backupCodesTitle: t("backupCodesTitle"),
    backupCodesDesc: t("backupCodesDesc"),
    backupCodesSaved: t("backupCodesSaved"),
    step3Title: t("step3Title"),
    step3Sub: t("step3Sub"),
    agreementCheckbox: t("agreementCheckbox"),
    agreementAuditNote: t("agreementAuditNote"),
    acceptBtn: t("acceptBtn"),
    errors: {
      passwordsDoNotMatch: t("errors.passwordsDoNotMatch"),
      totpFailed: t("errors.totpFailed"),
      timeSyncHint: t("errors.timeSyncHint"),
    },
  };

  return <PrimerAccesoContent role={role} labels={labels} />;
}
