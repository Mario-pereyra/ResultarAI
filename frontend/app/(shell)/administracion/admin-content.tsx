"use client";

import { useState, useEffect, useTransition } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

export interface AdminContentProps {
  labels: {
    title: string;
    kicker: string;
    searchPlaceholder: string;
    filterRole: string;
    filterRoleAll: string;
    filterStatus: string;
    filterStatusAll: string;
    createUserBtn: string;
    createGroupBtn: string;
    userTable: {
      username: string;
      name: string;
      role: string;
      status: string;
      totp: string;
      actions: string;
    };
    actions: {
      changeRole: string;
      credentials: string;
      resetPassword: string;
      suspend: string;
      activate: string;
      requireTotp: string;
      optionalTotp: string;
      revokeSessions: string;
      revokeAll: string;
      revokeCurrent: string;
    };
    status: {
      active: string;
      suspended: string;
      totpYes: string;
      totpNo: string;
      totpPending: string;
    };
    roles: {
      admin: string;
      tecnico: string;
      funcional: string;
    };
    createUserModal: {
      title: string;
      username: string;
      displayName: string;
      email: string;
      role: string;
      group: string;
      requireTotp: string;
      requireTotpHintAdmin: string;
      submit: string;
      successTitle: string;
      successDesc: string;
      tempPassword: string;
      copyBtn: string;
      copied: string;
      close: string;
    };
    createGroupModal: {
      title: string;
      name: string;
      description: string;
      members: string;
      addMembers: string;
      noMembers: string;
      submit: string;
    };
    resetPasswordModal: {
      title: string;
      desc: string;
      successTitle: string;
      successDesc: string;
      submit: string;
      close: string;
    };
    suspendModal: {
      title: string;
      desc: string;
      confirmText: string;
      submit: string;
    };
  };
}

interface UserData {
  id: string;
  username: string;
  display_name: string;
  email: string;
  role: string;
  status: string;
  totp_required: boolean;
}

interface GroupData {
  id: string;
  name: string;
  description: string;
  member_ids: string[];
}

export function AdminContent({ labels }: AdminContentProps) {
  const [activeTab, setActiveTab] = useState<"usuarios" | "grupos">("usuarios");
  const [users, setUsers] = useState<UserData[]>([]);
  const [groups, setGroups] = useState<GroupData[]>([]);
  const [loading, setLoading] = useState(true);
  const [isPending, startTransition] = useTransition();
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Filtros
  const [searchQuery, setSearchQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");

  // Modales
  const [showCreateUser, setShowCreateUser] = useState(false);
  const [showCreateUserSuccess, setShowCreateUserSuccess] = useState(false);
  const [createdUserTempPassword, setCreatedUserTempPassword] = useState("");

  const [showCreateGroup, setShowCreateGroup] = useState(false);

  const [showResetPassword, setShowResetPassword] = useState(false);
  const [showResetPasswordSuccess, setShowResetPasswordSuccess] = useState(false);
  const [resetTargetUser, setResetTargetUser] = useState<UserData | null>(null);
  const [resetTempPassword, setResetTempPassword] = useState("");

  const [showSuspend, setShowSuspend] = useState(false);
  const [suspendTargetUser, setSuspendTargetUser] = useState<UserData | null>(null);
  const [suspendConfirmText, setSuspendConfirmText] = useState("");

  // Formularios
  // Crear usuario
  const [newUsername, setNewUsername] = useState("");
  const [newDisplayName, setNewDisplayName] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [newRole, setNewRole] = useState("funcional");
  const [newGroupId, setNewGroupId] = useState("");

  // Crear grupo
  const [newGroupName, setNewGroupName] = useState("");
  const [newGroupDesc, setNewGroupDesc] = useState("");
  const [selectedMembers, setSelectedMembers] = useState<string[]>([]);

  // Clipboard copies
  const [copiedText, setCopiedText] = useState(false);

  // Cargar datos
  async function loadData() {
    try {
      const usersRes = await fetch("/api/admin/users");
      const groupsRes = await fetch("/api/admin/groups");
      if (!usersRes.ok || !groupsRes.ok) throw new Error();
      const usersData = await usersRes.json();
      const groupsData = await groupsRes.json();

      setUsers(usersData);
      setGroups(groupsData);
    } catch (err) {
      setErrorMsg("Error al obtener los datos de administración.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  // Crear Usuario submit
  async function handleCreateUserSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!newUsername || !newDisplayName || !newEmail) return;

    setErrorMsg(null);
    startTransition(async () => {
      try {
        const res = await fetch("/api/admin/users", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username: newUsername,
            display_name: newDisplayName,
            email: newEmail,
            role: newRole,
            group_id: newGroupId || null,
          }),
        });

        if (!res.ok) {
          const data = await res.json();
          setErrorMsg(data.detail || "Error al crear el usuario.");
          return;
        }

        const data = await res.json();
        setCreatedUserTempPassword(data.temp_password);
        setShowCreateUser(false);
        setShowCreateUserSuccess(true);
        setNewUsername("");
        setNewDisplayName("");
        setNewEmail("");
        setNewRole("funcional");
        setNewGroupId("");
        await loadData();
      } catch (err) {
        setErrorMsg("Error de red al crear el usuario.");
      }
    });
  }

  // Crear Grupo submit
  async function handleCreateGroupSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!newGroupName) return;

    setErrorMsg(null);
    startTransition(async () => {
      try {
        const res = await fetch("/api/admin/groups", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: newGroupName,
            description: newGroupDesc,
          }),
        });

        if (!res.ok) {
          const data = await res.json();
          setErrorMsg(data.detail || "Error al crear el grupo.");
          return;
        }

        const data = await res.json();
        const groupId = data.group_id;

        // Agregar miembros elegidos
        for (const userId of selectedMembers) {
          await fetch(`/api/admin/groups/${groupId}/members`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ user_id: userId }),
          });
        }

        setShowCreateGroup(false);
        setNewGroupName("");
        setNewGroupDesc("");
        setSelectedMembers([]);
        await loadData();
      } catch (err) {
        setErrorMsg("Error al crear el grupo o agregar los miembros.");
      }
    });
  }

  // Acciones de Usuario
  async function toggleTotp(user: UserData) {
    setErrorMsg(null);
    try {
      const res = await fetch(`/api/admin/users/${user.id}/require-totp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ require: !user.totp_required }),
      });
      if (!res.ok) throw new Error();
      await loadData();
    } catch (err) {
      setErrorMsg("Error al alternar requerimiento TOTP.");
    }
  }

  async function revokeAllSessions(user: UserData) {
    setErrorMsg(null);
    try {
      const res = await fetch(`/api/admin/users/${user.id}/sessions/revoke`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: null }),
      });
      if (!res.ok) throw new Error();
      await loadData();
    } catch (err) {
      setErrorMsg("Error al revocar las sesiones del usuario.");
    }
  }

  async function handleResetPasswordSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!resetTargetUser) return;

    setErrorMsg(null);
    startTransition(async () => {
      try {
        const res = await fetch(`/api/admin/users/${resetTargetUser.id}/reset-password`, {
          method: "POST",
        });
        if (!res.ok) throw new Error();
        const data = await res.json();
        setResetTempPassword(data.temp_password);
        setShowResetPassword(false);
        setShowResetPasswordSuccess(true);
      } catch (err) {
        setErrorMsg("Error al restablecer la contraseña.");
      }
    });
  }

  async function handleSuspendSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!suspendTargetUser || suspendConfirmText !== suspendTargetUser.username) return;

    setErrorMsg(null);
    startTransition(async () => {
      try {
        const res = await fetch(`/api/admin/users/${suspendTargetUser.id}/suspend`, {
          method: "POST",
        });
        if (!res.ok) throw new Error();
        setShowSuspend(false);
        setSuspendConfirmText("");
        setSuspendTargetUser(null);
        await loadData();
      } catch (err) {
        setErrorMsg("Error al suspender al usuario.");
      }
    });
  }

  // Quitar miembro de un grupo
  async function removeMember(groupId: string, userId: string) {
    try {
      const res = await fetch(`/api/admin/groups/${groupId}/members/${userId}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error();
      await loadData();
    } catch (err) {
      setErrorMsg("Error al quitar miembro del grupo.");
    }
  }

  // Filtrado de usuarios
  const filteredUsers = users.filter((u) => {
    const query = searchQuery.toLowerCase();
    const matchQuery = u.username.toLowerCase().includes(query) || u.display_name.toLowerCase().includes(query);
    const matchRole = roleFilter === "all" || u.role === roleFilter;
    const matchStatus = statusFilter === "all" || u.status === statusFilter;
    return matchQuery && matchRole && matchStatus;
  });

  if (loading) {
    return (
      <div style={{ padding: "var(--sp-6)" }}>
        <div className="skeleton" style={{ width: "200px", height: "30px", marginBottom: "20px" }}></div>
        <div className="skeleton" style={{ width: "100%", height: "200px" }}></div>
      </div>
    );
  }

  return (
    <div style={{ padding: "var(--sp-6)", maxWidth: "1200px", margin: "0 auto" }}>
      
      {/* Cabecera */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--sp-6)" }}>
        <div>
          <span className="kicker" style={{ fontSize: "var(--fs-small)", textTransform: "uppercase" }}>{labels.kicker}</span>
          <h1 style={{ fontSize: "var(--fs-h2)", fontWeight: 800, margin: 0 }}>{labels.title}</h1>
        </div>
        <div style={{ display: "flex", gap: "var(--sp-2)" }}>
          <Button variant="secondary" onClick={() => setShowCreateGroup(true)}>
            {labels.createGroupBtn}
          </Button>
          <Button variant="primary" onClick={() => setShowCreateUser(true)}>
            {labels.createUserBtn}
          </Button>
        </div>
      </div>

      {/* Alertas */}
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

      {/* Tabs */}
      <div style={{ display: "flex", gap: "var(--sp-4)", borderBottom: "1px solid var(--border-subtle)", marginBottom: "var(--sp-6)" }}>
        <button
          onClick={() => setActiveTab("usuarios")}
          style={{
            padding: "var(--sp-2) var(--sp-4)",
            fontWeight: activeTab === "usuarios" ? "bold" : "normal",
            borderBottom: activeTab === "usuarios" ? "2px solid var(--accent)" : "none",
            background: "none",
            border: "none",
            cursor: "pointer",
            color: activeTab === "usuarios" ? "var(--accent)" : "var(--ink-dim)"
          }}
        >
          Usuarios
        </button>
        <button
          onClick={() => setActiveTab("grupos")}
          style={{
            padding: "var(--sp-2) var(--sp-4)",
            fontWeight: activeTab === "grupos" ? "bold" : "normal",
            borderBottom: activeTab === "grupos" ? "2px solid var(--accent)" : "none",
            background: "none",
            border: "none",
            cursor: "pointer",
            color: activeTab === "grupos" ? "var(--accent)" : "var(--ink-dim)"
          }}
        >
          Grupos
        </button>
      </div>

      {/* TAB USUARIOS */}
      {activeTab === "usuarios" && (
        <div className="panel" style={{ padding: "var(--sp-4)" }}>
          
          {/* Barra de Filtros */}
          <div style={{ display: "flex", gap: "var(--sp-4)", marginBottom: "var(--sp-4)", flexWrap: "wrap" }}>
            <div style={{ flex: 1, minWidth: "250px" }}>
              <input
                className="input"
                type="text"
                placeholder={labels.searchPlaceholder}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
            
            <div style={{ width: "150px" }}>
              <select className="select" value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)}>
                <option value="all">{labels.filterRoleAll}</option>
                <option value="admin">{labels.roles.admin}</option>
                <option value="tecnico">{labels.roles.tecnico}</option>
                <option value="funcional">{labels.roles.funcional}</option>
              </select>
            </div>

            <div style={{ width: "150px" }}>
              <select className="select" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                <option value="all">{labels.filterStatusAll}</option>
                <option value="active">{labels.status.active}</option>
                <option value="suspended">{labels.status.suspended}</option>
              </select>
            </div>
          </div>

          {/* Tabla */}
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>{labels.userTable.username}</th>
                  <th>{labels.userTable.name}</th>
                  <th>{labels.userTable.role}</th>
                  <th>{labels.userTable.status}</th>
                  <th>{labels.userTable.totp}</th>
                  <th style={{ textAlign: "right" }}>{labels.userTable.actions}</th>
                </tr>
              </thead>
              <tbody>
                {filteredUsers.map((u) => (
                  <tr key={u.id}>
                    <td className="mono" style={{ fontWeight: 600 }}>{u.username}</td>
                    <td>{u.display_name}</td>
                    <td>
                      <span className={`tag ${u.role === "admin" ? "tag--danger" : u.role === "tecnico" ? "tag--info" : "tag--outline"}`}>
                        {u.role}
                      </span>
                    </td>
                    <td>
                      <span className={`tag ${u.status === "active" ? "tag--success" : "tag--danger"}`} style={{ background: u.status === "active" ? "var(--money)" : "var(--danger)" }}>
                        {u.status === "active" ? labels.status.active : labels.status.suspended}
                      </span>
                    </td>
                    <td>
                      <span style={{ color: u.totp_required ? "var(--money)" : "var(--ink-dim)", fontWeight: "bold" }}>
                        {u.totp_required ? labels.status.totpYes : labels.status.totpNo}
                      </span>
                    </td>
                    <td style={{ textAlign: "right" }}>
                      <div style={{ display: "inline-flex", gap: "var(--sp-1)" }}>
                        {/* Exigir/Opcional TOTP */}
                        {u.role !== "admin" && (
                          <button
                            title={u.totp_required ? labels.actions.optionalTotp : labels.actions.requireTotp}
                            onClick={() => toggleTotp(u)}
                            className="btn btn--ghost btn--sm"
                          >
                            🛡️
                          </button>
                        )}
                        {/* Revocar Sesiones */}
                        <button
                          title={labels.actions.revokeSessions}
                          onClick={() => revokeAllSessions(u)}
                          className="btn btn--ghost btn--sm"
                        >
                          🚫
                        </button>
                        {/* Reset Password */}
                        <button
                          title={labels.actions.resetPassword}
                          onClick={() => {
                            setResetTargetUser(u);
                            setShowResetPassword(true);
                          }}
                          className="btn btn--ghost btn--sm"
                        >
                          🔑
                        </button>
                        {/* Suspender */}
                        {u.status === "active" && (
                          <button
                            title={labels.actions.suspend}
                            onClick={() => {
                              setSuspendTargetUser(u);
                              setShowSuspend(true);
                            }}
                            className="btn btn--ghost btn--sm"
                            style={{ color: "var(--danger)" }}
                          >
                            🛑
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

        </div>
      )}

      {/* TAB GRUPOS */}
      {activeTab === "grupos" && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: "var(--sp-4)" }}>
          {groups.map((g) => (
            <div key={g.id} className="panel" style={{ padding: "var(--sp-4)", display: "flex", flexDirection: "column", gap: "var(--sp-2)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h3 style={{ margin: 0, fontSize: "var(--fs-h4)", fontWeight: 700 }}>{g.name}</h3>
                <span className="tag">{g.member_ids.length} miembros</span>
              </div>
              <p style={{ fontSize: "var(--fs-small)", color: "var(--ink-dim)", margin: 0, flexGrow: 1 }}>
                {g.description || "Sin descripción"}
              </p>

              {/* Lista de Miembros en el grupo */}
              <div style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: "var(--sp-2)", marginTop: "var(--sp-2)" }}>
                <span style={{ fontSize: "var(--fs-xsmall)", fontWeight: 600, color: "var(--ink-dim)", display: "block", marginBottom: "4px" }}>
                  MIEMBROS
                </span>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "4px" }}>
                  {g.member_ids.map((memberId) => {
                    const memberUser = users.find((u) => u.id === memberId);
                    return (
                      <span key={memberId} className="tag tag--outline" style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}>
                        {memberUser?.username || memberId}
                        <button
                          type="button"
                          onClick={() => removeMember(g.id, memberId)}
                          style={{ border: "none", background: "none", cursor: "pointer", padding: 0, color: "var(--danger)" }}
                          title="Quitar"
                        >
                          ×
                        </button>
                      </span>
                    );
                  })}
                  {g.member_ids.length === 0 && (
                    <span style={{ fontSize: "var(--fs-small)", color: "var(--ink-faint)" }}>
                      {labels.createGroupModal.noMembers}
                    </span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* MODALES */}

      {/* Modal: Crear Usuario */}
      {showCreateUser && (
        <div style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100 }}>
          <div className="panel" style={{ width: "100%", maxWidth: "450px", padding: "var(--sp-6)", background: "var(--panel)", borderRadius: "var(--r-lg)" }}>
            <h2 style={{ fontSize: "var(--fs-h4)", fontWeight: 700, marginBottom: "var(--sp-4)" }}>{labels.createUserModal.title}</h2>
            <form onSubmit={handleCreateUserSubmit} noValidate>
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--sp-4)" }}>
                <Input
                  label={labels.createUserModal.username}
                  value={newUsername}
                  onChange={(e) => setNewUsername(e.target.value)}
                  required
                />
                <Input
                  label={labels.createUserModal.displayName}
                  value={newDisplayName}
                  onChange={(e) => setNewDisplayName(e.target.value)}
                  required
                />
                <Input
                  label={labels.createUserModal.email}
                  type="email"
                  value={newEmail}
                  onChange={(e) => setNewEmail(e.target.value)}
                  required
                />
                <div>
                  <label className="field-label">{labels.createUserModal.role}</label>
                  <select className="select" value={newRole} onChange={(e) => setNewRole(e.target.value)}>
                    <option value="funcional">{labels.roles.funcional}</option>
                    <option value="tecnico">{labels.roles.tecnico}</option>
                    <option value="admin">{labels.roles.admin}</option>
                  </select>
                </div>
                <div>
                  <label className="field-label">{labels.createUserModal.group}</label>
                  <select className="select" value={newGroupId} onChange={(e) => setNewGroupId(e.target.value)}>
                    <option value="">Ninguno</option>
                    {groups.map((g) => (
                      <option key={g.id} value={g.id}>{g.name}</option>
                    ))}
                  </select>
                </div>

                <div style={{ display: "flex", gap: "var(--sp-2)", justifyContent: "flex-end", marginTop: "var(--sp-2)" }}>
                  <Button type="button" variant="ghost" onClick={() => setShowCreateUser(false)}>
                    Cancelar
                  </Button>
                  <Button type="submit" variant="primary" disabled={isPending || !newUsername || !newDisplayName || !newEmail} loading={isPending}>
                    {labels.createUserModal.submit}
                  </Button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Crear Usuario Exitoso (Contraseña Temporal) */}
      {showCreateUserSuccess && (
        <div style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100 }}>
          <div className="panel" style={{ width: "100%", maxWidth: "450px", padding: "var(--sp-6)", background: "var(--panel)", borderRadius: "var(--r-lg)", border: "2px solid var(--money)" }}>
            <h2 style={{ fontSize: "var(--fs-h4)", fontWeight: 700, color: "var(--money)", marginBottom: "var(--sp-2)" }}>
              ✓ {labels.createUserModal.successTitle}
            </h2>
            <p style={{ fontSize: "var(--fs-small)", color: "var(--ink-dim)", marginBottom: "var(--sp-4)" }}>
              {labels.createUserModal.successDesc}
            </p>

            <div style={{ display: "flex", flexDirection: "column", gap: "var(--sp-4)" }}>
              <div>
                <label className="field-label">{labels.createUserModal.tempPassword}</label>
                <div style={{ display: "flex", gap: "var(--sp-2)" }}>
                  <code className="mono" style={{ background: "var(--bg-subtle)", padding: "var(--sp-2) var(--sp-3)", borderRadius: "var(--r-sm)", border: "1px solid var(--border-subtle)", flexGrow: 1 }}>
                    {createdUserTempPassword}
                  </code>
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => {
                      navigator.clipboard.writeText(createdUserTempPassword);
                      setCopiedText(true);
                      setTimeout(() => setCopiedText(false), 2000);
                    }}
                  >
                    {copiedText ? labels.createUserModal.copied : labels.createUserModal.copyBtn}
                  </Button>
                </div>
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end" }}>
                <Button type="button" variant="primary" onClick={() => setShowCreateUserSuccess(false)}>
                  {labels.createUserModal.close}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Crear Grupo */}
      {showCreateGroup && (
        <div style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100 }}>
          <div className="panel" style={{ width: "100%", maxWidth: "450px", padding: "var(--sp-6)", background: "var(--panel)", borderRadius: "var(--r-lg)" }}>
            <h2 style={{ fontSize: "var(--fs-h4)", fontWeight: 700, marginBottom: "var(--sp-4)" }}>{labels.createGroupModal.title}</h2>
            <form onSubmit={handleCreateGroupSubmit} noValidate>
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--sp-4)" }}>
                <Input
                  label={labels.createGroupModal.name}
                  value={newGroupName}
                  onChange={(e) => setNewGroupName(e.target.value)}
                  required
                />
                <div>
                  <label className="field-label">{labels.createGroupModal.description}</label>
                  <textarea
                    className="textarea"
                    value={newGroupDesc}
                    onChange={(e) => setNewGroupDesc(e.target.value)}
                    style={{ width: "100%", height: "80px" }}
                  />
                </div>

                {/* Seleccionar miembros */}
                <div>
                  <label className="field-label">{labels.createGroupModal.members}</label>
                  <div style={{ maxHeight: "150px", overflowY: "auto", border: "1px solid var(--border-subtle)", padding: "var(--sp-2)", borderRadius: "var(--r-sm)" }}>
                    {users.map((u) => (
                      <div key={u.id} className="check-row" style={{ display: "flex", gap: "var(--sp-2)", marginBottom: "4px" }}>
                        <input
                          type="checkbox"
                          id={`member-${u.id}`}
                          className="checkbox"
                          checked={selectedMembers.includes(u.id)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedMembers([...selectedMembers, u.id]);
                            } else {
                              setSelectedMembers(selectedMembers.filter((id) => id !== u.id));
                            }
                          }}
                        />
                        <label htmlFor={`member-${u.id}`} style={{ fontSize: "var(--fs-small)", cursor: "pointer" }}>
                          {u.username} ({u.display_name})
                        </label>
                      </div>
                    ))}
                  </div>
                </div>

                <div style={{ display: "flex", gap: "var(--sp-2)", justifyContent: "flex-end", marginTop: "var(--sp-2)" }}>
                  <Button type="button" variant="ghost" onClick={() => setShowCreateGroup(false)}>
                    Cancelar
                  </Button>
                  <Button type="submit" variant="primary" disabled={isPending || !newGroupName} loading={isPending}>
                    {labels.createGroupModal.submit}
                  </Button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Restablecer Contraseña Confirmación */}
      {showResetPassword && resetTargetUser && (
        <div style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100 }}>
          <div className="panel" style={{ width: "100%", maxWidth: "450px", padding: "var(--sp-6)", background: "var(--panel)", borderRadius: "var(--r-lg)" }}>
            <h2 style={{ fontSize: "var(--fs-h4)", fontWeight: 700, marginBottom: "var(--sp-2)" }}>{labels.resetPasswordModal.title}</h2>
            <p style={{ fontSize: "var(--fs-small)", color: "var(--ink-dim)", marginBottom: "var(--sp-4)" }}>
              {labels.resetPasswordModal.desc.replace("{username}", resetTargetUser.username)}
            </p>
            <form onSubmit={handleResetPasswordSubmit}>
              <div style={{ display: "flex", gap: "var(--sp-2)", justifyContent: "flex-end" }}>
                <Button type="button" variant="ghost" onClick={() => {
                  setShowResetPassword(false);
                  setResetTargetUser(null);
                }}>
                  Cancelar
                </Button>
                <Button type="submit" variant="danger" disabled={isPending} loading={isPending}>
                  {labels.resetPasswordModal.submit}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Restablecer Contraseña Éxito (Muestra Contraseña una vez) */}
      {showResetPasswordSuccess && (
        <div style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100 }}>
          <div className="panel" style={{ width: "100%", maxWidth: "450px", padding: "var(--sp-6)", background: "var(--panel)", borderRadius: "var(--r-lg)", border: "2px solid var(--warn)" }}>
            <h2 style={{ fontSize: "var(--fs-h4)", fontWeight: 700, color: "var(--warn)", marginBottom: "var(--sp-2)" }}>
              {labels.resetPasswordModal.successTitle}
            </h2>
            <p style={{ fontSize: "var(--fs-small)", color: "var(--ink-dim)", marginBottom: "var(--sp-4)" }}>
              {labels.resetPasswordModal.successDesc}
            </p>

            <div style={{ display: "flex", flexDirection: "column", gap: "var(--sp-4)" }}>
              <div>
                <div style={{ display: "flex", gap: "var(--sp-2)" }}>
                  <code className="mono" style={{ background: "var(--bg-subtle)", padding: "var(--sp-2) var(--sp-3)", borderRadius: "var(--r-sm)", border: "1px solid var(--border-subtle)", flexGrow: 1 }}>
                    {resetTempPassword}
                  </code>
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => {
                      navigator.clipboard.writeText(resetTempPassword);
                      setCopiedText(true);
                      setTimeout(() => setCopiedText(false), 2000);
                    }}
                  >
                    {copiedText ? labels.createUserModal.copied : labels.createUserModal.copyBtn}
                  </Button>
                </div>
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end" }}>
                <Button type="button" variant="primary" onClick={() => {
                  setShowResetPasswordSuccess(false);
                  setResetTempPassword("");
                  setResetTargetUser(null);
                }}>
                  {labels.resetPasswordModal.close}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Suspender Usuario (Confirmación por Escritura) */}
      {showSuspend && suspendTargetUser && (
        <div style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100 }}>
          <div className="panel" style={{ width: "100%", maxWidth: "450px", padding: "var(--sp-6)", background: "var(--panel)", borderRadius: "var(--r-lg)" }}>
            <h2 style={{ fontSize: "var(--fs-h4)", fontWeight: 700, color: "var(--danger)", marginBottom: "var(--sp-2)" }}>
              {labels.suspendModal.title}
            </h2>
            <p style={{ fontSize: "var(--fs-small)", color: "var(--ink-dim)", marginBottom: "var(--sp-4)" }}>
              {labels.suspendModal.desc.replace("{username}", suspendTargetUser.username)}
            </p>

            <form onSubmit={handleSuspendSubmit} noValidate>
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--sp-4)" }}>
                <Input
                  label={labels.suspendModal.confirmText.replace("{username}", suspendTargetUser.username)}
                  placeholder={suspendTargetUser.username}
                  value={suspendConfirmText}
                  onChange={(e) => setSuspendConfirmText(e.target.value)}
                  required
                />

                <div style={{ display: "flex", gap: "var(--sp-2)", justifyContent: "flex-end", marginTop: "var(--sp-2)" }}>
                  <Button type="button" variant="ghost" onClick={() => {
                    setShowSuspend(false);
                    setSuspendTargetUser(null);
                    setSuspendConfirmText("");
                  }}>
                    Cancelar
                  </Button>
                  <Button type="submit" variant="danger" disabled={isPending || suspendConfirmText !== suspendTargetUser.username} loading={isPending}>
                    {labels.suspendModal.submit}
                  </Button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
}
