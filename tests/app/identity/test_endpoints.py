# ruff: noqa: E402
"""Integration/endpoints tests for identity routers and use cases (d11, sections 3-6)."""

from __future__ import annotations

import datetime
import os
from collections.abc import Iterator
from typing import Annotated, Any
from uuid import UUID

from cryptography.fernet import Fernet

# Set a stable test key in the environment before importing anything that initializes TotpConfig
_STABLE_KEY = Fernet.generate_key().decode("utf-8")
os.environ["IDENTITY_TOTP_ENCRYPTION_KEY"] = _STABLE_KEY

import pyotp
import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.connection import SessionLocal, get_db_session
from resultarai.adapters.persistence_postgres.models import (
    GroupMember,
    IdentityAuditEvent,
    TotpSecret,
    User,
)
from resultarai.app.api import create_app
from resultarai.app.identity import (
    SESSION_COOKIE,
    SessionConfig,
    TotpConfig,
    get_db,
    get_session_config,
    hash_password,
    require_completed_wizard,
)
from resultarai.app.use_cases.identity import (
    admin_publish_agreement,
)
from tests.app.identity.conftest import make_user

_CONFIG = SessionConfig(
    signing_key="test-endpoint-key-for-identity-and-access-control",
    idle_timeout=datetime.timedelta(minutes=30),
    absolute_lifetime=datetime.timedelta(hours=8),
    cookie_secure=False,  # disabled Secure for test client cookie extraction
)


def make_completed_admin(username: str, password_hash: str) -> tuple[UUID, str]:
    """Crea un administrador con TOTP enrolado para pasar el wizard."""
    user_id = make_user(username, role="admin", password_hash=password_hash)
    secret_base32 = pyotp.random_base32()

    totp_config = TotpConfig.from_env()
    fernet = Fernet(totp_config.encryption_key)
    encrypted_secret = fernet.encrypt(secret_base32.encode("utf-8"))

    with get_db_session() as db:
        db.add(TotpSecret(user_id=user_id, encrypted_secret=encrypted_secret))
        db.commit()
    return user_id, secret_base32


def login_admin(client: TestClient, username: str, pwd: str, secret_base32: str) -> None:
    """Realiza la autenticación completa en dos pasos de un Administrador en los tests."""
    r_login = client.post("/api/auth/login", json={"username": username, "password": pwd})
    assert r_login.status_code == 200
    res_data = r_login.json()
    assert res_data["status"] == "pending_totp"
    pending_token = res_data["pending_token"]

    totp = pyotp.TOTP(secret_base32)
    code = totp.now()

    r_verify = client.post(
        "/api/auth/totp/verify", json={"pending_token": pending_token, "code": code}
    )
    assert r_verify.status_code == 200


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Crea un TestClient con overrides inyectables para base de datos y configuración."""
    app = create_app()

    # Agregar una ruta protegida de negocio de prueba para validar el guard del wizard
    @app.get("/api/test-business-feature")
    def test_feature(user: Annotated[User, Depends(require_completed_wizard)]) -> dict[str, str]:
        return {"ok": "true", "username": user.username}

    def _override_db() -> Iterator[DbSession]:
        session = SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_session_config] = lambda: _CONFIG

    with TestClient(app) as test_client:
        yield test_client


def post_csrf(client: TestClient, url: str, json: dict[str, Any] | None = None) -> Any:
    """Helper que adjunta el header CSRF a partir de la cookie de sesión actual."""
    csrf_token = client.cookies.get("resultarai_csrf")
    headers = {}
    if csrf_token:
        headers["X-CSRF-Token"] = csrf_token
    return client.post(url, json=json, headers=headers)


def delete_csrf(client: TestClient, url: str) -> Any:
    """Helper que adjunta el header CSRF a peticiones DELETE."""
    csrf_token = client.cookies.get("resultarai_csrf")
    headers = {}
    if csrf_token:
        headers["X-CSRF-Token"] = csrf_token
    return client.delete(url, headers=headers)


def test_login_flow_success_no_totp(client: TestClient) -> None:
    """Login exitoso de un usuario que no tiene TOTP requerido."""
    pwd = "ValidPassword123!"
    make_user("login-user", role="tecnico", password_hash=hash_password(pwd))

    response = client.post("/api/auth/login", json={"username": "login-user", "password": pwd})
    assert response.status_code == 200
    assert response.json() == {"status": "success"}

    # Debe haber cookies seteadas
    assert SESSION_COOKIE in client.cookies
    assert "resultarai_csrf" in client.cookies


def test_login_flow_failed_credentials(client: TestClient) -> None:
    """Login fallido devuelve error genérico sin revelar la existencia de la cuenta."""
    pwd = "ValidPassword123!"
    make_user("login-exists", password_hash=hash_password(pwd))

    # Caso 1: usuario existe, contraseña incorrecta
    r1 = client.post(
        "/api/auth/login", json={"username": "login-exists", "password": "wrongpassword"}
    )
    assert r1.status_code == 400
    assert r1.json()["detail"] == "Credenciales inválidas."

    # Caso 2: usuario inexistente
    r2 = client.post(
        "/api/auth/login", json={"username": "non-existent", "password": "anypassword"}
    )
    assert r2.status_code == 400
    assert r2.json()["detail"] == "Credenciales inválidas."


def test_login_flow_suspended_user(client: TestClient) -> None:
    """Login de un usuario suspendido devuelve el mismo error genérico."""
    pwd = "ValidPassword123!"
    make_user("login-suspended", status="suspended", password_hash=hash_password(pwd))

    response = client.post("/api/auth/login", json={"username": "login-suspended", "password": pwd})
    assert response.status_code == 400
    assert response.json()["detail"] == "Credenciales inválidas."


def test_login_rate_limiting(client: TestClient) -> None:
    """Múltiples intentos fallidos provocan el bloqueo ACCOUNT_LOCKED."""
    pwd = "ValidPassword123!"
    make_user("rate-user", password_hash=hash_password(pwd))

    # Realizar 5 intentos fallidos (el default es 5)
    for _ in range(5):
        client.post("/api/auth/login", json={"username": "rate-user", "password": "wrong-password"})

    # El 6to intento debe devolver ACCOUNT_LOCKED
    response = client.post("/api/auth/login", json={"username": "rate-user", "password": pwd})
    assert response.status_code == 400
    assert response.json()["detail"] == "ACCOUNT_LOCKED"


def test_login_totp_required_and_verify(client: TestClient) -> None:
    """Un usuario con TOTP obligatorio e ingresado pasa por pending_totp y verificación."""
    pwd = "ValidPassword123!"
    user_id = make_user("totp-user", role="admin", password_hash=hash_password(pwd))

    # Inicializar TOTP secret en base de datos para este usuario
    secret_base32 = pyotp.random_base32()
    totp_config = TotpConfig.from_env()
    fernet = Fernet(totp_config.encryption_key)
    encrypted_secret = fernet.encrypt(secret_base32.encode("utf-8"))

    with get_db_session() as db:
        db.add(TotpSecret(user_id=user_id, encrypted_secret=encrypted_secret))
        db.commit()

    # Login inicial
    r_login = client.post("/api/auth/login", json={"username": "totp-user", "password": pwd})
    assert r_login.status_code == 200
    res_data = r_login.json()
    assert res_data["status"] == "pending_totp"
    assert "pending_token" in res_data
    pending_token = res_data["pending_token"]

    # No debe haber cookies de sesión aún
    assert SESSION_COOKIE not in client.cookies

    # Generar código TOTP
    totp = pyotp.TOTP(secret_base32)
    code = totp.now()

    # Verificar TOTP con código incorrecto
    r_verify_bad = client.post(
        "/api/auth/totp/verify", json={"pending_token": pending_token, "code": "000000"}
    )
    assert r_verify_bad.status_code == 400
    assert r_verify_bad.json()["detail"] == "Código inválido."

    # Verificar con código correcto
    r_verify_ok = client.post(
        "/api/auth/totp/verify", json={"pending_token": pending_token, "code": code}
    )
    assert r_verify_ok.status_code == 200
    assert r_verify_ok.json() == {"status": "success"}

    # Debe haber cookies seteadas tras verificación exitosa
    assert SESSION_COOKIE in client.cookies


def test_logout(client: TestClient) -> None:
    """Logout revoca la sesión del servidor y borra la cookie del cliente."""
    pwd = "ValidPassword123!"
    make_user("logout-user", password_hash=hash_password(pwd))

    # Iniciar sesión
    client.post("/api/auth/login", json={"username": "logout-user", "password": pwd})
    assert SESSION_COOKIE in client.cookies

    # Logout (requiere cookie de sesión y CSRF token)
    response = post_csrf(client, "/api/auth/logout")
    assert response.status_code == 200
    assert response.json() == {"status": "success"}

    # Cookie eliminada en cliente
    assert SESSION_COOKIE not in client.cookies


def test_password_change(client: TestClient) -> None:
    """Cambio propio de contraseña exige política y revoca otras sesiones."""
    pwd = "OldPassword123!"
    new_pwd = "NewPassword123!"
    make_user("pwd-user", password_hash=hash_password(pwd))

    # Iniciar sesión
    client.post("/api/auth/login", json={"username": "pwd-user", "password": pwd})

    # Cambiar contraseña con datos erróneos
    r_err = post_csrf(
        client,
        "/api/auth/password",
        json={"current_password": "wrong", "new_password": "short"},
    )
    assert r_err.status_code == 400

    # Cambiar contraseña correctamente
    r_ok = post_csrf(
        client,
        "/api/auth/password",
        json={"current_password": pwd, "new_password": new_pwd},
    )
    assert r_ok.status_code == 200
    assert r_ok.json() == {"status": "success"}

    # Intentar login con contraseña vieja
    r_old_login = client.post("/api/auth/login", json={"username": "pwd-user", "password": pwd})
    assert r_old_login.status_code == 400

    # Login con contraseña nueva
    r_new_login = client.post("/api/auth/login", json={"username": "pwd-user", "password": new_pwd})
    assert r_new_login.status_code == 200


def test_wizard_status_preferences(client: TestClient) -> None:
    """Wizard status devuelve pasos correctos y permite guardar preferencias."""
    pwd = "TempPassword123!"
    user_id = make_user("wizard-user", password_hash=hash_password(pwd))

    # Forzar cambio de contraseña en base de datos
    with get_db_session() as db:
        user = db.get(User, user_id)
        assert user is not None
        user.must_change_password = True
        db.commit()

    # Login
    client.post("/api/auth/login", json={"username": "wizard-user", "password": pwd})

    # Obtener status
    r_status = client.get("/api/me/wizard/status")
    assert r_status.status_code == 200
    status_data = r_status.json()
    assert "password_change" in status_data["pending_steps"]

    # Guardar preferencias
    r_pref = post_csrf(
        client,
        "/api/me/wizard/preferences",
        json={"preferred_language": "es", "preferred_theme": "dark"},
    )
    assert r_pref.status_code == 200
    assert r_pref.json() == {"status": "success"}

    # Verificar en base de datos
    with get_db_session() as db:
        user = db.get(User, user_id)
        assert user is not None
        assert user.preferred_language == "es"
        assert user.preferred_theme == "dark"


def test_personal_totp_config(client: TestClient) -> None:
    """Activación y desactivación voluntaria de TOTP para Técnico."""
    pwd = "ValidPassword123!"
    user_id = make_user("personal-totp", role="tecnico", password_hash=hash_password(pwd))

    client.post("/api/auth/login", json={"username": "personal-totp", "password": pwd})

    # 1. Enrolar
    r_enroll = post_csrf(client, "/api/me/totp/enroll")
    assert r_enroll.status_code == 200
    enroll_data = r_enroll.json()
    assert "secret" in enroll_data
    assert "backup_codes" in enroll_data
    secret = enroll_data["secret"]

    # 2. Confirmar y activar
    code = pyotp.TOTP(secret).now()
    r_enable = post_csrf(client, "/api/me/totp/enable", json={"code": code})
    assert r_enable.status_code == 200
    assert r_enable.json() == {"status": "success"}

    # Verificar que totp_required ahora es True en base de datos
    with get_db_session() as db:
        user = db.get(User, user_id)
        assert user is not None
        assert user.totp_required is True

    # 3. Desactivar
    r_disable = post_csrf(client, "/api/me/totp/disable")
    assert r_disable.status_code == 200
    assert r_disable.json() == {"status": "success"}

    # Verificar que se desactivó y se borró secreto
    with get_db_session() as db:
        user = db.get(User, user_id)
        assert user is not None
        assert user.totp_required is False
        assert db.get(TotpSecret, user_id) is None


def test_agreement_status_acceptance_and_publish(client: TestClient) -> None:
    """Publicación, consulta de estado y aceptación del acuerdo de uso."""
    admin_pwd = "AdminPassword123!"
    _, secret_base = make_completed_admin("ag-admin", hash_password(admin_pwd))

    user_pwd = "UserPassword123!"
    make_user("ag-user", role="funcional", password_hash=hash_password(user_pwd))

    # 1. Publicar versión como Admin
    login_admin(client, "ag-admin", admin_pwd, secret_base)
    r_pub = post_csrf(client, "/api/admin/agreement/publish", json={"text": "Texto del acuerdo 1"})
    assert r_pub.status_code == 200
    pub_data = r_pub.json()
    version_id = UUID(pub_data["version_id"])

    # Cerrar sesión admin
    post_csrf(client, "/api/auth/logout")

    # 2. Iniciar sesión usuario e inspeccionar status (debe estar pendiente)
    client.post("/api/auth/login", json={"username": "ag-user", "password": user_pwd})
    r_status1 = client.get("/api/me/agreement/status")
    assert r_status1.status_code == 200
    assert r_status1.json()["status"] == "pendiente"

    # 3. Aceptar acuerdo
    r_acc = post_csrf(client, "/api/me/agreement/accept", json={"version_id": str(version_id)})
    assert r_acc.status_code == 200
    assert r_acc.json() == {"status": "success"}

    # 4. Status ahora debe ser vigente
    r_status2 = client.get("/api/me/agreement/status")
    assert r_status2.json()["status"] == "vigente"


def test_admin_user_management(client: TestClient) -> None:
    """Admin crea un usuario, cambia rol, resetea password, exige totp y revoca sesiones."""
    admin_pwd = "AdminPassword123!"
    admin_id, secret_base = make_completed_admin("mgt-admin", hash_password(admin_pwd))

    # Iniciar sesión Admin
    login_admin(client, "mgt-admin", admin_pwd, secret_base)

    # 1. Crear usuario
    r_create = post_csrf(
        client,
        "/api/admin/users",
        json={
            "username": "new-employee",
            "display_name": "New Employee",
            "email": "employee@test.com",
            "role": "funcional",
        },
    )
    assert r_create.status_code == 200
    create_data = r_create.json()
    user_id = UUID(create_data["user_id"])
    assert "temp_password" in create_data

    # 2. Cambiar rol (prohibido a uno mismo, permitido sobre otros)
    # Uno mismo:
    r_self_role = post_csrf(client, f"/api/admin/users/{admin_id}/role", json={"role": "tecnico"})
    assert r_self_role.status_code == 400
    # Otro:
    r_other_role = post_csrf(client, f"/api/admin/users/{user_id}/role", json={"role": "tecnico"})
    assert r_other_role.status_code == 200

    # 3. Exigir TOTP
    r_req_totp = post_csrf(
        client, f"/api/admin/users/{user_id}/require-totp", json={"require": True}
    )
    assert r_req_totp.status_code == 200

    with get_db_session() as db:
        user = db.get(User, user_id)
        assert user is not None
        assert user.totp_required is True

    # 4. Reset password
    r_reset = post_csrf(client, f"/api/admin/users/{user_id}/reset-password")
    assert r_reset.status_code == 200
    assert "temp_password" in r_reset.json()

    # 5. Revocar sesiones
    r_revoke = post_csrf(client, f"/api/admin/users/{user_id}/sessions/revoke", json={})
    assert r_revoke.status_code == 200


def test_admin_group_management(client: TestClient) -> None:
    """Admin crea un grupo y gestiona la membresía."""
    admin_pwd = "AdminPassword123!"
    _, secret_base = make_completed_admin("grp-admin", hash_password(admin_pwd))

    user_id = make_user("grp-member", role="tecnico")

    login_admin(client, "grp-admin", admin_pwd, secret_base)

    # 1. Crear grupo
    r_group = post_csrf(
        client, "/api/admin/groups", json={"name": "Soporte", "description": "Equipo soporte"}
    )
    assert r_group.status_code == 200
    group_id = UUID(r_group.json()["group_id"])

    # 2. Añadir miembro
    r_add = post_csrf(
        client, f"/api/admin/groups/{group_id}/members", json={"user_id": str(user_id)}
    )
    assert r_add.status_code == 200

    # Verificar en base de datos
    with get_db_session() as db:
        member = db.execute(
            select(GroupMember).where(
                GroupMember.group_id == group_id, GroupMember.user_id == user_id
            )
        ).scalar_one_or_none()
        assert member is not None

    # 3. Quitar miembro
    r_rem = delete_csrf(client, f"/api/admin/groups/{group_id}/members/{user_id}")
    assert r_rem.status_code == 200

    with get_db_session() as db:
        member = db.execute(
            select(GroupMember).where(
                GroupMember.group_id == group_id, GroupMember.user_id == user_id
            )
        ).scalar_one_or_none()
        assert member is None


def test_guard_intercepts_unauthorized_access(client: TestClient) -> None:
    """Guard intercepta accesos a endpoints de negocio si el acuerdo o wizard están pendientes."""
    pwd = "ValidPassword123!"
    make_user("blocked-user", role="tecnico", password_hash=hash_password(pwd))

    # Establecer acuerdo vigente en el sistema
    with get_db_session() as db:
        admin = User(
            username="guard-admin",
            display_name="Guard Admin",
            role="admin",
            password_hash=hash_password(pwd),
            status="active",
        )
        db.add(admin)
        db.flush()
        admin_publish_agreement(db, admin, "Acuerdo de uso vigente")
        db.commit()

    # Login (el acuerdo de uso está pendiente de aceptación)
    client.post("/api/auth/login", json={"username": "blocked-user", "password": pwd})

    # Intentar acceder a un endpoint de negocio /api/test-business-feature
    # Debe lanzar 403 con AGREEMENT_PENDING
    response = client.get("/api/test-business-feature")
    assert response.status_code == 403
    assert response.json()["detail"] == "AGREEMENT_PENDING"


def test_csrf_protection(client: TestClient) -> None:
    """Toda mutación autenticada es rechazada si no se envía un header CSRF válido."""
    pwd = "ValidPassword123!"
    make_user("csrf-user", role="tecnico", password_hash=hash_password(pwd))

    client.post("/api/auth/login", json={"username": "csrf-user", "password": pwd})

    # Intento de POST sin header CSRF
    response = client.post(
        "/api/me/wizard/preferences",
        json={"preferred_language": "es", "preferred_theme": "light"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF token inválido o ausente."


def test_audit_log_entries(client: TestClient) -> None:
    """Cada mutación genera exactamente un evento registrado en identity_audit_events."""
    admin_pwd = "AdminPassword123!"
    admin_id, secret_base = make_completed_admin("audit-admin", hash_password(admin_pwd))

    login_admin(client, "audit-admin", admin_pwd, secret_base)

    # Ver recuento inicial
    with get_db_session() as db:
        count_before = db.execute(select(func.count(IdentityAuditEvent.id))).scalar_one()

    # 1. Crear grupo (mutación)
    post_csrf(client, "/api/admin/groups", json={"name": "AuditGroup"})

    # Verificar que se creó exactamente un log
    with get_db_session() as db:
        count_after = db.execute(select(func.count(IdentityAuditEvent.id))).scalar_one()
        assert count_after == count_before + 1

        # Verificar detalles del evento
        last_event = db.execute(
            select(IdentityAuditEvent).order_by(IdentityAuditEvent.timestamp.desc()).limit(1)
        ).scalar_one()
        assert last_event.event_type == "group.created"
        assert last_event.actor_user_id == admin_id
        assert last_event.target_ref == "group:AuditGroup"


def test_security_brute_force_release(client: TestClient) -> None:
    """9.1 Test de fuerza bruta: bloqueo y liberación por tiempo o por acción de Admin."""
    pwd = "ValidPassword123!"
    make_user("brute-force-user", role="tecnico", password_hash=hash_password(pwd))

    # 5 intentos fallidos
    for _ in range(5):
        client.post("/api/auth/login", json={"username": "brute-force-user", "password": "bad"})

    # Bloqueado
    r = client.post("/api/auth/login", json={"username": "brute-force-user", "password": pwd})
    assert r.status_code == 400
    assert r.json()["detail"] == "ACCOUNT_LOCKED"

    # Liberación por acción del Admin (limpia intentos en la DB)
    from resultarai.app.identity import clear_attempts

    with get_db_session() as db:
        clear_attempts(db, "brute-force-user")
        db.commit()

    # Vuelve a poder entrar
    r = client.post("/api/auth/login", json={"username": "brute-force-user", "password": pwd})
    assert r.status_code == 200
    assert r.json()["status"] == "success"


def test_security_revoked_or_expired_session_returns_401(client: TestClient) -> None:
    """9.2 Test de sesión revocada o expirada -> 401 en cualquier endpoint autenticado."""
    pwd = "ValidPassword123!"
    user_id = make_user("session-fail-user", role="tecnico", password_hash=hash_password(pwd))

    # login
    client.post("/api/auth/login", json={"username": "session-fail-user", "password": pwd})
    assert SESSION_COOKIE in client.cookies

    # Revocar sesión del servidor manualmente
    from resultarai.app.identity import revoke_all_sessions

    with get_db_session() as db:
        revoke_all_sessions(db, user_id)
        db.commit()

    # Intentar acceder a endpoints de sección 3 (auth), 4 (admin), 5 (me)
    r3 = post_csrf(
        client,
        "/api/auth/password",
        json={"current_password": pwd, "new_password": "NewPassword123!"},
    )
    assert r3.status_code == 401

    r4 = client.get("/api/admin/users")
    assert r4.status_code == 401

    r5 = client.get("/api/me/agreement/status")
    assert r5.status_code == 401


def test_security_body_userid_ignored(client: TestClient) -> None:
    """9.3 Test de body con userId ajeno -> ignorado en endpoints autenticados."""
    pwd = "ValidPassword123!"
    user_a = make_user("user-alice", role="admin", password_hash=hash_password(pwd))
    user_b = make_user("user-bob", role="tecnico", password_hash=hash_password(pwd))

    # Enrolar TOTP para alice para poder loguearse como admin completo
    secret_base32 = pyotp.random_base32()
    totp_config = TotpConfig.from_env()
    fernet = Fernet(totp_config.encryption_key)
    encrypted_secret = fernet.encrypt(secret_base32.encode("utf-8"))
    with get_db_session() as db:
        db.add(TotpSecret(user_id=user_a, encrypted_secret=encrypted_secret))
        db.commit()

    # Login Alice
    login_admin(client, "user-alice", pwd, secret_base32)

    # 1. Endpoint Sección 3 (auth): password con userId ajeno
    # (El endpoint cambia la contraseña de Alice, no de Bob)
    r3 = post_csrf(
        client,
        "/api/auth/password",
        json={"current_password": pwd, "new_password": "NewPassword123!", "userId": str(user_b)},
    )
    assert r3.status_code == 200

    # Verificar que la contraseña de Alice cambió, pero la de Bob sigue igual
    r_alice_old = client.post("/api/auth/login", json={"username": "user-alice", "password": pwd})
    assert r_alice_old.status_code == 400

    # 2. Endpoint Sección 4 (admin): crear usuario con userId ajeno en body
    r4 = post_csrf(
        client,
        "/api/admin/users",
        json={
            "username": "user-charlie",
            "display_name": "Charlie",
            "role": "funcional",
            "userId": str(user_b),
        },
    )
    assert r4.status_code == 200

    # 3. Endpoint Sección 5 (me): aceptar acuerdo
    # (El acuerdo es aceptado para el usuario autenticado (Alice), no para Bob)
    # Primero publicar acuerdo
    r_pub = post_csrf(client, "/api/admin/agreement/publish", json={"text": "Acuerdo de prueba"})
    version_id = r_pub.json()["version_id"]

    r5 = post_csrf(
        client, "/api/me/agreement/accept", json={"version_id": version_id, "userId": str(user_b)}
    )
    assert r5.status_code == 200

    # Verificar que el estado del acuerdo para Bob sigue siendo pendiente (no aceptó)
    # Logout Alice, Login Bob
    post_csrf(client, "/api/auth/logout")
    client.post("/api/auth/login", json={"username": "user-bob", "password": pwd})
    r_bob_status = client.get("/api/me/agreement/status")
    assert r_bob_status.status_code == 200
    assert r_bob_status.json()["status"] == "pendiente"


def test_security_cookie_attributes_and_csrf_rejection(client: TestClient) -> None:
    """9.4 Test de atributos de cookie y de rechazo de mutaciones sin token CSRF válido."""
    pwd = "ValidPassword123!"
    make_user("csrf-attr-user", role="tecnico", password_hash=hash_password(pwd))

    # Iniciar sesión con configuración de cookies segura forzada
    r_login = client.post("/api/auth/login", json={"username": "csrf-attr-user", "password": pwd})
    assert r_login.status_code == 200

    # Obtener las cabeceras Set-Cookie
    cookies_headers = r_login.headers.get_list("set-cookie")
    assert len(cookies_headers) >= 2

    # Buscar cookie de sesión y CSRF
    session_cookie_header = None
    csrf_cookie_header = None
    for header in cookies_headers:
        if "resultarai_session=" in header:
            session_cookie_header = header
        elif "resultarai_csrf=" in header:
            csrf_cookie_header = header

    assert session_cookie_header is not None
    assert csrf_cookie_header is not None

    # session cookie: HttpOnly, SameSite=Lax
    assert "httponly" in session_cookie_header.lower()
    assert "samesite=lax" in session_cookie_header.lower()

    # csrf cookie: SameSite=Lax, NO HttpOnly
    assert "httponly" not in csrf_cookie_header.lower()
    assert "samesite=lax" in csrf_cookie_header.lower()

    # Mutaciones sin CSRF header -> 403
    r_no_csrf = client.post(
        "/api/me/wizard/preferences", json={"preferred_language": "es", "preferred_theme": "dark"}
    )
    assert r_no_csrf.status_code == 403
    assert r_no_csrf.json()["detail"] == "CSRF token inválido o ausente."
