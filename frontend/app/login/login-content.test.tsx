import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { LoginContent } from "./login-content";

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    refresh: vi.fn(),
  }),
}));

const mockLabels = {
  title: "ResultarAI",
  signIn: "Iniciar sesión",
  usernameLabel: "Usuario",
  usernamePlaceholder: "Ingresá tu usuario",
  passwordLabel: "Contraseña",
  passwordPlaceholder: "Ingresá tu contraseña",
  showPassword: "Mostrar contraseña",
  hidePassword: "Ocultar contraseña",
  submit: "Ingresar",
  signingIn: "Ingresando...",
  infoHint: "Las cuentas las crea el administrador de tu organización.",
  step2Title: "Verificación en dos pasos",
  step2Sub: "Hola {name}, ingresá el código TOTP de tu aplicación para continuar.",
  totpLabel: "Código de verificación",
  totpPlaceholder: "000000",
  totpVerify: "Verificar",
  totpVerifying: "Verificando...",
  back: "Volver",
  errors: {
    invalidCredentials: "Usuario o contraseña incorrectos.",
    accountLocked: "Cuenta bloqueada temporalmente. Demasiados intentos fallidos. Se desbloquea en 15 min o pedile al administrador que la libere.",
    authOffline: "El servicio no está disponible. Intentá de nuevo en unos minutos.",
    totpInvalid: "Código incorrecto o vencido — los códigos rotan cada 30 s. Intentos restantes: {count}"
  }
};

describe("LoginContent", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    global.fetch = vi.fn();
  });

  it("renderiza el formulario de login (Paso 1) correctamente", () => {
    render(<LoginContent labels={mockLabels} />);

    expect(screen.getByRole("heading", { name: "Iniciar sesión" })).toBeDefined();
    expect(screen.getByPlaceholderText(mockLabels.usernamePlaceholder)).toBeDefined();
    expect(screen.getByPlaceholderText(mockLabels.passwordPlaceholder)).toBeDefined();
    expect(screen.getByRole("button", { name: "Ingresar" })).toBeDefined();
    expect(screen.getByText(mockLabels.infoHint)).toBeDefined();
  });

  it("alterna la visibilidad de la contraseña con el botón toggle", () => {
    render(<LoginContent labels={mockLabels} />);
    const passwordInput = screen.getByPlaceholderText(mockLabels.passwordPlaceholder) as HTMLInputElement;
    const toggleButton = screen.getByTitle("Mostrar contraseña");

    expect(passwordInput.type).toBe("password");

    fireEvent.click(toggleButton);
    expect(passwordInput.type).toBe("text");

    fireEvent.click(toggleButton);
    expect(passwordInput.type).toBe("password");
  });

  it("muestra error si las credenciales son incorrectas", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      status: 400,
      json: async () => ({ detail: "invalid_credentials" }),
    });
    global.fetch = fetchMock;

    render(<LoginContent labels={mockLabels} />);
    
    fireEvent.change(screen.getByPlaceholderText(mockLabels.usernamePlaceholder), { target: { value: "lucia" } });
    fireEvent.change(screen.getByPlaceholderText(mockLabels.passwordPlaceholder), { target: { value: "wrongpass" } });
    fireEvent.click(screen.getByRole("button", { name: "Ingresar" }));

    await waitFor(() => {
      expect(screen.getByText("Usuario o contraseña incorrectos.")).toBeDefined();
    });
  });

  it("muestra error si la cuenta está bloqueada", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      status: 400,
      json: async () => ({ detail: "ACCOUNT_LOCKED" }),
    });
    global.fetch = fetchMock;

    render(<LoginContent labels={mockLabels} />);

    const usernameInput = document.querySelector('input[autocomplete="username"]') as HTMLInputElement;
    const passwordInput = document.querySelector('input[autocomplete="current-password"]') as HTMLInputElement;
    const submitButton = screen.getByRole("button", { name: "Ingresar" });

    fireEvent.change(usernameInput, { target: { value: "lucia" } });
    fireEvent.change(passwordInput, { target: { value: "somepass" } });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/Demasiados intentos fallidos/)).toBeDefined();
      const uInput = document.querySelector('input[autocomplete="username"]') as HTMLInputElement;
      const pInput = document.querySelector('input[autocomplete="current-password"]') as HTMLInputElement;
      expect(uInput?.disabled).toBe(true);
      expect(pInput?.disabled).toBe(true);
    });
  });

  it("pasa al paso 2 si el backend retorna pending_totp", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => ({
        status: "pending_totp",
        pending_token: "mock-token",
      }),
    });
    global.fetch = fetchMock;

    render(<LoginContent labels={mockLabels} />);

    fireEvent.change(screen.getByPlaceholderText(mockLabels.usernamePlaceholder), { target: { value: "lucia" } });
    fireEvent.change(screen.getByPlaceholderText(mockLabels.passwordPlaceholder), { target: { value: "correctpass" } });
    fireEvent.click(screen.getByRole("button", { name: "Ingresar" }));

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Verificación en dos pasos" })).toBeDefined();
      expect(screen.getByPlaceholderText(mockLabels.totpPlaceholder)).toBeDefined();
      expect(screen.getByRole("button", { name: "Volver" })).toBeDefined();
    });

    // Probar el botón Volver
    fireEvent.click(screen.getByRole("button", { name: "Volver" }));
    expect(screen.getByRole("heading", { name: "Iniciar sesión" })).toBeDefined();
  });

  it("llama al flujo de redirección al ingresar totp exitoso", async () => {
    const onLoginSuccess = vi.fn();

    // Mock para login exitoso (devuelve pending_totp)
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({
        status: 200,
        ok: true,
        json: async () => ({
          status: "pending_totp",
          pending_token: "mock-token",
        }),
      })
      .mockResolvedValueOnce({
        status: 200,
        ok: true,
        json: async () => ({
          status: "success",
        }),
      });

    global.fetch = fetchMock;

    render(<LoginContent labels={mockLabels} onLoginSuccess={onLoginSuccess} />);

    fireEvent.change(screen.getByPlaceholderText(mockLabels.usernamePlaceholder), { target: { value: "lucia" } });
    fireEvent.change(screen.getByPlaceholderText(mockLabels.passwordPlaceholder), { target: { value: "correctpass" } });
    fireEvent.click(screen.getByRole("button", { name: "Ingresar" }));

    await waitFor(() => {
      expect(screen.getByPlaceholderText(mockLabels.totpPlaceholder)).toBeDefined();
    });

    fireEvent.change(screen.getByPlaceholderText(mockLabels.totpPlaceholder), { target: { value: "123456" } });
    fireEvent.click(screen.getByRole("button", { name: "Verificar" }));

    await waitFor(() => {
      expect(onLoginSuccess).toHaveBeenCalled();
    });
  });
});
