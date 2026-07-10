import { getTranslations } from "next-intl/server";
import { AdminContent } from "./admin-content";

export default async function AdministracionPage() {
  const t = await getTranslations("Administracion");

  const labels = {
    title: t("title"),
    kicker: t("kicker"),
    searchPlaceholder: t("searchPlaceholder"),
    filterRole: t("filterRole"),
    filterRoleAll: t("filterRoleAll"),
    filterStatus: t("filterStatus"),
    filterStatusAll: t("filterStatusAll"),
    createUserBtn: t("createUserBtn"),
    createGroupBtn: t("createGroupBtn"),
    tabUsers: t("tabUsers"),
    tabGroups: t("tabGroups"),
    cancel: t("cancel"),
    userTable: {
      username: t("userTable.username"),
      name: t("userTable.name"),
      role: t("userTable.role"),
      status: t("userTable.status"),
      totp: t("userTable.totp"),
      actions: t("userTable.actions"),
    },
    actions: {
      changeRole: t("actions.changeRole"),
      credentials: t("actions.credentials"),
      resetPassword: t("actions.resetPassword"),
      suspend: t("actions.suspend"),
      activate: t("actions.activate"),
      requireTotp: t("actions.requireTotp"),
      optionalTotp: t("actions.optionalTotp"),
      revokeSessions: t("actions.revokeSessions"),
      revokeAll: t("actions.revokeAll"),
      revokeCurrent: t("actions.revokeCurrent"),
    },
    status: {
      active: t("status.active"),
      suspended: t("status.suspended"),
      totpYes: t("status.totpYes"),
      totpNo: t("status.totpNo"),
      totpPending: t("status.totpPending"),
    },
    roles: {
      admin: t("roles.admin"),
      tecnico: t("roles.tecnico"),
      funcional: t("roles.funcional"),
    },
    createUserModal: {
      title: t("createUserModal.title"),
      username: t("createUserModal.username"),
      displayName: t("createUserModal.displayName"),
      email: t("createUserModal.email"),
      role: t("createUserModal.role"),
      group: t("createUserModal.group"),
      noGroup: t("createUserModal.noGroup"),
      requireTotp: t("createUserModal.requireTotp"),
      requireTotpHintAdmin: t("createUserModal.requireTotpHintAdmin"),
      submit: t("createUserModal.submit"),
      successTitle: t("createUserModal.successTitle"),
      successDesc: t("createUserModal.successDesc"),
      tempPassword: t("createUserModal.tempPassword"),
      copyBtn: t("createUserModal.copyBtn"),
      copied: t("createUserModal.copied"),
      close: t("createUserModal.close"),
    },
    createGroupModal: {
      title: t("createGroupModal.title"),
      name: t("createGroupModal.name"),
      description: t("createGroupModal.description"),
      members: t("createGroupModal.members"),
      addMembers: t("createGroupModal.addMembers"),
      noMembers: t("createGroupModal.noMembers"),
      submit: t("createGroupModal.submit"),
    },
    groupCard: {
      membersCount: t("groupCard.membersCount"),
      removeMember: t("groupCard.removeMember"),
    },
    resetPasswordModal: {
      title: t("resetPasswordModal.title"),
      desc: t("resetPasswordModal.desc"),
      successTitle: t("resetPasswordModal.successTitle"),
      successDesc: t("resetPasswordModal.successDesc"),
      submit: t("resetPasswordModal.submit"),
      close: t("resetPasswordModal.close"),
    },
    suspendModal: {
      title: t("suspendModal.title"),
      desc: t("suspendModal.desc"),
      confirmText: t("suspendModal.confirmText"),
      submit: t("suspendModal.submit"),
    },
  };

  return <AdminContent labels={labels} />;
}
