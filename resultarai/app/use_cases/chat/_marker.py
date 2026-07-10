"""Marcador de escalación compartido entre los caminos síncrono y streaming.

Módulo hoja sin dependencias internas: `streaming.py` importa de `turns.py`
(errores de dominio) y ambos necesitan el marcador — tenerlo acá evita el
import circular que aparecería si `turns.py` importara de `streaming.py`.
"""

from __future__ import annotations

ESCALATION_MARKER = "<<<NEEDS_PRO>>>"


def strip_escalation_marker(text: str) -> str:
    """Elimina el literal `<<<NEEDS_PRO>>>` de un texto COMPLETO ya generado.

    Contraparte no-streaming de `filter_escalation_marker` (streaming.py), para
    el camino síncrono (`turns.py`): el gateway de b05 deja el marcador dentro
    de `LLMResponse.text` (solo señala `needs_pro`), así que cualquier punto que
    persista texto de agente debe filtrarlo defensivamente antes del INSERT —
    de lo contrario el marcador quedaría en `Message.content` y saldría por el
    detalle de sesión y los snippets de búsqueda (hallazgo del review 10.1).
    Incondicional por diseño, igual que el filtro de streaming.
    """
    return text.replace(ESCALATION_MARKER, "")
