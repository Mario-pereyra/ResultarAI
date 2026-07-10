"""Escaneo de niveles de datos N2/N3 sobre la extraccion (d14, tareas 5.1-5.3 — ANEXO §4.4).

Corre sobre la **extraccion YA sanitizada** (`sanitize.py`, paso [5] del ANEXO §8), no
sobre el binario: lo unico que importa proteger es el texto que viajaria al LLM (§4.4).
Dos capas, con la precedencia del ANEXO (**N3 gana sobre N2**):

- **N3 — secretos → bloqueo.** Regex deterministas propios (claves API, JWT, private
  keys, cadenas de conexion con credencial). Un hallazgo N3 deja el adjunto en estado
  `blocked` (CheckConstraint de `attachments` en `b04`): NO enviable hasta quitar el
  secreto del archivo (mensaje "N3 (credenciales)" del ANEXO §10). El secreto NUNCA se
  persiste en claro: se guarda tipo + linea + un fragmento **redactado** (p. ej.
  `Password=***`).
- **N2 — PII → confirmacion auditada.** `presidio-analyzer` con modelo spaCy de espanol
  (PII general: emails, telefonos, nombres) mas reconocedores propios ES/BO (CI, NIT,
  telefono boliviano) que usan palabras de **contexto** para no marcar cualquier numero
  de una planilla. Un hallazgo N2 deja el adjunto `ready` PERO marca
  `requires_test_data_confirmation`: el envio queda bloqueado hasta que el dueno confirme
  "son datos de prueba" (endpoint auditado, `confirmation.py`) o quite el adjunto. La PII
  NO se persiste en claro: se guarda tipo + cantidad + lineas aproximadas.

## Forma documentada de `scan_result` (JSONB de `b04`)

`scan_result` es el metadato consultable del adjunto (visible para Admin en telemetria,
ANEXO §4.4). Es aditivo: cada etapa del pipeline agrega su clave sin pisar las demas.
Todas las claves son opcionales; su ausencia significa "esa etapa no encontro nada". Un
adjunto totalmente limpio tiene `scan_result = NULL` (distingue "limpio" de "escaneado
con hallazgos" de un vistazo). Shape completo::

    {
      # --- extraccion (extraction.py, camino de error; excluyente con el resto) ---
      "extraction_error": {"error_code": str, "params": {...}},

      # --- sanitizacion (sanitize.py, tarea 4.1) ---
      "sanitization": {"html_comments": int, "zero_width": int,
                       "control_chars": int, "nfc_changed": bool},

      # --- anti prompt-injection (heuristics.py, tarea 4.3) ---
      "injection_flags": [{"flag_type": str, "pattern_id": str,
                           "evidence": str, "line": int, "offset": int}],

      # --- N3 secretos (data_scan.scan_for_secrets, tarea 5.1) ---
      "n3_findings": [{"secret_type": str, "line": int, "redacted": str}],

      # --- N2 PII (data_scan.scan_for_pii, tarea 5.2) ---
      "pii_findings": [{"entity_type": str, "count": int, "lines": [int]}],
      "requires_test_data_confirmation": bool,   # True = pendiente; False = confirmada

      # --- confirmacion auditada (confirmation.confirm_test_data, tarea 5.2) ---
      "test_data_confirmation": {"confirmed_by": str, "confirmed_at": str (ISO 8601),
                                 "findings_summary": {entity_type: count}}
    }

## Donde corre el analyzer de Presidio y por que

El `AnalyzerEngine` se construye como **singleton perezoso** (`_get_analyzer`), NO en
import-time del app (design decision 5: "el analyzer NO se carga en import-time"). El
import de `presidio-analyzer`/`spacy` esta **diferido** dentro de `_build_analyzer`: el
arranque del app y el hot path del chat (que jamas tocan adjuntos) no pagan ni el import
ni la carga del modelo. El escaneo corre en el **proceso del app** dentro de
`extract_attachment` (paso [6] del ANEXO §8), justo despues de sanitizar y de la
heuristica de inyeccion, sobre el mismo texto limpio — NO dentro del worker aislado de
extraccion. Razon: el worker es un proceso `forkserver` fresco por adjunto; cargar ahi el
modelo spaCy (~13 MB) lo recargaria en CADA extraccion, anulando el singleton. La
extraccion/escaneo ocurre al SUBIR el adjunto (flujo aparte del streaming del chat), asi
que el singleton en el app ya esta "fuera del hot path del chat" y se reutiliza entre
subidas. La primera subida que necesite escaneo N2 paga la carga del modelo una vez.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from presidio_analyzer import AnalyzerEngine, RecognizerResult

    from resultarai.adapters.persistence_postgres.models import Attachment

    # Redactor de un secreto N3: recibe el match y devuelve un fragmento sin el dato en claro.
    _Redactor = Callable[[re.Match[str]], str]

__all__ = [
    "PiiFinding",
    "SecretFinding",
    "is_sendable",
    "scan_for_pii",
    "scan_for_secrets",
]

# Estado de `b04` para "extraido, sanitizado y escaneado, enviable" (CheckConstraint de
# attachments). Se replica el literal aca (no se importa de extraction.py) porque
# extraction.py importa ESTE modulo: la dependencia va en un solo sentido.
_STATUS_READY = "ready"


# ---------------------------------------------------------------------------------------
# N3 — secretos (regex deterministas propios, tarea 5.1)
# ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class SecretFinding:
    """Hallazgo N3: tipo de secreto + linea (1-based) + fragmento REDACTADO.

    `redacted` nunca contiene el secreto en claro: para cadenas de conexion conserva la
    etiqueta (`Password=***`); para claves/JWT conserva solo el prefijo identificable
    (`sk-***`, `eyJ...***`); para private keys, el marcador `-----BEGIN … PRIVATE KEY-----`
    (que no es material secreto).
    """

    secret_type: str
    line: int
    redacted: str

    def to_dict(self) -> dict[str, str | int]:
        """Forma JSON-serializable para `scan_result["n3_findings"]`."""
        return {"secret_type": self.secret_type, "line": self.line, "redacted": self.redacted}


def _redact_keep_prefix(match: re.Match[str], prefix_len: int) -> str:
    """Redaccion de una clave/token: conserva `prefix_len` chars y enmascara el resto."""
    return match.group(0)[:prefix_len] + "***"


def _redact_connection_credential(match: re.Match[str]) -> str:
    """Redaccion de `Password=valor` (o pwd/senha/contrasena): conserva etiqueta+separador."""
    return f"{match.group('key')}{match.group('sep')}***"


def _redact_connection_uri(match: re.Match[str]) -> str:
    """Redaccion de `esquema://user:pass@host`: enmascara solo la contrasena."""
    return f"{match.group('scheme')}://{match.group('user')}:***@{match.group('host')}"


def _redact_marker(match: re.Match[str]) -> str:
    """El propio marcador (p. ej. `-----BEGIN RSA PRIVATE KEY-----`) no es material secreto."""
    return match.group(0)


# Patrones de FABRICA (documentados en codigo, ANEXO §4.4). Cada entrada:
# (secret_type, patron compilado, funcion de redaccion). El orden es estable para que la
# telemetria sea determinista. `re.IGNORECASE` solo donde el literal lo requiere.
_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str], _Redactor], ...] = (
    # Claves API de proveedores conocidos (prefijos + token largo).
    (
        "openai_api_key",
        re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
        lambda m: _redact_keep_prefix(m, 3),
    ),
    (
        "aws_access_key",
        re.compile(r"\b(?:AKIA|ASIA|AGPA|AIDA|AROA|AIPA)[A-Z0-9]{16}\b"),
        lambda m: _redact_keep_prefix(m, 4),
    ),
    (
        "github_token",
        re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}\b"),
        lambda m: _redact_keep_prefix(m, 4),
    ),
    (
        "github_pat",
        re.compile(r"\bgithub_pat_[A-Za-z0-9_]{22,}\b"),
        lambda m: _redact_keep_prefix(m, 11),
    ),
    (
        "slack_token",
        re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
        lambda m: _redact_keep_prefix(m, 5),
    ),
    (
        "google_api_key",
        re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
        lambda m: _redact_keep_prefix(m, 4),
    ),
    # JWT: tres segmentos base64url; ancla `eyJ` (base64 de `{"`) reduce falsos positivos.
    (
        "jwt",
        re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b"),
        lambda m: _redact_keep_prefix(m, 3),
    ),
    # Private keys PEM (RSA/EC/DSA/OpenSSH/PGP/cifradas o sin prefijo).
    (
        "private_key",
        re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY-----"),
        _redact_marker,
    ),
    # Cadena de conexion con credencial en clave=valor: Password= / pwd= / senha= /
    # contrasena= / contraseña= (con `=` o `:`, valor entre comillas o hasta espacio).
    (
        "connection_password",
        re.compile(
            r"(?i)\b(?P<key>password|pwd|passwd|senha|contrase(?:ñ|n)a)\s*(?P<sep>[=:])\s*"
            r"(?P<val>\"[^\"]*\"|'[^']*'|\S+)"
        ),
        _redact_connection_credential,
    ),
    # URI con credencial embebida: esquema://user:pass@host.
    (
        "connection_uri",
        re.compile(
            r"\b(?P<scheme>[a-zA-Z][a-zA-Z0-9+.\-]*)://(?P<user>[^\s:/@]+):"
            r"(?P<pw>[^\s:/@]+)@(?P<host>[^\s/]+)"
        ),
        _redact_connection_uri,
    ),
)


def scan_for_secrets(text: str, extra_patterns: tuple[str, ...] = ()) -> list[SecretFinding]:
    """Escanea `text` (ya sanitizado) por secretos N3. Primera ocurrencia por patron.

    `extra_patterns` son regex adicionales configurables por instancia (ANEXO §4.4: "la
    LISTA de patrones extra puede venir de config"); sus coincidencias se guardan
    TOTALMENTE redactadas (`***`) porque su estructura es desconocida. Un patron extra
    invalido se ignora en silencio (no debe tumbar el pipeline por un typo de config).
    Nunca lanza ni bloquea por si mismo: la decision de estado la toma `extract_attachment`.
    """
    findings: list[SecretFinding] = []

    for secret_type, pattern, redactor in _SECRET_PATTERNS:
        match = pattern.search(text)
        if match is not None:
            findings.append(
                SecretFinding(
                    secret_type=secret_type,
                    line=_line_of(text, match.start()),
                    redacted=redactor(match),
                )
            )

    for index, raw in enumerate(extra_patterns):
        try:
            compiled = re.compile(raw)
        except re.error:
            continue
        match = compiled.search(text)
        if match is not None:
            findings.append(
                SecretFinding(
                    secret_type=f"custom_{index + 1}",
                    line=_line_of(text, match.start()),
                    redacted="***",
                )
            )

    return findings


def _line_of(text: str, offset: int) -> int:
    """Numero de linea 1-based del caracter en `offset` (mismo criterio que heuristics)."""
    return text.count("\n", 0, offset) + 1


# ---------------------------------------------------------------------------------------
# N2 — PII (Presidio + reconocedores propios ES/BO, tarea 5.2)
# ---------------------------------------------------------------------------------------

# Entidades que reportamos (acota el ruido de los reconocedores US-centricos de fabrica de
# Presidio a lo que interesa en el dominio ES-BO). Las BO_* son reconocedores propios.
_PII_ENTITIES = ("EMAIL_ADDRESS", "PHONE_NUMBER", "PERSON", "BO_CI", "BO_NIT", "BO_PHONE")

# Umbral de confianza: emails/nombres pasan holgados; los numeros BO_* solo superan el
# umbral cuando el REALCE POR CONTEXTO (palabras "CI"/"NIT"/"celular" cerca) los sube — un
# numero cualquiera de una planilla queda por debajo y no se reporta (reduce falsos
# positivos, requisito explicito de la tarea 5.2).
_PII_SCORE_THRESHOLD = 0.4

_analyzer: AnalyzerEngine | None = None
_analyzer_lock = threading.Lock()


@dataclass(frozen=True)
class PiiFinding:
    """Hallazgo N2 agregado por tipo: entidad + cantidad + lineas aproximadas.

    NUNCA guarda el dato en claro (ANEXO §4.4): solo el tipo de entidad, cuantas
    ocurrencias y en que lineas (1-based) — suficiente para la advertencia "N2 (PII)" del
    §10 y para la telemetria de Admin.
    """

    entity_type: str
    count: int
    lines: tuple[int, ...]

    def to_dict(self) -> dict[str, str | int | list[int]]:
        """Forma JSON-serializable para `scan_result["pii_findings"]`."""
        return {"entity_type": self.entity_type, "count": self.count, "lines": list(self.lines)}


def scan_for_pii(text: str) -> list[PiiFinding]:
    """Escanea `text` (ya sanitizado) por PII N2 con Presidio (idioma es) + reconocedores BO.

    Devuelve hallazgos agregados por tipo de entidad (sin el dato en claro). Lista vacia =
    sin PII. Carga el analyzer perezosamente en la primera llamada (ver docstring del
    modulo). Nunca lanza ni bloquea: N2 solo exige confirmacion, jamas bloquea.
    """
    if not text.strip():
        return []

    analyzer = _get_analyzer()
    results = analyzer.analyze(
        text=text,
        language="es",
        entities=list(_PII_ENTITIES),
        score_threshold=_PII_SCORE_THRESHOLD,
    )
    kept = _dedupe_overlaps(results)

    lines_by_type: dict[str, list[int]] = {}
    for result in kept:
        lines_by_type.setdefault(result.entity_type, []).append(_line_of(text, result.start))

    return [
        PiiFinding(entity_type=entity_type, count=len(lines), lines=tuple(sorted(set(lines))))
        for entity_type, lines in sorted(lines_by_type.items())
    ]


def _dedupe_overlaps(results: list[RecognizerResult]) -> list[RecognizerResult]:
    """Resuelve solapamientos entre reconocedores (p. ej. BO_PHONE vs PHONE_NUMBER sobre el
    mismo numero): greedy por score descendente, descarta cualquier hallazgo que solape uno
    ya conservado. Evita contar dos veces el mismo dato.
    """
    kept: list[RecognizerResult] = []
    for result in sorted(results, key=lambda r: (-r.score, -(r.end - r.start))):
        if any(not (result.end <= k.start or result.start >= k.end) for k in kept):
            continue
        kept.append(result)
    return kept


def _get_analyzer() -> AnalyzerEngine:
    """Devuelve el `AnalyzerEngine` singleton, construyendolo (con lock) en la 1ra llamada."""
    global _analyzer
    cached = _analyzer
    if cached is not None:
        return cached
    with _analyzer_lock:
        cached = _analyzer
        if cached is None:
            cached = _build_analyzer()
            _analyzer = cached
        return cached


def _build_analyzer() -> AnalyzerEngine:
    """Construye el `AnalyzerEngine` con NLP de espanol + reconocedores propios ES/BO.

    Import DIFERIDO de presidio/spacy (ver docstring del modulo): asi el costo de import y
    de carga del modelo no lo paga el arranque del app ni el hot path del chat.
    """
    from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
    from presidio_analyzer.nlp_engine import NlpEngineProvider

    configuration = {
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "es", "model_name": "es_core_news_sm"}],
    }
    nlp_engine = NlpEngineProvider(nlp_configuration=configuration).create_engine()
    analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["es"])

    # Reconocedores propios ES/BO: numeros que solo son PII cuando hay contexto cerca. El
    # score base bajo (0.1) queda por debajo del umbral; el realce por contexto lo sube.
    ci = PatternRecognizer(
        supported_entity="BO_CI",
        patterns=[Pattern(name="bo_ci", regex=r"\b\d{7,8}\b", score=0.1)],
        context=["ci", "carnet", "cedula", "cédula"],
        supported_language="es",
    )
    nit = PatternRecognizer(
        supported_entity="BO_NIT",
        patterns=[Pattern(name="bo_nit", regex=r"\b\d{7,12}\b", score=0.1)],
        context=["nit"],
        supported_language="es",
    )
    phone = PatternRecognizer(
        supported_entity="BO_PHONE",
        patterns=[Pattern(name="bo_phone", regex=r"\b(?:\+?591[-\s]?)?[67]\d{7}\b", score=0.3)],
        context=["telefono", "teléfono", "celular", "cel", "whatsapp", "número"],
        supported_language="es",
    )
    for recognizer in (ci, nit, phone):
        analyzer.registry.add_recognizer(recognizer)

    return analyzer


# ---------------------------------------------------------------------------------------
# Sendabilidad (helper para la composicion del mensaje, tarea 6.3)
# ---------------------------------------------------------------------------------------


def is_sendable(attachment: Attachment) -> bool:
    """True si el adjunto puede enviarse al modelo; helper para la composicion (tarea 6.3).

    Reglas (ANEXO §4.4): bloqueado por N3 -> no; N2 con PII sin confirmar -> no; `ready`
    limpio o con N2 ya confirmado -> si. Cualquier estado que no sea `ready` (uploaded /
    extracting / blocked / error) no es enviable.
    """
    if attachment.status != _STATUS_READY:
        return False
    scan_result = attachment.scan_result or {}
    return not scan_result.get("requires_test_data_confirmation", False)
