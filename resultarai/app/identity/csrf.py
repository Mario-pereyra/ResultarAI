"""Protección CSRF por token de doble envío (d11, tarea 2.6).

Patrón *double submit* (design Decision 5): junto con la sesión se emite un token
CSRF aleatorio en una cookie **no** ``HttpOnly`` (para que el frontend pueda
leerla y reenviarla). Toda mutación debe incluir ese valor en el header
``X-CSRF-Token``; el backend lo compara contra la cookie con
``secrets.compare_digest`` (tiempo constante). Complementa ``SameSite=Lax`` de la
cookie de sesión sin depender solo de él.
"""

from __future__ import annotations

import secrets

from fastapi import HTTPException, Request, Response

__all__ = [
    "CSRF_COOKIE",
    "CSRF_HEADER",
    "issue_csrf_token",
    "require_csrf",
    "set_csrf_cookie",
    "verify_csrf",
]

# Nombre de la cookie y del header CSRF (la sección 3 los reutiliza).
CSRF_COOKIE = "resultarai_csrf"
CSRF_HEADER = "X-CSRF-Token"

# Bytes de entropía del token CSRF (256 bits).
_TOKEN_BYTES = 32


def issue_csrf_token() -> str:
    """Genera un token CSRF aleatorio de alta entropía."""
    return secrets.token_urlsafe(_TOKEN_BYTES)


def verify_csrf(header_value: str | None, cookie_value: str | None) -> bool:
    """Compara el header contra la cookie en tiempo constante.

    Devuelve ``True`` solo si ambos están presentes y coinciden. La comparación
    usa ``secrets.compare_digest``; jamás ``==`` sobre los tokens.
    """
    if not header_value or not cookie_value:
        return False
    return secrets.compare_digest(header_value, cookie_value)


def set_csrf_cookie(
    response: Response,
    token: str,
    *,
    secure: bool = True,
    max_age: int | None = None,
) -> None:
    """Fija la cookie CSRF: ``Secure`` (según config), **no** ``HttpOnly``.

    Debe ser legible por el frontend para poder reenviar el valor en el header,
    de ahí ``httponly=False``. ``SameSite=Lax`` como la de sesión.
    """
    response.set_cookie(
        key=CSRF_COOKIE,
        value=token,
        max_age=max_age,
        secure=secure,
        httponly=False,
        samesite="lax",
        path="/",
    )


def require_csrf(request: Request) -> None:
    """Dependency FastAPI que exige un token CSRF válido en las mutaciones.

    Lanza 403 si el header ``X-CSRF-Token`` falta o no coincide con la cookie.
    """
    header_value = request.headers.get(CSRF_HEADER)
    cookie_value = request.cookies.get(CSRF_COOKIE)
    if not verify_csrf(header_value, cookie_value):
        raise HTTPException(status_code=403, detail="CSRF token inválido o ausente.")
