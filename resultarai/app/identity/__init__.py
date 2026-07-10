"""Bounded context ``identity``: módulos de seguridad de acceso (d11, sección 2).

Reúne el hashing/política de contraseñas, las sesiones server-side firmadas, los
dependencies de usuario/rol, el rate limiting de login, el segundo factor TOTP y
la protección CSRF. Ninguno toca ``core/`` (design Decision 10): la autorización
de identidad es por rol a nivel de ``app/``, no pasa por el Policy Gate.

Todos los módulos reciben la sesión de base como parámetro (sin globals) y son
libres de efectos en import. Los nombres de cookies/headers y los helpers para
fijarlas se re-exportan aquí para que la sección 3 (endpoints) los reutilice.
"""

from resultarai.app.identity.audit import log_identity_audit_event
from resultarai.app.identity.csrf import (
    CSRF_COOKIE,
    CSRF_HEADER,
    issue_csrf_token,
    require_csrf,
    set_csrf_cookie,
    verify_csrf,
)
from resultarai.app.identity.dependency import (
    get_current_user,
    get_db,
    get_session_config,
    require_admin,
    require_completed_wizard,
)
from resultarai.app.identity.passwords import (
    MIN_PASSWORD_LENGTH,
    PasswordPolicyError,
    generate_temporary_password,
    hash_password,
    needs_rehash,
    password_policy_violations,
    validate_password_policy,
    verify_password,
)
from resultarai.app.identity.rate_limit import (
    ACCOUNT_LOCKED,
    LockStatus,
    RateLimitConfig,
    account_lock_status,
    clear_attempts,
    count_recent_attempts,
    is_account_locked,
    normalize_account_ref,
    record_failed_attempt,
)
from resultarai.app.identity.sessions import (
    SESSION_COOKIE,
    CreatedSession,
    SessionConfig,
    clear_session_cookie,
    create_session,
    revoke_all_sessions,
    revoke_session,
    set_session_cookie,
    validate_session,
)
from resultarai.app.identity.totp import (
    BACKUP_CODE_COUNT,
    Enrollment,
    TotpConfig,
    enroll,
    generate_backup_codes,
    verify_backup_code,
    verify_code,
)

__all__ = [
    # rate_limit
    "ACCOUNT_LOCKED",
    # totp
    "BACKUP_CODE_COUNT",
    # csrf
    "CSRF_COOKIE",
    "CSRF_HEADER",
    # passwords
    "MIN_PASSWORD_LENGTH",
    # sessions
    "SESSION_COOKIE",
    "CreatedSession",
    "Enrollment",
    "LockStatus",
    "PasswordPolicyError",
    "RateLimitConfig",
    "SessionConfig",
    "TotpConfig",
    "account_lock_status",
    "clear_attempts",
    "clear_session_cookie",
    "count_recent_attempts",
    "create_session",
    "enroll",
    "generate_backup_codes",
    "generate_temporary_password",
    # dependency
    "get_current_user",
    "get_db",
    "get_session_config",
    "hash_password",
    "is_account_locked",
    "issue_csrf_token",
    # audit
    "log_identity_audit_event",
    "needs_rehash",
    "normalize_account_ref",
    "password_policy_violations",
    "record_failed_attempt",
    "require_admin",
    "require_completed_wizard",
    "require_csrf",
    "revoke_all_sessions",
    "revoke_session",
    "set_csrf_cookie",
    "set_session_cookie",
    "validate_password_policy",
    "validate_session",
    "verify_backup_code",
    "verify_code",
    "verify_csrf",
    "verify_password",
]
