import { getTranslations } from "next-intl/server";
import { LoginContent } from "./login-content";

export default async function LoginPage() {
  const t = await getTranslations("Login");

  const labels = {
    title: t("title"),
    signIn: t("signIn"),
    usernameLabel: t("usernameLabel"),
    usernamePlaceholder: t("usernamePlaceholder"),
    passwordLabel: t("passwordLabel"),
    passwordPlaceholder: t("passwordPlaceholder"),
    showPassword: t("showPassword"),
    hidePassword: t("hidePassword"),
    submit: t("submit"),
    signingIn: t("signingIn"),
    infoHint: t("infoHint"),
    step2Title: t("step2Title"),
    step2Sub: t("step2Sub"),
    totpLabel: t("totpLabel"),
    totpPlaceholder: t("totpPlaceholder"),
    totpVerify: t("totpVerify"),
    totpVerifying: t("totpVerifying"),
    back: t("back"),
    errors: {
      invalidCredentials: t("errors.invalidCredentials"),
      accountLocked: t("errors.accountLocked"),
      authOffline: t("errors.authOffline"),
      totpInvalid: t("errors.totpInvalid"),
    },
  };

  return <LoginContent labels={labels} />;
}
