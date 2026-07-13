"use client";

import { useState, useEffect, useTransition, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { csrfHeaders } from "@/lib/csrf";

export interface PrimerAccesoContentProps {
  role: string;
  labels: {
    title: string;
    step: string;
    step1Title: string;
    step1Sub: string;
    currentPassword: string;
    newPassword: string;
    repeatPassword: string;
    strength: {
      label: string;
      debil: string;
      regular: string;
      buena: string;
      fuerte: string;
    };
    rules: {
      length: string;
      cases: string;
      number: string;
      symbol: string;
    };
    changePasswordBtn: string;
    step2Title: string;
    step2Sub: string;
    scanQr: string;
    manualKey: string;
    codeLabel: string;
    codePlaceholder: string;
    verifyBtn: string;
    skipBtn: string;
    adminWarning: string;
    backupCodesTitle: string;
    backupCodesDesc: string;
    backupCodesSaved: string;
    step3Title: string;
    step3Sub: string;
    agreementCheckbox: string;
    agreementAuditNote: string;
    acceptBtn: string;
    errors: {
      passwordsDoNotMatch: string;
      totpFailed: string;
      timeSyncHint: string;
    };
  };
}

export function PrimerAccesoContent({ role, labels }: PrimerAccesoContentProps) {
  const router = useRouter();
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [loading, setLoading] = useState(true);
  const [isPending, startTransition] = useTransition();
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Paso 1: Contraseña
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [repeatPassword, setRepeatPassword] = useState("");

  // Paso 2: TOTP
  const [totpEnrollData, setTotpEnrollData] = useState<{
    secret: string;
    provisioning_uri: string;
    backup_codes: string[];
  } | null>(null);
  const [totpCode, setTotpCode] = useState("");
  const [totpSuccess, setTotpSuccess] = useState(false);

  // Paso 3: Acuerdo
  const [agreementText, setAgreementText] = useState("");
  const [agreementVersionId, setAgreementVersionId] = useState("");
  const [agreementAccepted, setAgreementAccepted] = useState(false);

  // Cargar estado inicial del Wizard
  useEffect(() => {
    async function loadWizardStatus() {
      try {
        const res = await fetch("/api/me/wizard/status");
        if (!res.ok) throw new Error();
        const data = await res.json();

        if (data.must_change_password) {
          setStep(1);
        } else if (data.totp_enrollment_pending) {
          setStep(2);
          await loadTotpEnrollment();
        } else if (data.agreement_acceptance_pending) {
          setStep(3);
          await loadAgreementStatus();
        } else {
          router.push("/");
        }
      } catch (err) {
        setErrorMsg("Error al conectar con el servidor.");
      } finally {
        setLoading(false);
      }
    }
    loadWizardStatus();
  }, [router]);

  // Cargar datos de TOTP
  async function loadTotpEnrollment() {
    try {
      const res = await fetch("/api/me/totp/enroll", {
        method: "POST",
        headers: { ...csrfHeaders() },
      });
      if (!res.ok) throw new Error();
      const data = await res.json();
      setTotpEnrollData({
        secret: data.secret,
        provisioning_uri: data.provisioning_uri,
        backup_codes: data.backup_codes || [],
      });
    } catch (err) {
      setErrorMsg("Error al iniciar enrolamiento TOTP.");
    }
  }

  // Cargar texto del Acuerdo
  async function loadAgreementStatus() {
    try {
      const res = await fetch("/api/me/agreement/status");
      if (!res.ok) throw new Error();
      const data = await res.json();
      if (data.latest_version) {
        setAgreementText(data.latest_version.text);
        setAgreementVersionId(data.latest_version.id);
      }
    } catch (err) {
      setErrorMsg("Error al obtener el acuerdo de uso.");
    }
  }

  // Reglas de la Contraseña
  const rules = {
    length: newPassword.length >= 12,
    cases: /[A-Z]/.test(newPassword) && /[a-z]/.test(newPassword),
    number: /[0-9]/.test(newPassword),
    symbol: /[^A-Za-z0-9]/.test(newPassword),
  };

  const strengthScore = Object.values(rules).filter(Boolean).length;
  const passwordValid = strengthScore === 4 && newPassword === repeatPassword && currentPassword.length > 0;

  const getStrengthLabel = () => {
    if (newPassword.length === 0) return "";
    if (strengthScore <= 1) return labels.strength.debil;
    if (strengthScore === 2) return labels.strength.regular;
    if (strengthScore === 3) return labels.strength.buena;
    return labels.strength.fuerte;
  };

  const getStrengthColor = () => {
    if (strengthScore <= 1) return "var(--danger)";
    if (strengthScore === 2) return "var(--warn)";
    if (strengthScore === 3) return "var(--info)";
    return "var(--money)";
  };

  const getStrengthPercent = () => {
    return `${(strengthScore / 4) * 100}%`;
  };

  // Enviar cambio de contraseña
  async function handlePasswordSubmit(e: FormEvent) {
    e.preventDefault();
    if (!passwordValid) return;

    setErrorMsg(null);
    startTransition(async () => {
      try {
        const res = await fetch("/api/auth/password", {
          method: "POST",
          headers: { "Content-Type": "application/json", ...csrfHeaders() },
          body: JSON.stringify({
            current_password: currentPassword,
            new_password: newPassword,
          }),
        });

        if (!res.ok) {
          const data = await res.json();
          setErrorMsg(data.detail || "Error al cambiar la contraseña.");
          return;
        }

        // Avanzar a TOTP
        await loadTotpEnrollment();
        setStep(2);
      } catch (err) {
        setErrorMsg("Error de conexión al cambiar la contraseña.");
      }
    });
  }

  // Confirmar TOTP
  async function handleTotpSubmit(e: FormEvent) {
    e.preventDefault();
    if (!totpCode || totpCode.length < 6) return;

    setErrorMsg(null);
    startTransition(async () => {
      try {
        const res = await fetch("/api/me/totp/enable", {
          method: "POST",
          headers: { "Content-Type": "application/json", ...csrfHeaders() },
          body: JSON.stringify({ code: totpCode }),
        });

        if (!res.ok) {
          setErrorMsg(labels.errors.totpFailed + " " + labels.errors.timeSyncHint);
          return;
        }

        setTotpSuccess(true);
      } catch (err) {
        setErrorMsg("Error al verificar el código TOTP.");
      }
    });
  }

  // Saltar TOTP (no-admins)
  function handleSkipTotp() {
    if (role === "admin") return;
    setErrorMsg(null);
    loadAgreementStatus().then(() => {
      setStep(3);
    });
  }

  // Enviar aceptación del acuerdo
  async function handleAgreementSubmit(e: FormEvent) {
    e.preventDefault();
    if (!agreementAccepted || !agreementVersionId) return;

    setErrorMsg(null);
    startTransition(async () => {
      try {
        const res = await fetch("/api/me/agreement/accept", {
          method: "POST",
          headers: { "Content-Type": "application/json", ...csrfHeaders() },
          body: JSON.stringify({ version_id: agreementVersionId }),
        });

        if (!res.ok) {
          const data = await res.json();
          setErrorMsg(data.detail || "Error al guardar aceptación.");
          return;
        }

        // Finalizar y redirigir
        router.push("/");
      } catch (err) {
        setErrorMsg("Error de conexión al aceptar el acuerdo.");
      }
    });
  }

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh", background: "var(--bg)" }}>
        <div className="skeleton" style={{ width: "300px", height: "40px" }}></div>
      </div>
    );
  }

  const isAdmin = role === "admin";

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: "100vh", background: "var(--bg)", padding: "var(--sp-4)" }}>
      
      {/* Kicker y Logo */}
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", marginBottom: "var(--sp-6)" }}>
        <span className="kicker" style={{ fontSize: "var(--fs-small)", fontWeight: 600, color: "var(--ink-dim)" }}>
          {labels.title.toUpperCase()}
        </span>
      </div>

      <div className="panel panel--raised" style={{ width: "100%", maxWidth: "500px", padding: "var(--sp-6)", background: "var(--panel)", borderRadius: "var(--r-lg)", boxShadow: "var(--shadow-lg)" }}>
        
        {/* Indicador de pasos */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--sp-6)", borderBottom: "1px solid var(--border-subtle)", paddingBottom: "var(--sp-3)" }}>
          <span style={{ fontSize: "var(--fs-small)", color: "var(--ink-dim)" }}>
            {labels.step.replace("{current}", String(step)).replace("{total}", "3")}
          </span>
          <div style={{ display: "flex", gap: "var(--sp-2)" }}>
            <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: step >= 1 ? "var(--accent)" : "var(--border)" }}></span>
            <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: step >= 2 ? "var(--accent)" : "var(--border)" }}></span>
            <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: step >= 3 ? "var(--accent)" : "var(--border)" }}></span>
          </div>
        </div>

        {/* Mensaje de Error */}
        {errorMsg && (
          <div className="error-card" role="alert" style={{ marginBottom: "var(--sp-4)" }}>
            <span className="error-card__icon" aria-hidden="true">⚠️</span>
            <div>
              <p className="error-card__why" style={{ margin: 0, fontSize: "var(--fs-small)" }}>
                {errorMsg}
              </p>
            </div>
          </div>
        )}

        {/* PASO 1: CAMBIO DE CONTRASEÑA */}
        {step === 1 && (
          <form onSubmit={handlePasswordSubmit} noValidate>
            <h2 style={{ fontSize: "var(--fs-h4)", fontWeight: 700, marginBottom: "var(--sp-2)" }}>{labels.step1Title}</h2>
            <p style={{ fontSize: "var(--fs-small)", color: "var(--ink-dim)", marginBottom: "var(--sp-6)" }}>{labels.step1Sub}</p>

            <div style={{ display: "flex", flexDirection: "column", gap: "var(--sp-4)" }}>
              <Input
                label={labels.currentPassword}
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                required
              />

              <Input
                label={labels.newPassword}
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
              />

              {/* Strength Meter */}
              {newPassword.length > 0 && (
                <div style={{ marginTop: "-2px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "var(--fs-small)", marginBottom: "4px" }}>
                    <span>{labels.strength.label}</span>
                    <span style={{ color: getStrengthColor(), fontWeight: "bold" }}>{getStrengthLabel()}</span>
                  </div>
                  <div className="quota-bar" role="meter" aria-valuenow={strengthScore} aria-valuemin={0} aria-valuemax={4}>
                    <span className="quota-bar__fill" style={{ width: getStrengthPercent(), background: getStrengthColor() }}></span>
                  </div>
                </div>
              )}

              {/* Rules Checklist */}
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--sp-1)", padding: "var(--sp-2)", background: "var(--bg-subtle)", borderRadius: "var(--r-sm)" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "var(--sp-2)", fontSize: "var(--fs-small)" }}>
                  <span style={{ color: rules.length ? "var(--money)" : "var(--danger)" }}>{rules.length ? "✓" : "✗"}</span>
                  <span style={{ color: rules.length ? "var(--ink)" : "var(--ink-dim)" }}>{labels.rules.length}</span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "var(--sp-2)", fontSize: "var(--fs-small)" }}>
                  <span style={{ color: rules.cases ? "var(--money)" : "var(--danger)" }}>{rules.cases ? "✓" : "✗"}</span>
                  <span style={{ color: rules.cases ? "var(--ink)" : "var(--ink-dim)" }}>{labels.rules.cases}</span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "var(--sp-2)", fontSize: "var(--fs-small)" }}>
                  <span style={{ color: rules.number ? "var(--money)" : "var(--danger)" }}>{rules.number ? "✓" : "✗"}</span>
                  <span style={{ color: rules.number ? "var(--ink)" : "var(--ink-dim)" }}>{labels.rules.number}</span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "var(--sp-2)", fontSize: "var(--fs-small)" }}>
                  <span style={{ color: rules.symbol ? "var(--money)" : "var(--danger)" }}>{rules.symbol ? "✓" : "✗"}</span>
                  <span style={{ color: rules.symbol ? "var(--ink)" : "var(--ink-dim)" }}>{labels.rules.symbol}</span>
                </div>
              </div>

              <Input
                label={labels.repeatPassword}
                type="password"
                value={repeatPassword}
                onChange={(e) => setRepeatPassword(e.target.value)}
                required
              />

              <Button type="submit" variant="primary" disabled={isPending || !passwordValid} loading={isPending} block size="lg">
                {labels.changePasswordBtn}
              </Button>
            </div>
          </form>
        )}

        {/* PASO 2: ENROLAMIENTO TOTP */}
        {step === 2 && (
          <div>
            {!totpSuccess ? (
              <form onSubmit={handleTotpSubmit} noValidate>
                <h2 style={{ fontSize: "var(--fs-h4)", fontWeight: 700, marginBottom: "var(--sp-2)" }}>{labels.step2Title}</h2>
                <p style={{ fontSize: "var(--fs-small)", color: "var(--ink-dim)", marginBottom: "var(--sp-6)" }}>{labels.step2Sub}</p>

                <div style={{ display: "flex", flexDirection: "column", gap: "var(--sp-4)" }}>
                  
                  {/* QR Code */}
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "var(--sp-2)", padding: "var(--sp-4)", background: "var(--bg-subtle)", borderRadius: "var(--r-sm)" }}>
                    <span style={{ fontSize: "var(--fs-small)", fontWeight: 600 }}>{labels.scanQr}</span>
                    {/* audit-allow-literal-color-start: código QR — el blanco/negro debe ser literal para poder escanearse, no participa del theming */}
                    <svg width="128" height="128" viewBox="0 0 29 29" shapeRendering="crispEdges" style={{ background: "#fff", padding: "8px", borderRadius: "4px" }}>
                      <path d="M0 0h7v7H0zm22 0h7v7h-7zM0 22h7v7H0z" fill="#000" />
                      <path d="M2 2h3v3H2zm22 0h3v3h-3zM2 24h3v3H2z" fill="#fff" />
                      <path d="M9 0h1v3H9zm2 0h3v1h-3zm5 0h1v5h-1zm2 0h2v1h-2zm-8 4h3v1h-3zm5 0h2v3h-2zm-6 2h1v2H8zm8 0h3v1h-3zm-5 3h1v2h-1zm2 0h3v1h-3zm-6 2h2v1H9zm5 0h2v2h-2zm5 0h1v3h-1zm-9 2h1v3H9zm4 0h3v1h-3zm6 0h2v1h-2zm-9 2h3v1H9zm5 0h2v2h-2zm4 2h3v1h-3zm-8 2h1v3h-1zm3 0h2v1h-2zm4 0h3v2h-3zm-6 2h1v1h-1zm2 0h1v1h-1zm3 0h2v1h-2z" fill="#000" />
                    </svg>
                    {/* audit-allow-literal-color-end */}
                  </div>

                  {/* Clave Manual */}
                  <div style={{ display: "flex", flexDirection: "column", gap: "var(--sp-2)" }}>
                    <span style={{ fontSize: "var(--fs-small)", fontWeight: 600 }}>{labels.manualKey}</span>
                    <div style={{ display: "flex", gap: "var(--sp-2)", alignItems: "center" }}>
                      <code className="mono" style={{ background: "var(--bg-subtle)", padding: "var(--sp-2) var(--sp-3)", borderRadius: "var(--r-sm)", border: "1px solid var(--border-subtle)", flexGrow: 1, fontSize: "var(--fs-small)" }}>
                        {totpEnrollData?.secret || "Cargando..."}
                      </code>
                    </div>
                  </div>

                  {/* Input Código */}
                  <Input
                    label={labels.codeLabel}
                    placeholder={labels.codePlaceholder}
                    value={totpCode}
                    onChange={(e) => setTotpCode(e.target.value)}
                    maxLength={6}
                    required
                  />

                  {/* Botones */}
                  <div style={{ display: "flex", gap: "var(--sp-2)", marginTop: "var(--sp-2)" }}>
                    {!isAdmin ? (
                      <Button type="button" variant="ghost" onClick={handleSkipTotp} style={{ flex: 1 }}>
                        {labels.skipBtn}
                      </Button>
                    ) : (
                      <div style={{ flex: 1 }}>
                        <span style={{ fontSize: "var(--fs-small)", color: "var(--danger)" }}>
                          ⚠️ {labels.adminWarning}
                        </span>
                      </div>
                    )}
                    <Button type="submit" variant="primary" disabled={isPending || totpCode.length < 6} loading={isPending} style={{ flex: 2 }}>
                      {labels.verifyBtn}
                    </Button>
                  </div>

                </div>
              </form>
            ) : (
              /* Códigos de respaldo */
              <div>
                <h2 style={{ fontSize: "var(--fs-h4)", fontWeight: 700, marginBottom: "var(--sp-2)" }}>{labels.backupCodesTitle}</h2>
                <p style={{ fontSize: "var(--fs-small)", color: "var(--ink-dim)", marginBottom: "var(--sp-6)" }}>{labels.backupCodesDesc}</p>

                <div style={{ display: "flex", flexDirection: "column", gap: "var(--sp-4)" }}>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--sp-2)", fontFamily: "var(--font-mono)", fontSize: "var(--fs-small)", background: "var(--bg-subtle)", padding: "var(--sp-3)", borderRadius: "var(--r-sm)", border: "1px solid var(--border-subtle)" }}>
                    {totpEnrollData?.backup_codes.map((code) => (
                      <div key={code} style={{ textAlign: "center", color: "var(--ink)" }}>{code}</div>
                    ))}
                  </div>

                  <Button
                    type="button"
                    variant="primary"
                    block
                    onClick={async () => {
                      await loadAgreementStatus();
                      setStep(3);
                    }}
                  >
                    {labels.backupCodesSaved}
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* PASO 3: ACUERDO DE USO */}
        {step === 3 && (
          <form onSubmit={handleAgreementSubmit} noValidate>
            <h2 style={{ fontSize: "var(--fs-h4)", fontWeight: 700, marginBottom: "var(--sp-2)" }}>{labels.step3Title}</h2>
            <p style={{ fontSize: "var(--fs-small)", color: "var(--ink-dim)", marginBottom: "var(--sp-6)" }}>{labels.step3Sub}</p>

            <div style={{ display: "flex", flexDirection: "column", gap: "var(--sp-4)" }}>
              
              {/* Acuerdo scrollable */}
              <div style={{ height: "200px", overflowY: "scroll", padding: "var(--sp-3)", background: "var(--bg-subtle)", border: "1px solid var(--border-subtle)", borderRadius: "var(--r-sm)", fontSize: "var(--fs-small)", lineHeight: "var(--lh-base)", whiteSpace: "pre-line" }}>
                {agreementText || "Cargando acuerdo..."}
              </div>

              {/* Checkbox */}
              <div className="check-row" style={{ display: "flex", alignItems: "flex-start", gap: "var(--sp-2)", padding: "var(--sp-1) 0" }}>
                <input
                  type="checkbox"
                  id="agree-checkbox"
                  className="checkbox"
                  checked={agreementAccepted}
                  onChange={(e) => setAgreementAccepted(e.target.checked)}
                  style={{ marginTop: "4px" }}
                />
                <label htmlFor="agree-checkbox" style={{ fontSize: "var(--fs-small)", lineHeight: "var(--lh-base)", cursor: "pointer" }}>
                  {labels.agreementCheckbox}
                </label>
              </div>

              {/* Nota de auditoría */}
              <p style={{ fontSize: "var(--fs-xsmall)", color: "var(--ink-faint)", margin: 0 }}>
                {labels.agreementAuditNote}
              </p>

              <Button type="submit" variant="primary" disabled={isPending || !agreementAccepted} loading={isPending} block size="lg">
                {labels.acceptBtn}
              </Button>
            </div>
          </form>
        )}

      </div>
    </div>
  );
}
