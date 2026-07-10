"""Proteccion zip-bomb para OOXML (d14, tarea 2.4).

Los OOXML (`.xlsx`/`.docx`) son contenedores ZIP: un archivo chico puede declarar (o
expandir a) cientos de MB y agotar la memoria de la plataforma al parsearse. El ANEXO
§4.1 punto 4 exige abortar si el descomprimido supera un tope (default 100 MB) o si el
ratio comprimido:descomprimido supera un tope (default 50:1). Ambos son **config**
(`AttachmentsConfig`), no constantes.

Enfoque (documentado, por que es seguro en memoria):

1. **Chequeo barato del indice** (directorio central del ZIP): sumar `file_size`
   (descomprimido DECLARADO) y `compress_size` de cada entrada. Si el total declarado
   supera el tope, o el ratio declarado supera el tope, se aborta **sin descomprimir un
   solo byte** — con solo leer el indice. Esto atrapa la zip-bomb clasica (una entrada
   que declara gigabytes desde unos KB) de forma barata.

2. **Verificacion en streaming con tope de bytes leidos** (defensa en profundidad): el
   indice PUEDE mentir, asi que ademas se descomprime cada entrada en trozos de tamano
   fijo llevando un contador global; si el total leido cruza el tope se aborta al
   instante. Nunca se materializa mas de un trozo (memoria O(trozo)); el bucle jamas
   acumula el binario descomprimido completo. En CPython `zipfile` acota la salida de
   cada miembro a su `file_size` declarado, de modo que este paso confirma el indice y
   deja el limite explicito por si esa garantia no aplicara (ZIP64/variantes).

El worker aislado de extraccion (tarea 2.5) es el respaldo final: cualquier bomba que
lograra colarse igual queda contenida por su timeout + `RLIMIT_AS`.
"""

from __future__ import annotations

import io
import zipfile

from resultarai.app.attachments.errors import ZipBombSuspectedError

# Trozo de lectura del streaming de verificacion: memoria de trabajo O(este valor).
_READ_CHUNK_BYTES = 64 * 1024

# Piso para aplicar el chequeo de ratio DECLARADO: por debajo de este descomprimido total
# el ratio no es senal (un OOXML minusculo con XML repetitivo puede dar ratios altos sin
# ser bomba). Una bomba real que se acerca al tope de tamano lo supera con creces, asi que
# el piso no debilita la deteccion. No es config: es un guarda interno anti falso positivo.
_RATIO_MIN_UNCOMPRESSED_BYTES = 256 * 1024


def inspect_ooxml_for_zip_bomb(
    content: bytes,
    *,
    max_uncompressed_bytes: int,
    max_ratio: float,
) -> None:
    """Aborta con `ZipBombSuspectedError` si `content` (un OOXML) parece zip-bomb.

    No devuelve nada si el OOXML es razonable. Un binario que ni siquiera es un ZIP valido
    NO se trata aca como bomba: se ignora (`return`) y la extraccion aislada lo llevara a
    estado `error` con su causa (la validacion de firma de subida ya verifico el magic ZIP,
    pero un ZIP estructuralmente roto no es una bomba).
    """
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            infos = archive.infolist()

            declared_uncompressed = sum(info.file_size for info in infos)
            declared_compressed = sum(info.compress_size for info in infos)

            # (1) Chequeo barato del indice: sin descomprimir nada.
            if declared_uncompressed > max_uncompressed_bytes:
                raise ZipBombSuspectedError(
                    reason="declared_size",
                    declared_uncompressed_bytes=declared_uncompressed,
                    limit_bytes=max_uncompressed_bytes,
                )

            if (
                declared_uncompressed >= _RATIO_MIN_UNCOMPRESSED_BYTES
                and declared_compressed > 0
                and declared_uncompressed / declared_compressed > max_ratio
            ):
                raise ZipBombSuspectedError(
                    reason="declared_ratio",
                    ratio=round(declared_uncompressed / declared_compressed, 2),
                    limit_ratio=max_ratio,
                )

            # (2) Verificacion en streaming con tope de bytes leidos (defensa en prof.).
            _verify_expansion_streaming(archive, infos, max_uncompressed_bytes)
    except zipfile.BadZipFile:
        return


def _verify_expansion_streaming(
    archive: zipfile.ZipFile,
    infos: list[zipfile.ZipInfo],
    max_uncompressed_bytes: int,
) -> None:
    """Descomprime en trozos con contador global; aborta si cruza el tope de bytes."""
    total_read = 0
    for info in infos:
        with archive.open(info) as member:
            while True:
                chunk = member.read(_READ_CHUNK_BYTES)
                if not chunk:
                    break
                total_read += len(chunk)
                if total_read > max_uncompressed_bytes:
                    raise ZipBombSuspectedError(
                        reason="expanded_size",
                        limit_bytes=max_uncompressed_bytes,
                    )
