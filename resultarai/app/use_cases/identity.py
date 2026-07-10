"""Casos de uso para identidad y acceso (d11, secciones 3, 4, 5, 6)."""

from __future__ import annotations

import datetime
import hashlib
from typing import Any
from uuid import UUID

from itsdangerous import BadData, URLSafeTimedSerializer
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.models import (
    Group,
    GroupMember,
    IdentityAuditEvent,
    TotpBackupCode,
    TotpSecret,
    UsageAgreementAcceptance,
    UsageAgreementVersion,
    User,
    get_utc_now,
)
from resultarai.app.identity.audit import log_identity_audit_event
from resultarai.app.identity.csrf import issue_csrf_token
from resultarai.app.identity.passwords import (
    PasswordPolicyError,
    generate_temporary_password,
    hash_password,
    validate_password_policy,
    verify_password,
)
from resultarai.app.identity.rate_limit import (
    RateLimitConfig,
    clear_attempts,
    is_account_locked,
    record_failed_attempt,
)
from resultarai.app.identity.sessions import (
    SessionConfig,
    create_session,
    revoke_all_sessions,
    revoke_session,
)
from resultarai.app.identity.totp import (
    TotpConfig,
    enroll,
    generate_backup_codes,
    verify_backup_code,
    verify_code,
)

# Hash Argon2id de "dummy" para mitigar ataques de enumeración / tiempo
_DUMMY_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$wFSW/iJ6VBr9PRAT6vxJFQ$"
    "WT/IgroWWJ3AzN/cus+tOgvWv+ksjt3Ul5a0fbqvW1k"
)


def login_user(
    db: DbSession,
    username: str,
    password: str,
    origin: str,
    session_config: SessionConfig,
    rate_limit_config: RateLimitConfig,
    totp_config: TotpConfig,
    *,
    now: datetime.datetime | None = None,
) -> dict[str, Any]:
    """Valida credenciales, aplica rate limiting y decide si exige TOTP o crea sesión."""
    # 1. Verificar bloqueo por rate limit
    if is_account_locked(db, username, rate_limit_config, now=now):
        return {"status": "locked"}

    # 2. Buscar usuario
    stmt = select(User).where(User.username == username)
    user = db.execute(stmt).scalar_one_or_none()

    # 3. Validar existencia y estado
    if user is None or user.status != "active":
        # Ejecutar verificación dummy para prevenir ataques de tiempo
        verify_password(password, _DUMMY_HASH)
        record_failed_attempt(db, username, origin, now=now)
        db.commit()
        return {"status": "invalid_credentials"}

    # 4. Verificar contraseña
    if not verify_password(password, user.password_hash):
        record_failed_attempt(db, username, origin, now=now)
        db.commit()
        return {"status": "invalid_credentials"}

    # 5. Éxito: limpiar intentos fallidos
    clear_attempts(db, username)
    db.commit()

    # 6. Determinar si requiere TOTP
    totp_required = user.role == "admin" or user.totp_required
    totp_secret = db.get(TotpSecret, user.id)
    has_totp = totp_secret is not None

    if totp_required and has_totp:
        # No crear sesión aún. Devolver token firmado de corta duración (~5 min)
        serializer = URLSafeTimedSerializer(
            session_config.signing_key, salt="resultarai.pending_totp"
        )
        pending_token = serializer.dumps({"user_id": str(user.id)})
        return {
            "status": "pending_totp",
            "pending_token": pending_token,
        }

    # 7. Crear sesión
    created = create_session(db, user.id, session_config, now=now)
    csrf_token = issue_csrf_token()
    db.commit()
    return {
        "status": "success",
        "user": user,
        "created_session": created,
        "csrf_token": csrf_token,
    }


def verify_totp_code(
    db: DbSession,
    pending_token: str,
    code: str,
    origin: str,
    session_config: SessionConfig,
    rate_limit_config: RateLimitConfig,
    totp_config: TotpConfig,
    *,
    now: datetime.datetime | None = None,
) -> dict[str, Any]:
    """Verifica el segundo paso del login con código TOTP o de respaldo."""
    # 1. Validar el token temporal
    serializer = URLSafeTimedSerializer(session_config.signing_key, salt="resultarai.pending_totp")
    try:
        # Expiración estricta de 5 minutos
        payload = serializer.loads(pending_token, max_age=300)
    except BadData:
        return {"status": "invalid_token"}

    user_id_str = payload.get("user_id")
    if not user_id_str:
        return {"status": "invalid_token"}

    user_id = UUID(user_id_str)
    user = db.get(User, user_id)
    if not user or user.status != "active":
        return {"status": "invalid_token"}

    # 2. Verificar rate limit de TOTP (se asocia a la cuenta del usuario)
    if is_account_locked(db, user.username, rate_limit_config, now=now):
        return {"status": "locked"}

    # 3. Validar código (TOTP o de respaldo)
    valid_totp = verify_code(db, user.id, code, totp_config)
    valid_backup = False
    if not valid_totp:
        valid_backup = verify_backup_code(db, user.id, code, now=now)

    if not (valid_totp or valid_backup):
        record_failed_attempt(db, user.username, origin, now=now)
        db.commit()
        if is_account_locked(db, user.username, rate_limit_config, now=now):
            return {"status": "locked"}
        return {"status": "invalid_code"}

    # 4. Éxito: limpiar intentos y crear sesión definitiva
    clear_attempts(db, user.username)
    created = create_session(db, user.id, session_config, now=now)
    csrf_token = issue_csrf_token()
    db.commit()
    return {
        "status": "success",
        "user": user,
        "created_session": created,
        "csrf_token": csrf_token,
    }


def change_password(
    db: DbSession,
    user: User,
    current_password: str,
    new_password: str,
    current_cookie_value: str | None,
    session_config: SessionConfig,
    *,
    now: datetime.datetime | None = None,
) -> dict[str, Any]:
    """Cambia la contraseña del propio usuario y revoca otras sesiones."""
    # 1. Validar contraseña actual
    if not verify_password(current_password, user.password_hash):
        return {"status": "error", "error": "Contraseña actual incorrecta."}

    # 2. Impedir contraseña idéntica
    if new_password == current_password:
        return {"status": "error", "error": "La nueva contraseña no puede ser igual a la actual."}

    # 3. Validar política
    try:
        validate_password_policy(new_password)
    except PasswordPolicyError as exc:
        return {"status": "policy_error", "violations": exc.violations}

    # 4. Guardar hash
    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    db.flush()

    # 5. Revocar otras sesiones activas
    current_session_id = None
    if current_cookie_value:
        try:
            serializer = URLSafeTimedSerializer(
                session_config.signing_key, salt="resultarai.session"
            )
            token = serializer.loads(current_cookie_value)
            current_session_id = hashlib.sha256(token.encode("utf-8")).hexdigest()
        except BadData:
            pass

    revoke_all_sessions(db, user.id, except_session=current_session_id, now=now)
    db.commit()
    return {"status": "success"}


def enroll_totp_secret(
    db: DbSession,
    user: User,
    totp_config: TotpConfig,
    *,
    now: datetime.datetime | None = None,
) -> dict[str, Any]:
    """Genera e ingresa en base de datos un secreto TOTP cifrado temporal."""
    enrollment = enroll(db, user.id, user.username, totp_config, now=now)
    backup_codes = generate_backup_codes(db, user.id, now=now)
    db.commit()
    return {
        "secret": enrollment.secret,
        "provisioning_uri": enrollment.provisioning_uri,
        "backup_codes": backup_codes,
    }


def enable_totp_secret(
    db: DbSession,
    user: User,
    code: str,
    totp_config: TotpConfig,
    *,
    now: datetime.datetime | None = None,
) -> dict[str, Any]:
    """Confirma y habilita definitivamente el secreto TOTP generado."""
    if not verify_code(db, user.id, code, totp_config):
        return {"status": "error", "error": "Código TOTP inválido."}

    user.totp_required = True
    db.flush()

    # Audit event: voluntario (source=self)
    log_identity_audit_event(
        db=db,
        event_type="user.totp_required",
        actor_user_id=user.id,
        target_ref=f"user:{user.username}",
        details={"required": "true", "source": "self"},
        now=now,
    )
    db.commit()
    return {"status": "success"}


def disable_totp_secret(
    db: DbSession,
    user: User,
    *,
    now: datetime.datetime | None = None,
) -> dict[str, Any]:
    """Desactiva TOTP si no es forzado por el Admin."""
    if user.role == "admin":
        return {"status": "error", "error": "Las cuentas con rol Admin no pueden desactivar TOTP."}

    # Verificar si el Admin fijó la obligatoriedad (details.source == 'admin')
    stmt = (
        select(IdentityAuditEvent)
        .where(
            IdentityAuditEvent.event_type == "user.totp_required",
            IdentityAuditEvent.target_ref == f"user:{user.username}",
        )
        .order_by(IdentityAuditEvent.timestamp.desc())
        .limit(1)
    )
    last_event = db.execute(stmt).scalar_one_or_none()

    if (
        last_event
        and last_event.details
        and last_event.details.get("source") == "admin"
        and last_event.details.get("required") is True
    ):
        return {
            "status": "error",
            "error": (
                "No se puede desactivar TOTP porque el Administrador "
                "lo ha marcado como obligatorio."
            ),
        }

    user.totp_required = False
    db.execute(delete(TotpSecret).where(TotpSecret.user_id == user.id))
    db.execute(delete(TotpBackupCode).where(TotpBackupCode.user_id == user.id))
    db.flush()

    log_identity_audit_event(
        db=db,
        event_type="user.totp_required",
        actor_user_id=user.id,
        target_ref=f"user:{user.username}",
        details={"required": "false", "source": "self"},
        now=now,
    )
    db.commit()
    return {"status": "success"}


def get_wizard_status(db: DbSession, user: User) -> dict[str, Any]:
    """Devuelve los pasos del wizard pendientes para el usuario."""
    must_change_password = user.must_change_password

    totp_req = user.role == "admin" or user.totp_required
    totp_secret = db.get(TotpSecret, user.id)
    totp_enrollment_pending = totp_req and (totp_secret is None)

    agreement_acceptance_pending = False
    stmt = (
        select(UsageAgreementVersion).order_by(UsageAgreementVersion.version_number.desc()).limit(1)
    )
    latest = db.execute(stmt).scalar_one_or_none()
    if latest:
        stmt_acc = select(UsageAgreementAcceptance).where(
            UsageAgreementAcceptance.user_id == user.id,
            UsageAgreementAcceptance.version_id == latest.id,
        )
        acc = db.execute(stmt_acc).scalar_one_or_none()
        if acc is None:
            agreement_acceptance_pending = True

    pending_steps = []
    if must_change_password:
        pending_steps.append("password_change")
    if totp_enrollment_pending:
        pending_steps.append("totp_enrollment")
    if agreement_acceptance_pending:
        pending_steps.append("agreement_acceptance")

    return {
        "must_change_password": must_change_password,
        "totp_enrollment_pending": totp_enrollment_pending,
        "agreement_acceptance_pending": agreement_acceptance_pending,
        "pending_steps": pending_steps,
    }


def set_wizard_preferences(
    db: DbSession, user: User, preferred_language: str, preferred_theme: str
) -> dict[str, Any]:
    """Guarda idioma y tema elegidos."""
    user.preferred_language = preferred_language
    user.preferred_theme = preferred_theme
    db.flush()
    db.commit()
    return {"status": "success"}


def get_agreement_status(db: DbSession, user: User) -> dict[str, Any]:
    """Devuelve el estado de la última firma del acuerdo contra la vigente."""
    stmt = (
        select(UsageAgreementVersion).order_by(UsageAgreementVersion.version_number.desc()).limit(1)
    )
    latest = db.execute(stmt).scalar_one_or_none()
    if not latest:
        return {
            "status": "vigente",
            "latest_version": None,
        }

    stmt_acc = select(UsageAgreementAcceptance).where(
        UsageAgreementAcceptance.user_id == user.id,
        UsageAgreementAcceptance.version_id == latest.id,
    )
    acc = db.execute(stmt_acc).scalar_one_or_none()

    version_data = {
        "id": str(latest.id),
        "text": latest.text,
        "version_number": latest.version_number,
    }

    if acc:
        return {"status": "vigente", "latest_version": version_data}
    return {"status": "pendiente", "latest_version": version_data}


def accept_agreement(
    db: DbSession,
    user: User,
    version_id: UUID,
    *,
    now: datetime.datetime | None = None,
) -> dict[str, Any]:
    """Registra la aceptación explícita de la versión vigente por parte del usuario."""
    version = db.get(UsageAgreementVersion, version_id)
    if not version:
        return {"status": "error", "error": "Versión del acuerdo no encontrada."}

    # Verificar que sea la vigente
    stmt = (
        select(UsageAgreementVersion).order_by(UsageAgreementVersion.version_number.desc()).limit(1)
    )
    latest = db.execute(stmt).scalar_one_or_none()
    if not latest or latest.id != version_id:
        return {"status": "error", "error": "Solo se puede aceptar la versión vigente del acuerdo."}

    stmt_acc = select(UsageAgreementAcceptance).where(
        UsageAgreementAcceptance.user_id == user.id,
        UsageAgreementAcceptance.version_id == version_id,
    )
    acc = db.execute(stmt_acc).scalar_one_or_none()
    if not acc:
        db.add(
            UsageAgreementAcceptance(
                user_id=user.id,
                version_id=version_id,
                accepted_at=now or get_utc_now(),
            )
        )
        db.flush()

        # Audit
        log_identity_audit_event(
            db=db,
            event_type="agreement.accepted",
            actor_user_id=user.id,
            target_ref=f"agreement:{version_id}",
            details={"version_number": version.version_number},
            now=now,
        )
    db.commit()
    return {"status": "success"}


# ==========================================
# ADMIN USE CASES
# ==========================================


def admin_create_user(
    db: DbSession,
    admin_user: User,
    username: str,
    display_name: str,
    email: str | None,
    role: str,
    group_id: UUID | None = None,
    *,
    now: datetime.datetime | None = None,
) -> dict[str, Any]:
    """Crea una cuenta de usuario, asocia grupo, y devuelve la temporal."""
    stmt = select(User).where(User.username == username)
    if db.execute(stmt).scalar_one_or_none():
        return {"status": "error", "error": "El nombre de usuario ya existe."}

    if role not in ("admin", "tecnico", "funcional"):
        return {"status": "error", "error": f"Rol inválido: {role}."}

    temp_password = generate_temporary_password(16)
    user = User(
        username=username,
        display_name=display_name,
        email=email,
        role=role,
        password_hash=hash_password(temp_password),
        must_change_password=True,
        status="active",
        totp_required=(role == "admin"),
    )
    db.add(user)
    db.flush()

    if group_id:
        group = db.get(Group, group_id)
        if not group:
            return {"status": "error", "error": "Grupo no encontrado."}
        db.add(
            GroupMember(
                group_id=group_id,
                user_id=user.id,
                added_at=now or get_utc_now(),
            )
        )
        db.flush()

    # Audit log (sin secretos)
    log_identity_audit_event(
        db=db,
        event_type="user.created",
        actor_user_id=admin_user.id,
        target_ref=f"user:{username}",
        details={
            "role": role,
            "display_name": display_name,
            "group_id": str(group_id) if group_id else None,
        },
        now=now,
    )

    db.commit()
    return {
        "status": "success",
        "user_id": str(user.id),
        "temp_password": temp_password,
    }


def admin_suspend_user(
    db: DbSession,
    admin_user: User,
    user_id: UUID,
    *,
    now: datetime.datetime | None = None,
) -> dict[str, Any]:
    """Suspende un usuario y revoca todas sus sesiones."""
    user = db.get(User, user_id)
    if not user:
        return {"status": "error", "error": "Usuario no encontrado."}

    user.status = "suspended"
    db.flush()

    # Revocar sesiones de inmediato
    revoke_all_sessions(db, user.id, revoked_by=admin_user.id, now=now)

    log_identity_audit_event(
        db=db,
        event_type="user.suspended",
        actor_user_id=admin_user.id,
        target_ref=f"user:{user.username}",
        details={"status": "suspended"},
        now=now,
    )
    db.commit()
    return {"status": "success"}


def admin_change_role(
    db: DbSession,
    admin_user: User,
    user_id: UUID,
    role: str,
    *,
    now: datetime.datetime | None = None,
) -> dict[str, Any]:
    """Cambia el rol del usuario (prohibido a sí mismo)."""
    if admin_user.id == user_id:
        return {"status": "error", "error": "No puedes cambiar tu propio rol."}

    user = db.get(User, user_id)
    if not user:
        return {"status": "error", "error": "Usuario no encontrado."}

    if role not in ("admin", "tecnico", "funcional"):
        return {"status": "error", "error": f"Rol inválido: {role}."}

    old_role = user.role
    user.role = role

    # Si pasa a admin, TOTP es forzado
    if role == "admin":
        user.totp_required = True

    db.flush()

    log_identity_audit_event(
        db=db,
        event_type="user.role_changed",
        actor_user_id=admin_user.id,
        target_ref=f"user:{user.username}",
        details={"old_role": old_role, "new_role": role},
        now=now,
    )
    db.commit()
    return {"status": "success"}


def admin_reset_password(
    db: DbSession,
    admin_user: User,
    user_id: UUID,
    *,
    now: datetime.datetime | None = None,
) -> dict[str, Any]:
    """Genera nueva contraseña temporal y revoca sesiones para forzar wizard."""
    user = db.get(User, user_id)
    if not user:
        return {"status": "error", "error": "Usuario no encontrado."}

    temp_password = generate_temporary_password(16)
    user.password_hash = hash_password(temp_password)
    user.must_change_password = True
    db.flush()

    # Revocar todas las sesiones
    revoke_all_sessions(db, user.id, revoked_by=admin_user.id, now=now)

    log_identity_audit_event(
        db=db,
        event_type="user.password_reset",
        actor_user_id=admin_user.id,
        target_ref=f"user:{user.username}",
        details={},
        now=now,
    )

    db.commit()
    return {
        "status": "success",
        "temp_password": temp_password,
    }


def admin_revoke_user_sessions(
    db: DbSession,
    admin_user: User,
    user_id: UUID,
    session_id: str | None = None,
    *,
    now: datetime.datetime | None = None,
) -> dict[str, Any]:
    """Revoca una sesión individual o todas las sesiones de un usuario."""
    user = db.get(User, user_id)
    if not user:
        return {"status": "error", "error": "Usuario no encontrado."}

    if session_id:
        revoke_session(db, session_id, revoked_by=admin_user.id, now=now)
        details = {"session_id": session_id}
    else:
        count = revoke_all_sessions(db, user.id, revoked_by=admin_user.id, now=now)
        details = {"all": "true", "count": str(count)}

    log_identity_audit_event(
        db=db,
        event_type="session.revoked",
        actor_user_id=admin_user.id,
        target_ref=f"user:{user.username}",
        details=details,
        now=now,
    )
    db.commit()
    return {"status": "success"}


def admin_require_totp(
    db: DbSession,
    admin_user: User,
    user_id: UUID,
    require: bool,
    *,
    now: datetime.datetime | None = None,
) -> dict[str, Any]:
    """Marca TOTP como obligatorio u opcional (prohibido desactivar en admin)."""
    user = db.get(User, user_id)
    if not user:
        return {"status": "error", "error": "Usuario no encontrado."}

    if user.role == "admin" and not require:
        return {
            "status": "error",
            "error": "TOTP es obligatorio para el rol Admin y no puede desactivarse.",
        }

    user.totp_required = require
    db.flush()

    log_identity_audit_event(
        db=db,
        event_type="user.totp_required",
        actor_user_id=admin_user.id,
        target_ref=f"user:{user.username}",
        details={"required": "true" if require else "false", "source": "admin"},
        now=now,
    )
    db.commit()
    return {"status": "success"}


def admin_create_group(
    db: DbSession,
    admin_user: User,
    name: str,
    description: str | None = None,
    *,
    now: datetime.datetime | None = None,
) -> dict[str, Any]:
    """Crea un grupo de usuarios."""
    stmt = select(Group).where(Group.name == name)
    if db.execute(stmt).scalar_one_or_none():
        return {"status": "error", "error": "El nombre de grupo ya existe."}

    group = Group(
        name=name,
        description=description,
        created_at=now or get_utc_now(),
    )
    db.add(group)
    db.flush()

    log_identity_audit_event(
        db=db,
        event_type="group.created",
        actor_user_id=admin_user.id,
        target_ref=f"group:{name}",
        details={"description": description},
        now=now,
    )
    db.commit()
    return {"status": "success", "group_id": str(group.id)}


def admin_add_group_member(
    db: DbSession,
    admin_user: User,
    group_id: UUID,
    user_id: UUID,
    *,
    now: datetime.datetime | None = None,
) -> dict[str, Any]:
    """Agrega un usuario a un grupo."""
    group = db.get(Group, group_id)
    if not group:
        return {"status": "error", "error": "Grupo no encontrado."}

    user = db.get(User, user_id)
    if not user:
        return {"status": "error", "error": "Usuario no encontrado."}

    # Verificar membresía
    stmt = select(GroupMember).where(
        GroupMember.group_id == group_id, GroupMember.user_id == user_id
    )
    existing = db.execute(stmt).scalar_one_or_none()
    if not existing:
        db.add(
            GroupMember(
                group_id=group_id,
                user_id=user_id,
                added_at=now or get_utc_now(),
            )
        )
        db.flush()

        log_identity_audit_event(
            db=db,
            event_type="group.member_added",
            actor_user_id=admin_user.id,
            target_ref=f"group:{group.name}",
            details={"user_id": str(user_id), "username": user.username},
            now=now,
        )
    db.commit()
    return {"status": "success"}


def admin_remove_group_member(
    db: DbSession,
    admin_user: User,
    group_id: UUID,
    user_id: UUID,
    *,
    now: datetime.datetime | None = None,
) -> dict[str, Any]:
    """Quita a un usuario de un grupo."""
    group = db.get(Group, group_id)
    if not group:
        return {"status": "error", "error": "Grupo no encontrado."}

    user = db.get(User, user_id)
    if not user:
        return {"status": "error", "error": "Usuario no encontrado."}

    stmt = select(GroupMember).where(
        GroupMember.group_id == group_id, GroupMember.user_id == user_id
    )
    existing = db.execute(stmt).scalar_one_or_none()
    if existing:
        db.delete(existing)
        db.flush()

        log_identity_audit_event(
            db=db,
            event_type="group.member_removed",
            actor_user_id=admin_user.id,
            target_ref=f"group:{group.name}",
            details={"user_id": str(user_id), "username": user.username},
            now=now,
        )
    db.commit()
    return {"status": "success"}


def admin_publish_agreement(
    db: DbSession,
    admin_user: User,
    text: str,
    *,
    now: datetime.datetime | None = None,
) -> dict[str, Any]:
    """Publica una nueva versión del acuerdo de uso del sistema."""
    stmt = select(func.max(UsageAgreementVersion.version_number))
    max_val = db.execute(stmt).scalar()
    next_num = (max_val or 0) + 1

    new_version = UsageAgreementVersion(
        text=text,
        version_number=next_num,
        published_at=now or get_utc_now(),
        published_by=admin_user.id,
    )
    db.add(new_version)
    db.flush()

    log_identity_audit_event(
        db=db,
        event_type="agreement.published",
        actor_user_id=admin_user.id,
        target_ref=f"agreement:{new_version.id}",
        details={"version_number": next_num},
        now=now,
    )
    db.commit()
    return {
        "status": "success",
        "version_id": str(new_version.id),
        "version_number": new_version.version_number,
    }
