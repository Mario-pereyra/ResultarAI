"""Sanitizacion pre-insercion del texto extraido (d14, tarea 4.1 — ANEXO §4.3 punto 2).

Funciones **puras** que operan SOBRE el texto ya extraido por los adapters
`extraction_*` (paso [5] del pipeline, ANEXO §8), antes de que ese `full_text` se
persista y de que el escaneo N2/N3 (tarea 5.x) o la composicion del `inserted_text`
(tarea 6.x) lo consuman. Remueve los vectores de *smuggling* de instrucciones que un
documento hostil puede esconder del ojo humano pero que el modelo si leeria:

1. **Comentarios HTML/XML** (``<!-- … -->``): texto invisible en el render del
   documento pero presente en la extraccion (tipico de DOCX→HTML→Markdown y XML).
   Solo se remueven comentarios BIEN FORMADOS (con cierre): un ``<!--`` sin cierre es
   texto visible para el modelo y removerlo hasta el final corromperia contenido
   legitimo.
2. **Caracteres invisibles**: toda la categoria Unicode ``Cf`` (format) — zero-width
   space/non-joiner/joiner (U+200B/C/D), BOM/ZWNBSP (U+FEFF), word joiner (U+2060),
   soft hyphen (U+00AD) y los controles bidi (U+202A-E, U+2066-69, usados en ataques
   de reordenamiento visual) — y toda la categoria ``Cc`` (control) **excepto**
   ``\\n`` y ``\\t``. Un ``\\r`` se remueve como control, asi ``\\r\\n`` colapsa a
   ``\\n`` (normalizacion de saltos de linea gratis). Remover ``Cf`` completo es
   deliberadamente agresivo: en el dominio del producto (espanol/es-BO, ERP) ningun
   caracter de formato invisible es contenido legitimo.
3. **Normalizacion Unicode NFC** contra homoglifos por descomposicion (una ``o`` +
   acento combinante U+0301 se compone a ``ó``): asi los patrones del escaneo
   heuristico (tarea 4.3) y N2/N3 (tarea 5.x) matchean sobre una forma canonica.

El orden importa: invisibles PRIMERO (un comentario "partido" por zero-width, p. ej.
``<!​--``, se recompone y cae en el paso 2), comentarios despues, NFC al final (NFC
nunca produce caracteres ``Cc``/``Cf`` ni secuencias ``<!--`` nuevas).

Lo que esta sanitizacion **NO** toca: el contenido oculto estructural (hojas/columnas
ocultas, runs ``vanish``) que los extractores ya marcaron ``[oculta]`` — ese contenido
se CONSERVA visible con su marcador (ANEXO §4.3 punto 2: se marca, no se silencia).
Tampoco remueve el marcador de escalacion ni patrones de instruccion: eso es
DETECCION (heuristics.py, tarea 4.3), no transformacion — el texto de un adjunto es
dato y se preserva; solo se eliminan artefactos invisibles/no imprimibles.

El conteo de artefactos removidos se devuelve en el resultado (barato: se calcula al
pasar) para telemetria en `scan_result` — nunca bloquea ni decide politica.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

__all__ = [
    "SanitizationResult",
    "sanitize_extracted_text",
    "strip_html_comments",
    "strip_invisible_characters",
]

# Comentario HTML/XML bien formado, incluso multilinea (DOTALL); non-greedy para no
# tragar contenido entre dos comentarios distintos.
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)

# Controles preservados: los unicos con semantica legitima en texto plano extraido.
_KEPT_CONTROLS = frozenset({"\n", "\t"})

# Categorias Unicode removidas: Cc (control) salvo _KEPT_CONTROLS, Cf (format:
# zero-width, BOM, soft hyphen, controles bidi).
_REMOVED_CATEGORIES = frozenset({"Cc", "Cf"})


@dataclass(frozen=True)
class SanitizationResult:
    """Texto sanitizado + conteo de artefactos removidos (telemetria, no politica)."""

    text: str
    removed_html_comments: int
    removed_zero_width: int  # categoria Cf completa (zero-width, BOM, bidi, soft hyphen)
    removed_control_chars: int  # categoria Cc, excepto \n y \t
    nfc_changed: bool  # True si la normalizacion NFC altero el texto

    @property
    def removed_anything(self) -> bool:
        """True si algun paso altero el texto (util para decidir si registrar)."""
        return (
            self.removed_html_comments > 0
            or self.removed_zero_width > 0
            or self.removed_control_chars > 0
            or self.nfc_changed
        )

    def artifacts_dict(self) -> dict[str, int | bool]:
        """Forma JSON-serializable para `scan_result` (telemetria de Admin)."""
        return {
            "html_comments": self.removed_html_comments,
            "zero_width": self.removed_zero_width,
            "control_chars": self.removed_control_chars,
            "nfc_changed": self.nfc_changed,
        }


def strip_invisible_characters(text: str) -> tuple[str, int, int]:
    """Remueve caracteres de formato (Cf) y de control (Cc, salvo ``\\n``/``\\t``).

    Devuelve ``(texto, removidos_cf, removidos_cc)``. Una sola pasada.
    """
    kept: list[str] = []
    removed_format = 0
    removed_control = 0
    for char in text:
        if char in _KEPT_CONTROLS:
            kept.append(char)
            continue
        category = unicodedata.category(char)
        if category not in _REMOVED_CATEGORIES:
            kept.append(char)
        elif category == "Cf":
            removed_format += 1
        else:
            removed_control += 1
    if not removed_format and not removed_control:
        return text, 0, 0
    return "".join(kept), removed_format, removed_control


def strip_html_comments(text: str) -> tuple[str, int]:
    """Remueve comentarios HTML/XML bien formados. Devuelve ``(texto, removidos)``."""
    stripped, count = _HTML_COMMENT.subn("", text)
    return stripped, count


def sanitize_extracted_text(text: str) -> SanitizationResult:
    """Sanitiza el texto extraido: invisibles → comentarios → NFC (ver docstring).

    Funcion pura y determinista (P2 del ANEXO: la extraccion sanitizada se almacena
    una sola vez y no cambia entre corridas). El marcador ``[oculta]`` de los
    extractores es ASCII imprimible: pasa intacto por los tres pasos.
    """
    stripped, removed_format, removed_control = strip_invisible_characters(text)
    without_comments, removed_comments = strip_html_comments(stripped)
    normalized = unicodedata.normalize("NFC", without_comments)
    return SanitizationResult(
        text=normalized,
        removed_html_comments=removed_comments,
        removed_zero_width=removed_format,
        removed_control_chars=removed_control,
        nfc_changed=normalized != without_comments,
    )
