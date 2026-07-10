"use client";

import { useState, useTransition, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

export interface LoginContentProps {
  instanceName?: string;
  labels: {
    title: string;
    signIn: string;
    usernameLabel: string;
    usernamePlaceholder: string;
    passwordLabel: string;
    passwordPlaceholder: string;
    showPassword: string;
    hidePassword: string;
    submit: string;
    signingIn: string;
    infoHint: string;
    step2Title: string;
    step2Sub: string;
    totpLabel: string;
    totpPlaceholder: string;
    totpVerify: string;
    totpVerifying: string;
    back: string;
    errors: {
      invalidCredentials: string;
      accountLocked: string;
      authOffline: string;
      totpInvalid: string;
    };
  };
  onLoginSuccess?: () => void;
}

export function LoginContent({
  instanceName = "Resultar Bolivia",
  labels,
  onLoginSuccess,
}: LoginContentProps) {
  const router = useRouter();
  const [step, setStep] = useState<1 | 2>(1);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [totpCode, setTotpCode] = useState("");
  const [pendingToken, setPendingToken] = useState("");
  
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  async function handleStep1Submit(e: FormEvent) {
    e.preventDefault();
    if (!username || !password) return;

    setErrorMsg(null);
    startTransition(async () => {
      try {
        const res = await fetch("/api/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username, password }),
        });

        if (res.status === 400) {
          const err = await res.json();
          if (err.detail === "ACCOUNT_LOCKED") {
            setErrorMsg(labels.errors.accountLocked);
          } else {
            setErrorMsg(labels.errors.invalidCredentials);
            setPassword(""); // Limpiar contraseña
          }
          return;
        }

        if (!res.ok) {
          setErrorMsg(labels.errors.authOffline);
          return;
        }

        const data = await res.json();
        if (data.status === "pending_totp") {
          setPendingToken(data.pending_token);
          setStep(2);
          setTotpCode("");
        } else if (data.status === "success" || data.status === "ok") {
          await handlePostLoginRedirect();
        }
      } catch (err) {
        setErrorMsg(labels.errors.authOffline);
      }
    });
  }

  async function handleStep2Submit(e: FormEvent) {
    e.preventDefault();
    if (!totpCode || !pendingToken) return;

    setErrorMsg(null);
    startTransition(async () => {
      try {
        const res = await fetch("/api/auth/totp/verify", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            pending_token: pendingToken,
            code: totpCode,
          }),
        });

        if (res.status === 400) {
          const err = await res.json();
          if (err.detail === "ACCOUNT_LOCKED") {
            setErrorMsg(labels.errors.accountLocked);
            setStep(1); // Cuenta bloqueada vuelve a paso 1
          } else {
            setErrorMsg(labels.errors.totpInvalid.replace("{count}", "restantes"));
          }
          return;
        }

        if (!res.ok) {
          setErrorMsg(labels.errors.authOffline);
          return;
        }

        const data = await res.json();
        if (data.status === "success" || data.status === "ok") {
          await handlePostLoginRedirect();
        }
      } catch (err) {
        setErrorMsg(labels.errors.authOffline);
      }
    });
  }

  async function handlePostLoginRedirect() {
    if (onLoginSuccess) {
      onLoginSuccess();
      return;
    }
    // Fetch wizard status
    try {
      const res = await fetch("/api/me/wizard/status");
      if (res.ok) {
        const data = await res.json();
        if (data.pending_steps && data.pending_steps.length > 0) {
          router.push("/primer-acceso");
          return;
        }
      }
    } catch (e) {
      // Ignorar
    }
    router.push("/");
  }

  const isLocked = errorMsg === labels.errors.accountLocked;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
        background: "var(--bg)",
        padding: "var(--sp-4)",
      }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          marginBottom: "var(--sp-6)",
        }}
      >
        <svg
          viewBox="0 0 32 32"
          width="40"
          height="40"
          style={{ color: "var(--accent)", marginBottom: "var(--sp-2)" }}
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
        >
          <path d="M6 26L26 6M26 6H12M26 6V20" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <span
          className="kicker"
          style={{
            fontSize: "var(--fs-small)",
            fontWeight: "600",
            letterSpacing: "0.1em",
            color: "var(--ink-dim)",
            textTransform: "uppercase",
          }}
        >
          {instanceName}
        </span>
      </div>

      <div
        className="panel panel--raised"
        style={{
          width: "100%",
          maxWidth: "400px",
          padding: "var(--sp-6)",
          background: "var(--panel)",
          borderRadius: "var(--r-lg)",
          boxShadow: "var(--shadow-lg)",
        }}
      >
        {errorMsg ? (
          <div
            className="error-card"
            role="alert"
            style={{ marginBottom: "var(--sp-4)" }}
          >
            <span className="error-card__icon" aria-hidden="true">
              <svg
                viewBox="0 0 24 24"
                width="18"
                height="18"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
            </span>
            <div>
              {isLocked && <p className="error-card__code">ACCOUNT_LOCKED</p>}
              <p className="error-card__title" style={{ margin: 0, fontWeight: 600 }}>
                {isLocked ? "Cuenta bloqueada temporalmente" : "Error de acceso"}
              </p>
              <p className="error-card__why" style={{ margin: 0, fontSize: "var(--fs-small)" }}>
                {errorMsg}
              </p>
            </div>
          </div>
        ) : null}

        {step === 1 ? (
          <form onSubmit={handleStep1Submit} noValidate>
            <h2
              style={{
                fontSize: "var(--fs-h3)",
                fontWeight: 700,
                marginBottom: "var(--sp-6)",
                textAlign: "center",
              }}
            >
              {labels.signIn}
            </h2>

            <div style={{ display: "flex", flexDirection: "column", gap: "var(--sp-4)" }}>
              <Input
                label={labels.usernameLabel}
                placeholder={labels.usernamePlaceholder}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                disabled={isPending || isLocked}
                required
                autoComplete="username"
              />

              <div style={{ position: "relative" }}>
                <Input
                  label={labels.passwordLabel}
                  placeholder={labels.passwordPlaceholder}
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={isPending || isLocked}
                  required
                  autoComplete="current-password"
                  style={{ paddingRight: "3.5rem" }}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  disabled={isPending || isLocked}
                  aria-pressed={showPassword}
                  className="btn btn--ghost btn--sm"
                  style={{
                    position: "absolute",
                    top: "32px",
                    right: "8px",
                    height: "36px",
                    width: "36px",
                    padding: 0,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                  title={showPassword ? labels.hidePassword : labels.showPassword}
                >
                  <svg
                    viewBox="0 0 24 24"
                    width="18"
                    height="18"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                  >
                    {showPassword ? (
                      <>
                        <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                        <line x1="1" y1="1" x2="23" y2="23" />
                      </>
                    ) : (
                      <>
                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                        <circle cx="12" cy="12" r="3" />
                      </>
                    )}
                  </svg>
                </button>
              </div>

              <Button
                type="submit"
                variant="primary"
                block
                size="lg"
                loading={isPending}
                disabled={isLocked || !username || !password}
              >
                {isPending ? labels.signingIn : labels.submit}
              </Button>

              <hr style={{ border: 0, borderTop: "1px solid var(--border-subtle)", margin: "var(--sp-2) 0" }} />

              <div
                style={{
                  display: "flex",
                  gap: "var(--sp-2)",
                  fontSize: "var(--fs-small)",
                  color: "var(--ink-dim)",
                  lineHeight: "var(--lh-base)",
                }}
              >
                <svg
                  viewBox="0 0 24 24"
                  width="16"
                  height="16"
                  style={{ flexShrink: 0, color: "var(--accent)" }}
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="16" x2="12" y2="12" />
                  <line x1="12" y1="8" x2="12.01" y2="8" />
                </svg>
                <span>{labels.infoHint}</span>
              </div>
            </div>
          </form>
        ) : (
          <form onSubmit={handleStep2Submit} noValidate>
            <h2
              style={{
                fontSize: "var(--fs-h4)",
                fontWeight: 700,
                marginBottom: "var(--sp-2)",
                textAlign: "center",
              }}
            >
              {labels.step2Title}
            </h2>
            <p
              style={{
                fontSize: "var(--fs-small)",
                color: "var(--ink-dim)",
                textAlign: "center",
                marginBottom: "var(--sp-6)",
              }}
            >
              {labels.step2Sub.replace("{name}", username)}
            </p>

            <div style={{ display: "flex", flexDirection: "column", gap: "var(--sp-4)" }}>
              <Input
                label={labels.totpLabel}
                placeholder={labels.totpPlaceholder}
                value={totpCode}
                onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                disabled={isPending}
                required
                maxLength={6}
                inputMode="numeric"
                autoComplete="one-time-code"
                mono
              />

              <div style={{ display: "flex", gap: "var(--sp-2)" }}>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => {
                    setStep(1);
                    setErrorMsg(null);
                  }}
                  disabled={isPending}
                  style={{ flex: 1 }}
                >
                  {labels.back}
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  loading={isPending}
                  disabled={totpCode.length !== 6}
                  style={{ flex: 2 }}
                >
                  {isPending ? labels.totpVerifying : labels.totpVerify}
                </Button>
              </div>
            </div>
          </form>
        )}
      </div>

      <div
        style={{
          marginTop: "var(--sp-6)",
          fontSize: "var(--fs-small)",
          fontFamily: "var(--font-mono)",
          color: "var(--ink-faint)",
        }}
      >
        {/* audit-allow-literal-string: dato técnico de versión de build y locale, no es contenido de usuario traducible */}
        v1.0 · es-BO
      </div>
    </div>
  );
}
