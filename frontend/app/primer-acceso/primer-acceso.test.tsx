import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { PrimerAccesoContent } from "./primer-acceso-content";

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    refresh: vi.fn(),
  }),
}));

const mockLabels = {
  title: "Primer acceso",
  step: "Paso {current} de {total}",
  step1Title: "Contraseña nueva",
  step1Sub: "Establecé una contraseña segura para tu cuenta.",
  currentPassword: "Contraseña actual (temporal)",
  newPassword: "Contraseña nueva",
  repeatPassword: "Repetir contraseña",
  strength: {
    label: "Fortaleza:",
    debil: "débil",
    regular: "regular",
    buena: "buena",
    fuerte: "fuerte"
  },
  rules: {
    length: "Mínimo 12 caracteres",
    cases: "Mayúscula y minúscula",
    number: "Al menos un número",
    symbol: "Al menos un símbolo (ej. !@#$%^&*)"
  },
  changePasswordBtn: "Cambiar contraseña",
  step2Title: "Configuración de segundo factor (TOTP)",
  step2Sub: "Escaneá el código QR con tu aplicación autenticadora o ingresá la clave manual.",
  scanQr: "Escaneá el código QR:",
  manualKey: "Clave manual:",
  codeLabel: "Código de 6 dígitos",
  codePlaceholder: "000000",
  verifyBtn: "Confirmar y enrolar",
  skipBtn: "Configurar más tarde",
  adminWarning: "Tu rol requiere verificación en dos pasos.",
  backupCodesTitle: "Códigos de respaldo generados",
  backupCodesDesc: "Guardá estos códigos en un lugar seguro...",
  backupCodesSaved: "Ya guardé los códigos",
  step3Title: "Acuerdo de uso",
  step3Sub: "Leé y aceptá los términos y condiciones de uso del sistema.",
  agreementCheckbox: "Leí y acepto el acuerdo de uso",
  agreementAuditNote: "Tu aceptación queda registrada con fecha, hora y versión del acuerdo.",
  acceptBtn: "Aceptar y entrar",
  errors: {
    passwordsDoNotMatch: "Las contraseñas no coinciden.",
    totpFailed: "Código incorrecto o vencido — los códigos rotan cada 30 s.",
    timeSyncHint: "Si el problema persiste, verificá la hora del teléfono."
  }
};

describe("PrimerAccesoContent", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    global.fetch = vi.fn();
  });

  it("renderiza el paso 1 (Contraseña) si la API indica que debe cambiarla", async () => {
    global.fetch = vi.fn().mockImplementation(async (url: string) => {
      if (url.includes("/api/me/wizard/status")) {
        return {
          status: 200,
          ok: true,
          json: async () => ({
            must_change_password: true,
            totp_enrollment_pending: false,
            agreement_acceptance_pending: false,
            pending_steps: ["password_change"]
          }),
        };
      }
      return { status: 404, ok: false, json: async () => ({}) };
    });

    render(<PrimerAccesoContent role="funcional" labels={mockLabels} />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: mockLabels.step1Title })).toBeDefined();
    });

    const currentPassInput = document.querySelector('input[type="password"]') as HTMLInputElement;
    expect(currentPassInput).toBeDefined();
  });

  it("actualiza dinámicamente la fortaleza de contraseña y habilita submit solo si es fuerte", async () => {
    global.fetch = vi.fn().mockImplementation(async (url: string) => {
      if (url.includes("/api/me/wizard/status")) {
        return {
          status: 200,
          ok: true,
          json: async () => ({
            must_change_password: true,
            totp_enrollment_pending: false,
            agreement_acceptance_pending: false,
            pending_steps: ["password_change"]
          }),
        };
      }
      return { status: 404, ok: false, json: async () => ({}) };
    });

    render(<PrimerAccesoContent role="funcional" labels={mockLabels} />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: mockLabels.step1Title })).toBeDefined();
    });

    const currentInput = document.querySelectorAll('input[type="password"]')[0] as HTMLInputElement;
    const newInput = document.querySelectorAll('input[type="password"]')[1] as HTMLInputElement;
    const repeatInput = document.querySelectorAll('input[type="password"]')[2] as HTMLInputElement;
    const submitBtn = screen.getByRole("button", { name: mockLabels.changePasswordBtn });

    expect(submitBtn.hasAttribute("disabled")).toBe(true);

    // Ingresar contraseña débil
    fireEvent.change(currentInput, { target: { value: "temp123" } });
    fireEvent.change(newInput, { target: { value: "debil" } });
    fireEvent.change(repeatInput, { target: { value: "debil" } });
    expect(screen.getByText(mockLabels.strength.debil)).toBeDefined();
    expect(submitBtn.hasAttribute("disabled")).toBe(true);

    // Ingresar contraseña fuerte
    fireEvent.change(newInput, { target: { value: "Segura12345!" } });
    fireEvent.change(repeatInput, { target: { value: "Segura12345!" } });
    expect(screen.getByText(mockLabels.strength.fuerte)).toBeDefined();
    expect(submitBtn.hasAttribute("disabled")).toBe(false);
  });

  it("avanza a TOTP (Paso 2) después de cambiar contraseña exitosamente", async () => {
    global.fetch = vi.fn().mockImplementation(async (url: string) => {
      if (url.includes("/api/me/wizard/status")) {
        return {
          status: 200,
          ok: true,
          json: async () => ({
            must_change_password: true,
            totp_enrollment_pending: true,
            agreement_acceptance_pending: true,
            pending_steps: ["password_change", "totp_enrollment", "agreement_acceptance"]
          }),
        };
      }
      if (url.includes("/api/auth/password")) {
        return {
          status: 200,
          ok: true,
          json: async () => ({ status: "success" }),
        };
      }
      if (url.includes("/api/me/totp/enroll")) {
        return {
          status: 200,
          ok: true,
          json: async () => ({
            secret: "JBSWY3DPEHPK3PXP",
            provisioning_uri: "otpauth://totp/Resultar?secret=JBSWY3DPEHPK3PXP",
            backup_codes: ["1234-5678", "8765-4321"]
          }),
        };
      }
      return { status: 404, ok: false, json: async () => ({}) };
    });

    render(<PrimerAccesoContent role="funcional" labels={mockLabels} />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: mockLabels.step1Title })).toBeDefined();
    });

    const currentInput = document.querySelectorAll('input[type="password"]')[0] as HTMLInputElement;
    const newInput = document.querySelectorAll('input[type="password"]')[1] as HTMLInputElement;
    const repeatInput = document.querySelectorAll('input[type="password"]')[2] as HTMLInputElement;
    const submitBtn = screen.getByRole("button", { name: mockLabels.changePasswordBtn });

    fireEvent.change(currentInput, { target: { value: "temp123456789" } });
    fireEvent.change(newInput, { target: { value: "Segura12345!" } });
    fireEvent.change(repeatInput, { target: { value: "Segura12345!" } });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: mockLabels.step2Title })).toBeDefined();
      expect(screen.getByText("JBSWY3DPEHPK3PXP")).toBeDefined();
    });
  });

  it("permite saltar TOTP a usuarios no-admin, pero obliga a los admin", async () => {
    global.fetch = vi.fn().mockImplementation(async (url: string) => {
      if (url.includes("/api/me/wizard/status")) {
        return {
          status: 200,
          ok: true,
          json: async () => ({
            must_change_password: false,
            totp_enrollment_pending: true,
            agreement_acceptance_pending: true,
            pending_steps: ["totp_enrollment", "agreement_acceptance"]
          }),
        };
      }
      if (url.includes("/api/me/totp/enroll")) {
        return {
          status: 200,
          ok: true,
          json: async () => ({
            secret: "JBSWY3DPEHPK3PXP",
            provisioning_uri: "otpauth://totp/Resultar?secret=JBSWY3DPEHPK3PXP",
            backup_codes: []
          }),
        };
      }
      if (url.includes("/api/me/agreement/status")) {
        return {
          status: 200,
          ok: true,
          json: async () => ({
            status: "pendiente",
            latest_version: {
              id: "uuid-version",
              text: "Contenido del acuerdo de uso legal.",
              version_number: 1
            }
          }),
        };
      }
      return { status: 404, ok: false, json: async () => ({}) };
    });

    const { unmount } = render(<PrimerAccesoContent role="funcional" labels={mockLabels} />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: mockLabels.step2Title })).toBeDefined();
    });

    const skipBtn = screen.getByRole("button", { name: mockLabels.skipBtn });
    fireEvent.click(skipBtn);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: mockLabels.step3Title })).toBeDefined();
    });

    unmount();

    // Caso admin
    render(<PrimerAccesoContent role="admin" labels={mockLabels} />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: mockLabels.step2Title })).toBeDefined();
    });

    expect(screen.queryByRole("button", { name: mockLabels.skipBtn })).toBeNull();
    expect(screen.getByText(new RegExp(mockLabels.adminWarning))).toBeDefined();
  });

  it("muestra códigos de respaldo al verificar TOTP y avanza al paso 3 al confirmarlos", async () => {
    global.fetch = vi.fn().mockImplementation(async (url: string) => {
      if (url.includes("/api/me/wizard/status")) {
        return {
          status: 200,
          ok: true,
          json: async () => ({
            must_change_password: false,
            totp_enrollment_pending: true,
            agreement_acceptance_pending: true,
            pending_steps: ["totp_enrollment", "agreement_acceptance"]
          }),
        };
      }
      if (url.includes("/api/me/totp/enroll")) {
        return {
          status: 200,
          ok: true,
          json: async () => ({
            secret: "JBSWY3DPEHPK3PXP",
            provisioning_uri: "otpauth://totp/Resultar?secret=JBSWY3DPEHPK3PXP",
            backup_codes: ["BK-0001", "BK-0002"]
          }),
        };
      }
      if (url.includes("/api/me/totp/enable")) {
        return {
          status: 200,
          ok: true,
          json: async () => ({ status: "success" }),
        };
      }
      if (url.includes("/api/me/agreement/status")) {
        return {
          status: 200,
          ok: true,
          json: async () => ({
            status: "pendiente",
            latest_version: {
              id: "uuid-version",
              text: "Contenido del acuerdo de uso legal.",
              version_number: 1
            }
          }),
        };
      }
      return { status: 404, ok: false, json: async () => ({}) };
    });

    render(<PrimerAccesoContent role="admin" labels={mockLabels} />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: mockLabels.step2Title })).toBeDefined();
    });

    const codeInput = screen.getByPlaceholderText(mockLabels.codePlaceholder);
    fireEvent.change(codeInput, { target: { value: "123456" } });

    const verifyBtn = screen.getByRole("button", { name: mockLabels.verifyBtn });
    fireEvent.click(verifyBtn);

    // Debe mostrar los códigos de respaldo
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: mockLabels.backupCodesTitle })).toBeDefined();
      expect(screen.getByText("BK-0001")).toBeDefined();
      expect(screen.getByText("BK-0002")).toBeDefined();
    });

    // Clic en Confirmar guardado de códigos para avanzar al paso 3
    const savedBtn = screen.getByRole("button", { name: mockLabels.backupCodesSaved });
    fireEvent.click(savedBtn);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: mockLabels.step3Title })).toBeDefined();
      expect(screen.getByText("Contenido del acuerdo de uso legal.")).toBeDefined();
    });
  });

  it("deshabilita submit del paso 3 hasta aceptar checkbox, guardando aceptación en la API", async () => {
    const fetchMock = vi.fn().mockImplementation(async (url: string) => {
      if (url.includes("/api/me/wizard/status")) {
        return {
          status: 200,
          ok: true,
          json: async () => ({
            must_change_password: false,
            totp_enrollment_pending: false,
            agreement_acceptance_pending: true,
            pending_steps: ["agreement_acceptance"]
          }),
        };
      }
      if (url.includes("/api/me/agreement/status")) {
        return {
          status: 200,
          ok: true,
          json: async () => ({
            status: "pendiente",
            latest_version: {
              id: "uuid-agreement-version",
              text: "Texto legal definitivo.",
              version_number: 1
            }
          }),
        };
      }
      if (url.includes("/api/me/agreement/accept")) {
        return {
          status: 200,
          ok: true,
          json: async () => ({ status: "success" }),
        };
      }
      return { status: 404, ok: false, json: async () => ({}) };
    });

    global.fetch = fetchMock;

    render(<PrimerAccesoContent role="funcional" labels={mockLabels} />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: mockLabels.step3Title })).toBeDefined();
    });

    const checkbox = document.querySelector('input[type="checkbox"]') as HTMLInputElement;
    const submitBtn = screen.getByRole("button", { name: mockLabels.acceptBtn });

    expect(submitBtn.hasAttribute("disabled")).toBe(true);

    fireEvent.click(checkbox);
    expect(submitBtn.hasAttribute("disabled")).toBe(false);

    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/api/me/agreement/accept"), expect.any(Object));
    });
  });
});
