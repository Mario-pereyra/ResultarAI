# Design — d14-attachments

## Context

El [ANEXO-ATTACHMENTS](../../../design/ANEXO-ATTACHMENTS.md) es la fuente normativa y ya resuelve el problema a nivel de producto: pipeline por tipo (§2), economía de tokens (§3), seguridad en capas (§4), almacenamiento (§5) y pipeline paso a paso (§8). Está escrito para el stack Node del intento 2026-06 (SheetJS, unpdf, mammoth.js, tesseract.js, file-type, Presidio-en-Node). La [tabla de pivote de docs/07](../../../docs/07-roadmap.md) reemplaza ese stack por Python: openpyxl + python-calamine, pypdf, mammoth (Python), pytesseract (OCR diferido), Presidio + reconocedores propios. El schema de almacenamiento (`attachments`/`extractions`/`message_attachments`, invariantes de inmutabilidad y dedup) ya lo entregó `b04-persistencia-postgres` (capability `attachment-storage`); este change **escribe** en él, no lo redefine. La constraint transversal es cache-first (§7): la extracción es contenido de mensaje de usuario, al final del contexto, truncada una sola vez — cualquier byte que cambie antes del adjunto invalida el prefijo cacheado.

## Goals / Non-Goals

**Goals:**

- Portar a Python el pipeline completo del ANEXO (§8) como slice vertical: endpoints + extractores + escáner + worker aislado + UI del composer.
- Seguridad OWASP File Upload + spotlighting anti prompt-injection + escaneo N2/N3, con los rechazos y avisos exactos del §10.
- Transparencia diferencial ("Ver lo que verá el agente") y estados de chip que nunca fallan en silencio.
- Mantener `core/` sin frameworks: el pipeline vive en `app/` + `adapters/` detrás de un port; los extractores son adapters que traducen, no deciden.

**Non-Goals:**

- OCR (V1.1), visión, RAG/ingesta, resumen previo por IA (§3.3), adjuntos en workflows (`e22`). El schema de `b04` no se toca.

## Decisions

1. **Extractores por tipo como adapters detrás de un `ExtractionPort`.** El contrato (tipo de entrada → extracción estructurada) se define como `Protocol` puro; cada tipo (hojas, PDF, DOCX, texto/código/logs) es un adapter independiente. Alternativa descartada: un módulo monolítico de extracción — rompería la independencia entre adapters (import-linter, contrato 3) y dificultaría el test por tipo. El registro de `extractor_version` (P2/§5) sale del adapter.
2. **Hojas de cálculo: `openpyxl` + `python-calamine`.** `python-calamine` (binding Rust de calamine) es rápido y robusto para `.xls/.xlsx` hostiles (el sustituto Python de SheetJS §2.1); `openpyxl` cubre inspección fina de estilos/celdas ocultas cuando hace falta marcarlas `[oculta]`. CSV/TSV con el `csv` de stdlib en streaming (equivalente a papaparse). Salida esquema-primero (inventario + esquema + tabla MD/TSV), coherente con la investigación SpreadsheetLLM que cita el ANEXO.
3. **PDF: `pypdf` para texto nativo por página.** Sustituto Python de unpdf (§2.2). La detección de escaneado es el umbral de chars/página del ANEXO; el OCR (pytesseract `spa`) se **detecta y ofrece pero no se implementa** (V1.1). Alternativa `pdfplumber`/`pymupdf`: mejor layout de tablas pero `pymupdf` es AGPL y layout complejo es alcance RAG diferido; `pypdf` (BSD) alcanza para texto nativo con marcadores de página.
4. **DOCX: `mammoth` (Python).** Existe puerto Python de mammoth (lo confirma la tabla de pivote): Word → Markdown estructurado, imágenes → marcador. Evita `python-docx` crudo, que no reconstruye la semántica de títulos/tablas que el agente necesita para navegar un MIT.
5. **Escaneo N2/N3 con `presidio-analyzer` + reconocedores propios ES/BO.** Presidio es Python nativo (el ANEXO §4.4 lamentaba tener que reimplementarlo en Node — en Python ya es de primera clase). N3 (secretos: patrones API/`Password=`/JWT/private keys/cadenas de conexión) → bloqueo; N2 (PII + CI/NIT bolivianos, teléfonos, emails) con reconocedores custom → confirmación auditada. Corre sobre la extracción, no el binario. Alternativa: solo regex propio — Presidio aporta contexto y menos falsos negativos; los reconocedores propios cubren lo boliviano que Presidio no trae.
6. **Worker de parseo aislado con timeout y memoria acotada.** Proceso separado (pool con límite de recursos, `resource`/subproceso) con timeout 30 s: un XLSX/PDF malformado no debe tumbar `app/`. Es la traducción Python del "worker aislado" §4.1. Alternativa: parsear en el request handler — descartada, un parser hostil bloquearía el event loop.
7. **Spotlighting con `id` aleatorio por adjunto.** El delimitador `<adjunto id=aleatorio>` y la declaración dato-no-instrucción viven en el system prompt **estático** (regla fija, compatible cache-first). El `id` aleatorio impide el escape por cierre+reapertura de etiqueta. La heurística de instrucción embebida advierte y marca `scan_result` + traza, no bloquea (los falsos positivos no justifican bloqueo automático, §4.3). Un adjunto no puede disparar el marcador de escalación: la cadena queda como dato dentro del delimitador.
8. **Truncado por relevancia una sola vez, al componer el mensaje.** Estrategia por tipo (§3.2): consciente de estructura (headings), esquema-primero (hojas), head+tail (logs, tail-first). El resultado es `inserted_text` inmutable (invariante de `b04`). "Pedir otra parte" corta un fragmento nuevo de `full_text` como mensaje append-only. El conteo de tokens usa el tokenizer del proveedor vía el gateway (`b05`), no una estimación propia divergente.
9. **Frontend con `AttachmentAdapter` de assistant-ui.** Un adapter por familia de tipos sobre `CompositeAttachmentAdapter` (§6): `add()` valida/sube, hace polling del estado de extracción, `send()` devuelve la referencia `attachment_id`; la `inserted_text` la compone el servidor (el texto extraído nunca depende del cliente). Los eventos `attachmentAddError` tipados mapean a los mensajes del §10.

## Risks / Trade-offs

- [Tablas complejas de PDF pierden estructura en extracción plana] → Mitigación: aceptarlo y **decirlo** en la vista previa (aviso "Tablas PDF" del §10); el layout real es alcance RAG diferido.
- [Falsos positivos del escáner N3 bloqueando archivos legítimos] → Mitigación: N3 bloquea (es la decisión de seguridad del ANEXO) pero el mensaje indica línea/ubicación para que el usuario limpie o discuta; los patrones son configurables por instancia. N2 nunca bloquea, solo confirma.
- [Worker aislado añade latencia y complejidad operativa] → Mitigación: el timeout y el pool acotado son baratos frente a una caída de `app/` por un parser hostil; la extracción es una sola vez (dedup) y luego cache-hit.
- [Divergencia con el schema de `b04`] → Mitigación: consumir sus repositorios/tablas tal cual; los tests de `d14` escriben vía el `StatePort`/repositorios de `b04`, no con SQL propio.
- [Presidio infla dependencias/arranque] → Mitigación: cargar el analyzer en el worker, no en el hot path del chat; reconocedores propios ES/BO como plugins.

## Migration Plan

No hay datos previos que migrar (capability nueva). Despliegue: agregar dependencias (`openpyxl`, `python-calamine`, `pypdf`, `mammoth`, `presidio-analyzer`) al `pyproject.toml`; el schema ya existe por `b04`. Rollback: feature flag de subida de adjuntos en el composer (kill-switch coherente con `d20`); apagarlo deja el chat sin adjuntos sin afectar el resto. Los binarios ya subidos siguen su retención de 90 días.

## Open Questions

*(ninguna bloqueante — el ANEXO fija el comportamiento; el OCR y el resumen previo quedan explícitamente diferidos, no abiertos)*
