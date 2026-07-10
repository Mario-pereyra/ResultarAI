"""Conteo de tokens del proveedor via LiteLLM (d14-attachments, tarea 6.1).

Seam explicito entre `app/attachments`/`app/use_cases/chat` y el gateway de modelos: el
diseño pide "tokenizer del proveedor via gateway b05, no estimacion propia" (ANEXO
§3.1/§8 paso [7]). LiteLLM expone `litellm.token_counter(model=..., text=...)` como
tokenizer generico -- resuelve el tokenizer correcto por `model` cuando lo conoce (p. ej.
tiktoken `cl100k_base` para familias OpenAI-compatibles) y cae a una aproximacion
razonable para modelos que no tiene mapeados explicitamente, como los perfiles
`deepseek/...` de fabrica (`manifests/model_profiles.yaml`) -- DeepSeek no publica hoy un
tokenizer propio integrado a LiteLLM, asi que esta es la mejor aproximacion determinista
disponible sin salir a llamar la API del proveedor solo para contar tokens.

Se expone como funcion de ADAPTER (no un port nuevo en `core/`) porque el conteo de
tokens es un detalle de infraestructura de LiteLLM, igual que `LiteLLMClient` (regla dura
2 de CLAUDE.md: toda llamada a modelo pasa por LiteLLM). `app/attachments` y
`app/use_cases/chat` importan esta funcion en vez de `litellm` directo, preservando la
frontera app -> adapters -> core (regla dura 1) y dejando un unico punto de reemplazo si
el tokenizer real de DeepSeek llega a integrarse a LiteLLM mas adelante.
"""

from __future__ import annotations

import litellm

__all__ = ["count_tokens"]


def count_tokens(text: str, *, model: str) -> int:
    """Cuenta los tokens de `text` con el tokenizer que LiteLLM resuelve para `model`.

    Texto vacio cuenta 0 sin llamar a LiteLLM (evita una llamada trivial en el camino
    mas comun de "adjunto sin texto extraido"). `model` es el `ModelProfile.model` real
    (p. ej. `deepseek/deepseek-v4-flash`, ver `manifests/model_profiles.yaml`), no el
    `id` del perfil -- el llamador resuelve esa traduccion (ver
    `resultarai/app/attachments/insertion.py::resolve_token_counter_model`).
    """
    if not text:
        return 0
    return int(litellm.token_counter(model=model, text=text))
