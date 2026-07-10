import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { AdminContent } from "./admin-content";

const mockLabels = {
  title: "Administración",
  kicker: "Consola admin",
  searchPlaceholder: "Buscar username o nombre...",
  filterRole: "Rol",
  filterRoleAll: "Todos los roles",
  filterStatus: "Estado",
  filterStatusAll: "Todos los estados",
  createUserBtn: "Crear usuario",
  createGroupBtn: "Crear grupo",
  userTable: {
    username: "USERNAME",
    name: "NOMBRE",
    role: "ROL",
    status: "ESTADO",
    totp: "TOTP",
    actions: "ACCIONES"
  },
  actions: {
    changeRole: "Editar rol",
    credentials: "Credenciales",
    resetPassword: "Restablecer contraseña",
    suspend: "Suspender",
    activate: "Activar",
    requireTotp: "Exigir TOTP",
    optionalTotp: "TOTP opcional",
    revokeSessions: "Revocar sesiones",
    revokeAll: "Revocar todas",
    revokeCurrent: "Revocar actual"
  },
  status: {
    active: "ACTIVO",
    suspended: "SUSPENDIDO",
    totpYes: "SÍ",
    totpNo: "NO",
    totpPending: "PENDIENTE"
  },
  roles: {
    admin: "Admin",
    tecnico: "Técnico",
    funcional: "Funcional"
  },
  createUserModal: {
    title: "Crear usuario",
    username: "Username",
    displayName: "Nombre para mostrar",
    email: "Correo electrónico",
    role: "Rol",
    group: "Grupo",
    requireTotp: "Requerir TOTP en el primer acceso",
    requireTotpHintAdmin: "Obligatorio para Admin",
    submit: "Crear usuario",
    successTitle: "Usuario creado con éxito",
    successDesc: "Copiá la contraseña temporal. Se muestra una sola vez.",
    tempPassword: "Contraseña temporal",
    copyBtn: "Copiar",
    copied: "¡Copiado!",
    close: "Cerrar"
  },
  createGroupModal: {
    title: "Crear grupo",
    name: "Nombre del grupo",
    description: "Descripción",
    members: "Miembros del grupo",
    addMembers: "Agregar miembros",
    noMembers: "No hay miembros en el grupo.",
    submit: "Crear grupo"
  },
  resetPasswordModal: {
    title: "Restablecer contraseña",
    desc: "Vas a restablecer la contraseña para {username}. Se generará una contraseña temporal.",
    successTitle: "Contraseña restablecida",
    successDesc: "Copiá la contraseña temporal generada.",
    submit: "Restablecer",
    close: "Cerrar"
  },
  suspendModal: {
    title: "Suspender usuario",
    desc: "Vas a suspender la cuenta de {username}.",
    confirmText: "Escribí {username} para confirmar",
    submit: "Suspender usuario"
  }
};

const mockUsers = [
  {
    id: "uuid-marcos",
    username: "marcos",
    display_name: "Marcos Admin",
    email: "marcos@resultar.bo",
    role: "admin",
    status: "active",
    totp_required: true
  },
  {
    id: "uuid-lucia",
    username: "lucia",
    display_name: "Lucía Funcional",
    email: "lucia@resultar.bo",
    role: "funcional",
    status: "active",
    totp_required: false
  },
  {
    id: "uuid-dario",
    username: "dario",
    display_name: "Darío Técnico",
    email: "dario@resultar.bo",
    role: "tecnico",
    status: "suspended",
    totp_required: false
  }
];

const mockGroups = [
  {
    id: "uuid-grupo-a",
    name: "Grupo Operaciones",
    description: "Grupo para el personal de operaciones.",
    member_ids: ["uuid-lucia"]
  }
];

describe("AdminContent", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    global.fetch = vi.fn();
    // Clipboard mock
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn(),
      },
    });
  });

  it("renderiza la lista de usuarios y grupos con sus respectivos estados y tabs", async () => {
    global.fetch = vi.fn().mockImplementation(async (url: string) => {
      if (url.includes("/api/admin/users")) {
        return { status: 200, ok: true, json: async () => mockUsers };
      }
      if (url.includes("/api/admin/groups")) {
        return { status: 200, ok: true, json: async () => mockGroups };
      }
      return { status: 404, ok: false, json: async () => ({}) };
    });

    render(<AdminContent labels={mockLabels} />);

    await waitFor(() => {
      expect(screen.getByText("marcos")).toBeDefined();
      expect(screen.getByText("lucia")).toBeDefined();
      expect(screen.getByText("dario")).toBeDefined();
    });

    // Validar estados
    expect(screen.getByText("Marcos Admin")).toBeDefined();
    expect(screen.getByText("Darío Técnico")).toBeDefined();
    
    // Cambiar a pestaña Grupos
    const groupTab = screen.getByRole("button", { name: "Grupos" });
    fireEvent.click(groupTab);

    await waitFor(() => {
      expect(screen.getByText("Grupo Operaciones")).toBeDefined();
      expect(screen.getByText("1 miembros")).toBeDefined();
    });
  });

  it("filtra usuarios por búsqueda de texto y selectores de rol y estado", async () => {
    global.fetch = vi.fn().mockImplementation(async (url: string) => {
      if (url.includes("/api/admin/users")) {
        return { status: 200, ok: true, json: async () => mockUsers };
      }
      if (url.includes("/api/admin/groups")) {
        return { status: 200, ok: true, json: async () => mockGroups };
      }
      return { status: 404, ok: false, json: async () => ({}) };
    });

    render(<AdminContent labels={mockLabels} />);

    await waitFor(() => {
      expect(screen.getByText("lucia")).toBeDefined();
    });

    // Búsqueda de texto
    const searchInput = screen.getByPlaceholderText(mockLabels.searchPlaceholder);
    fireEvent.change(searchInput, { target: { value: "dar" } });

    expect(screen.queryByText("lucia")).toBeNull();
    expect(screen.getByText("dario")).toBeDefined();

    // Limpiar búsqueda
    fireEvent.change(searchInput, { target: { value: "" } });

    // Filtrar por rol Técnico
    const roleSelect = screen.getAllByRole("combobox")[0];
    fireEvent.change(roleSelect, { target: { value: "tecnico" } });

    expect(screen.queryByText("lucia")).toBeNull();
    expect(screen.getByText("dario")).toBeDefined();
  });

  it("crea un nuevo usuario y muestra la contraseña temporal en el modal de éxito", async () => {
    const fetchMock = vi.fn().mockImplementation(async (url: string, options?: any) => {
      const isPost = options?.method === "POST" || options?.method === "post";
      if (url.includes("/api/admin/users") && url.endsWith("/users") && isPost) {
        return {
          status: 200,
          ok: true,
          json: async () => ({
            status: "success",
            user_id: "new-user-uuid",
            temp_password: "TEMP-PASSWORD-123"
          }),
        };
      }
      if (url.includes("/api/admin/users")) {
        return { status: 200, ok: true, json: async () => mockUsers };
      }
      if (url.includes("/api/admin/groups")) {
        return { status: 200, ok: true, json: async () => mockGroups };
      }
      return { status: 404, ok: false, json: async () => ({}) };
    });
    global.fetch = fetchMock;

    render(<AdminContent labels={mockLabels} />);

    await waitFor(() => {
      expect(screen.getByText("lucia")).toBeDefined();
    });

    // Abrir modal de creación
    fireEvent.click(screen.getByRole("button", { name: mockLabels.createUserBtn }));

    expect(screen.getByRole("heading", { name: mockLabels.createUserModal.title })).toBeDefined();

    // Llenar campos
    const usernameInput = screen.getByLabelText(mockLabels.createUserModal.username, { exact: false });
    const nameInput = screen.getByLabelText(mockLabels.createUserModal.displayName, { exact: false });
    const emailInput = screen.getByLabelText(mockLabels.createUserModal.email, { exact: false });

    fireEvent.change(usernameInput, { target: { value: "carmen" } });
    fireEvent.change(nameInput, { target: { value: "Carmen Rodríguez" } });
    fireEvent.change(emailInput, { target: { value: "carmen@resultar.bo" } });

    // Submit (segundo botón "Crear usuario", el primero está en la cabecera)
    const submitBtn = screen.getAllByRole("button", { name: mockLabels.createUserModal.submit })[1];
    fireEvent.click(submitBtn);

    // Debería ver el modal de éxito (con checkmark ✓ opcional)
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /Usuario creado con éxito/i })).toBeDefined();
      expect(screen.getByText("TEMP-PASSWORD-123")).toBeDefined();
    });

    // Copiar y cerrar
    const copyBtn = screen.getByRole("button", { name: mockLabels.createUserModal.copyBtn });
    fireEvent.click(copyBtn);
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith("TEMP-PASSWORD-123");

    fireEvent.click(screen.getByRole("button", { name: mockLabels.createUserModal.close }));
    expect(screen.queryByText("TEMP-PASSWORD-123")).toBeNull();
  });

  it("crea un grupo agregando miembros seleccionados", async () => {
    const fetchMock = vi.fn().mockImplementation(async (url: string, options?: any) => {
      const isPost = options?.method === "POST" || options?.method === "post";
      if (url.includes("/api/admin/groups") && url.endsWith("/groups") && isPost) {
        return {
          status: 200,
          ok: true,
          json: async () => ({
            status: "success",
            group_id: "new-group-uuid"
          }),
        };
      }
      if (url.includes("/members")) {
        return { status: 200, ok: true, json: async () => ({ status: "success" }) };
      }
      if (url.includes("/api/admin/users")) {
        return { status: 200, ok: true, json: async () => mockUsers };
      }
      if (url.includes("/api/admin/groups")) {
        return { status: 200, ok: true, json: async () => mockGroups };
      }
      return { status: 404, ok: false, json: async () => ({}) };
    });
    global.fetch = fetchMock;

    render(<AdminContent labels={mockLabels} />);

    await waitFor(() => {
      expect(screen.getByText("lucia")).toBeDefined();
    });

    fireEvent.click(screen.getByRole("button", { name: mockLabels.createGroupBtn }));

    const nameInput = screen.getByLabelText(mockLabels.createGroupModal.name, { exact: false });
    fireEvent.change(nameInput, { target: { value: "Grupo Desarrollo" } });

    // Seleccionar miembros por checkbox
    const checkboxes = screen.getAllByRole("checkbox");
    fireEvent.click(checkboxes[1]); // seleccionar lucia

    // Submit (segundo botón "Crear grupo", el primero está en la cabecera)
    const submitBtn = screen.getAllByRole("button", { name: mockLabels.createGroupModal.submit })[1];
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/api/admin/groups/new-group-uuid/members"), expect.any(Object));
    });
  });

  it("ejecuta acciones de usuario (totp, revocar, reset de contraseña)", async () => {
    const fetchMock = vi.fn().mockImplementation(async (url: string) => {
      if (url.includes("/require-totp")) {
        return { status: 200, ok: true, json: async () => ({ status: "success" }) };
      }
      if (url.includes("/sessions/revoke")) {
        return { status: 200, ok: true, json: async () => ({ status: "success" }) };
      }
      if (url.includes("/reset-password")) {
        return {
          status: 200,
          ok: true,
          json: async () => ({
            status: "success",
            temp_password: "RESET-TEMP-PASS"
          })
        };
      }
      if (url.includes("/api/admin/users")) {
        return { status: 200, ok: true, json: async () => mockUsers };
      }
      if (url.includes("/api/admin/groups")) {
        return { status: 200, ok: true, json: async () => mockGroups };
      }
      return { status: 404, ok: false, json: async () => ({}) };
    });
    global.fetch = fetchMock;

    render(<AdminContent labels={mockLabels} />);

    await waitFor(() => {
      expect(screen.getByText("lucia")).toBeDefined();
    });

    // 1. Requerir TOTP (lucia es el primer usuario no-admin activo)
    const totpBtn = screen.getAllByTitle(mockLabels.actions.requireTotp)[0];
    fireEvent.click(totpBtn);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/require-totp"), expect.any(Object));
    });

    // 2. Revocar Sesiones
    const revokeBtn = screen.getAllByTitle(mockLabels.actions.revokeSessions)[0];
    fireEvent.click(revokeBtn);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/sessions/revoke"), expect.any(Object));
    });

    // 3. Reset de Contraseña
    const resetBtn = screen.getAllByTitle(mockLabels.actions.resetPassword)[0];
    fireEvent.click(resetBtn);

    expect(screen.getByRole("heading", { name: mockLabels.resetPasswordModal.title })).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: mockLabels.resetPasswordModal.submit }));

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /Contraseña restablecida/i })).toBeDefined();
      expect(screen.getByText("RESET-TEMP-PASS")).toBeDefined();
    });
  });

  it("suspende a un usuario tras escribir su nombre exacto en el modal de confirmación", async () => {
    const fetchMock = vi.fn().mockImplementation(async (url: string) => {
      if (url.includes("/suspend")) {
        return { status: 200, ok: true, json: async () => ({ status: "success" }) };
      }
      if (url.includes("/api/admin/users")) {
        return { status: 200, ok: true, json: async () => mockUsers };
      }
      if (url.includes("/api/admin/groups")) {
        return { status: 200, ok: true, json: async () => mockGroups };
      }
      return { status: 404, ok: false, json: async () => ({}) };
    });
    global.fetch = fetchMock;

    render(<AdminContent labels={mockLabels} />);

    await waitFor(() => {
      expect(screen.getByText("lucia")).toBeDefined();
    });

    // Abrir modal de suspensión para marcos (primer usuario activo de la tabla)
    const suspendBtn = screen.getAllByTitle(mockLabels.actions.suspend)[0];
    fireEvent.click(suspendBtn);

    expect(screen.getByRole("heading", { name: mockLabels.suspendModal.title })).toBeDefined();

    const submitBtn = screen.getByRole("button", { name: mockLabels.suspendModal.submit });
    expect(submitBtn.hasAttribute("disabled")).toBe(true);

    // Escribir nombre incorrecto
    const confirmInput = screen.getByLabelText(/marcos/i, { exact: false });
    fireEvent.change(confirmInput, { target: { value: "incorrecto" } });
    expect(submitBtn.hasAttribute("disabled")).toBe(true);

    // Escribir nombre correcto
    fireEvent.change(confirmInput, { target: { value: "marcos" } });
    expect(submitBtn.hasAttribute("disabled")).toBe(false);

    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/suspend"), expect.any(Object));
    });
  });
});
