"""Proveedor FastAPI de `AttachmentsConfig` (d14), compartido entre routers.

Vive en un modulo NEUTRAL (no en `app/api/attachments.py`) para que tanto
`app/api/attachments.py` como `app/api/chat.py` (envio de mensajes con adjuntos, tarea
6.3) lo importen sin que los dos routers de API terminen importandose entre si:
`app/api/attachments.py` ya importa `get_registries` DESDE `app/api/chat.py` (mismo
patron que `get_turn_stream_registry` en `app/api/chat_stream.py`), asi que si
`get_attachments_config` viviera en `app/api/attachments.py`, `chat.py` importandolo de
vuelta crearia un ciclo. Este modulo rompe esa dependencia circular.
"""

from __future__ import annotations

from resultarai.app.attachments.config import AttachmentsConfig

__all__ = ["get_attachments_config"]


def get_attachments_config() -> AttachmentsConfig:
    """Proveedor inyectable de la config de adjuntos (por defecto, desde entorno).

    Mismo patron que `get_session_config`: los tests la sobreescriben via
    `app.dependency_overrides` para apuntar `storage_dir` a un directorio temporal y
    fijar limites/presupuestos chicos.
    """
    return AttachmentsConfig.from_env()
