"""Tests de la proteccion zip-bomb OOXML (d14, tarea 2.4).

Cubre el requirement "Proteccion zip-bomb en OOXML" de `attachments-security`: un OOXML
cuyo ZIP interno expande por encima del tope de tamano o de ratio se aborta leyendo solo el
indice (sin descomprimir ni agotar memoria); un OOXML legitimo pasa; un binario que ni es
ZIP no se trata como bomba.
"""

from __future__ import annotations

import io
import zipfile

import pytest
from openpyxl import Workbook

from resultarai.app.attachments.errors import ZipBombSuspectedError
from resultarai.app.attachments.zip_guard import inspect_ooxml_for_zip_bomb

_MIB = 1024 * 1024


def _zip_with_payload(payload: bytes, *, name: str = "bloat.bin") -> bytes:
    """Crea en memoria un ZIP con una entrada `payload` comprimida con deflate."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(name, payload)
    return buffer.getvalue()


def _legit_xlsx() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet["A1"] = "codigo"
    sheet["A2"] = 1
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_declared_size_over_threshold_aborts_without_decompressing() -> None:
    """Un ZIP que declara un descomprimido enorme se aborta leyendo solo el indice.

    La entrada expande a 64 MiB desde ~64 KiB comprimidos (un zip-bomb tipico). Con el tope
    en 8 MiB, la proteccion lo rechaza por `declared_size` inspeccionando el directorio
    central: nunca materializa los 64 MiB, de modo que no agota memoria de la plataforma.
    """
    bomb = _zip_with_payload(b"\x00" * (64 * _MIB))
    assert len(bomb) < 1 * _MIB  # comprimido chico: la bomba miente en el descomprimido

    with pytest.raises(ZipBombSuspectedError) as exc_info:
        inspect_ooxml_for_zip_bomb(bomb, max_uncompressed_bytes=8 * _MIB, max_ratio=50.0)
    assert exc_info.value.error_code == "zip_bomb_suspected"
    assert exc_info.value.params["reason"] == "declared_size"


def test_lying_ratio_aborts() -> None:
    """Ratio comprimido:descomprimido sobre el tope (indice "mentiroso") se aborta.

    El descomprimido (1 MiB) esta por debajo del tope de tamano (100 MiB), pero el ratio
    (~1000:1) supera el tope de 50:1 -> reason `declared_ratio`.
    """
    payload = _zip_with_payload(b"\x00" * (1 * _MIB))

    with pytest.raises(ZipBombSuspectedError) as exc_info:
        inspect_ooxml_for_zip_bomb(payload, max_uncompressed_bytes=100 * _MIB, max_ratio=50.0)
    assert exc_info.value.params["reason"] == "declared_ratio"


def test_legit_xlsx_passes() -> None:
    """Un .xlsx real (ratio ~4:1, pocos KB) no dispara la proteccion."""
    inspect_ooxml_for_zip_bomb(_legit_xlsx(), max_uncompressed_bytes=100 * _MIB, max_ratio=50.0)


def test_non_zip_content_is_not_treated_as_bomb() -> None:
    """Un binario que ni es ZIP valido no se trata como bomba (lo maneja la extraccion)."""
    inspect_ooxml_for_zip_bomb(b"esto no es un zip", max_uncompressed_bytes=1 * _MIB, max_ratio=2.0)
