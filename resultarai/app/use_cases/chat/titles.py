"""Generación automática de títulos de sesión a partir del primer turno.

Tarea 2.2 de d13-chat-conversacion: título determinista a partir del primer
mensaje de usuario, editable por el usuario sin regeneración posterior.
"""

from __future__ import annotations

__all__ = ["generate_session_title"]


def generate_session_title(user_text: str) -> str:
    """Genera un título automático a partir del primer mensaje de usuario.

    Especificación de la tarea 2.2:
    - Colapsa espacios/saltos de línea a espacio simple
    - Recorta a 60 caracteres máximo cortando en el último espacio antes del límite
    - Agrega "…" si hubo recorte
    - Devuelve "Nueva conversación" si el texto queda vacío tras normalizar

    Parámetros:
        user_text: Contenido del primer mensaje de usuario de la sesión.

    Retorna:
        Una cadena única (60 chars máx) apta para persistir en `Session.title`.
    """
    # Colapsa espacios/saltos de línea a espacio simple.
    normalized = " ".join(user_text.split())

    # Si queda vacío tras normalizar, usa el fallback.
    if not normalized:
        return "Nueva conversación"

    # Recorta a 60 caracteres máximo en el último espacio antes del límite.
    max_length = 60
    if len(normalized) <= max_length:
        return normalized

    # Busca el último espacio dentro del límite.
    substring = normalized[:max_length]
    last_space_index = substring.rfind(" ")

    if last_space_index > 0:
        # Hay un espacio dentro del límite; corta justo antes.
        return substring[:last_space_index] + "…"
    else:
        # No hay espacio: corta a 60 y agrega "…" (palabra muy larga).
        return normalized[:max_length] + "…"
