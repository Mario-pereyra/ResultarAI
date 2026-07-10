"""Heuristica de instruccion embebida en adjuntos (d14, tarea 4.3 — ANEXO §4.3 punto 3).

Modulo propio (no en `sanitize.py`): la sanitizacion TRANSFORMA el texto; esto solo
DETECTA — corre despues de sanitizar (asi los patrones no se evaden con zero-width ni
homoglifos descompuestos) y produce flags que **no bloquean**: los falsos positivos de
un clasificador no justifican bloqueo automatico en V1 (ANEXO §4.3). El pipeline
(`extraction.py`) persiste los flags en `scan_result["injection_flags"]` del adjunto;
el frontend (tarea 8.2) los muestra como advertencia "Posible instruccion embebida"
(§10) y la traza Langfuse los recoge de ahi. El adjunto sigue su curso a `ready`.

Que detecta (lista razonable ES/EN, deliberadamente acotada — cada patron esta pensado
para frases DIRIGIDAS a la IA, tolerando falsos positivos porque solo advierten):

- **Ordenes de ignorar/olvidar instrucciones** ("ignorá las instrucciones", "ignore
  previous instructions", "disregard the above rules", "olvidá todo lo anterior",
  "forget all previous…").
- **Referencias al system prompt** ("system prompt" — un documento de negocio
  legitimo no habla del system prompt del asistente).
- **Redefinicion de identidad/rol** ("actuá como", "you are now", "ahora sos/eres",
  "act as if you…").
- **Instrucciones nuevas** ("nuevas instrucciones", "new instructions").
- **Exfiltracion del prompt** ("revelá tu prompt", "reveal your system prompt").
- **Marcador de escalacion** (`ESCALATION_MARKER`, importado de `_marker` — fuente
  unica del literal): un documento NO debe poder disparar la escalacion de modelo. La
  escalacion solo existe en la SALIDA del modelo (camino de d13); dentro de un adjunto
  el marcador es dato: queda envuelto por el spotlight (tarea 4.2), se flaggea aca y
  jamas genera un evento de escalacion.

Cada flag lleva tipo, patron, evidencia (fragmento con contexto) y posicion aproximada
(linea 1-based + offset de caracter). Para mantener `scan_result` compacto se reporta
la PRIMERA ocurrencia de cada patron (la advertencia al usuario es por adjunto, no por
ocurrencia; Admin ve el detalle suficiente para auditar).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from resultarai.app.use_cases.chat._marker import ESCALATION_MARKER

__all__ = [
    "FLAG_EMBEDDED_INSTRUCTION",
    "FLAG_ESCALATION_MARKER",
    "InjectionFlag",
    "scan_for_injection",
]

FLAG_EMBEDDED_INSTRUCTION = "embedded_instruction"
FLAG_ESCALATION_MARKER = "escalation_marker"

# Contexto de evidencia alrededor del match (caracteres hacia cada lado).
_EVIDENCE_CONTEXT_CHARS = 40

# Patrones de instruccion dirigida a la IA (case-insensitive). `(?:\S+\s+){0,3}` acota
# el hueco entre el verbo y el objeto a pocas palabras (evita matches kilometricos).
_RAW_INSTRUCTION_PATTERNS: tuple[tuple[str, str], ...] = (
    # ES: "ignorá las instrucciones", "ignora todas las instrucciones previas"
    ("es_ignore_instructions", r"ignor\S*\s+(?:\S+\s+){0,3}instrucciones"),
    # ES: "olvidá (todo) lo anterior/dicho/previo"
    ("es_forget_previous", r"olvid\S*\s+(?:todo\s+)?lo\s+(?:anterior|dicho|previo)"),
    # ES: "actuá como" / "actúa como" / "actua como" (redefinicion de rol)
    ("es_act_as", r"act(?:u[aá]|úa)\s+como"),
    # ES: "ahora sos/eres…", "eres/sos ahora…" (redefinicion de identidad)
    ("es_you_are_now", r"(?:ahora\s+(?:sos|eres)|(?:eres|sos)\s+ahora)\b"),
    # ES: "nuevas instrucciones"
    ("es_new_instructions", r"nuevas\s+instrucciones"),
    # ES: "revelá/mostrá/imprimí … prompt" (exfiltracion)
    ("es_reveal_prompt", r"(?:revel[aá]|mostr[aá]|muestra|imprim[ií])\s+(?:\S+\s+){0,2}prompt"),
    # EN: "ignore previous/all prior instructions"
    ("en_ignore_instructions", r"ignore\s+(?:\S+\s+){0,3}instructions"),
    # EN: "disregard the above instructions/rules/prompt"
    ("en_disregard", r"disregard\s+(?:\S+\s+){0,3}(?:instructions|rules|prompts?)"),
    # EN: "forget all previous/prior/earlier…", "forget everything"
    ("en_forget_previous", r"forget\s+(?:all\s+)?(?:previous|prior|earlier|everything)"),
    # EN: "you are now…" (redefinicion de identidad)
    ("en_you_are_now", r"you\s+are\s+now\b"),
    # EN: "act as if you…", "act as a system/an AI/the system"
    ("en_act_as", r"act\s+as\s+(?:if\s+you|an?\s+(?:ai|system|assistant)|the\s+system)"),
    # EN: "new instructions"
    ("en_new_instructions", r"new\s+instructions"),
    # ES+EN: mencion del system prompt
    ("system_prompt", r"system\s*prompt"),
)

_INSTRUCTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (pattern_id, re.compile(raw, re.IGNORECASE)) for pattern_id, raw in _RAW_INSTRUCTION_PATTERNS
)


@dataclass(frozen=True)
class InjectionFlag:
    """Hallazgo de la heuristica: tipo + patron + evidencia + posicion aproximada."""

    flag_type: str  # FLAG_EMBEDDED_INSTRUCTION | FLAG_ESCALATION_MARKER
    pattern_id: str
    evidence: str  # fragmento con contexto alrededor del match
    line: int  # 1-based
    offset: int  # offset de caracter en el texto completo

    def to_dict(self) -> dict[str, str | int]:
        """Forma JSON-serializable para `scan_result` (JSONB de `b04`)."""
        return {
            "flag_type": self.flag_type,
            "pattern_id": self.pattern_id,
            "evidence": self.evidence,
            "line": self.line,
            "offset": self.offset,
        }


def scan_for_injection(text: str) -> list[InjectionFlag]:
    """Escanea el texto (ya sanitizado) y devuelve los flags de inyeccion detectados.

    Primera ocurrencia por patron (ver docstring del modulo). Lista vacia = limpio.
    NUNCA lanza ni bloquea: la decision de mostrar advertencia es del frontend y la
    persistencia del flag es del pipeline.
    """
    flags: list[InjectionFlag] = []

    for pattern_id, pattern in _INSTRUCTION_PATTERNS:
        match = pattern.search(text)
        if match is not None:
            flags.append(
                _build_flag(text, FLAG_EMBEDDED_INSTRUCTION, pattern_id, match.start(), match.end())
            )

    marker_offset = text.find(ESCALATION_MARKER)
    if marker_offset != -1:
        flags.append(
            _build_flag(
                text,
                FLAG_ESCALATION_MARKER,
                FLAG_ESCALATION_MARKER,
                marker_offset,
                marker_offset + len(ESCALATION_MARKER),
            )
        )

    return flags


def _build_flag(text: str, flag_type: str, pattern_id: str, start: int, end: int) -> InjectionFlag:
    """Arma el flag con evidencia contextual y posicion (linea 1-based + offset)."""
    context_start = max(0, start - _EVIDENCE_CONTEXT_CHARS)
    context_end = min(len(text), end + _EVIDENCE_CONTEXT_CHARS)
    evidence = " ".join(text[context_start:context_end].split())
    line = text.count("\n", 0, start) + 1
    return InjectionFlag(
        flag_type=flag_type,
        pattern_id=pattern_id,
        evidence=evidence,
        line=line,
        offset=start,
    )
