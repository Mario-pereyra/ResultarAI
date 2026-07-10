# Tasks — d14-attachments

## 1. Contrato y dependencias

- [x] 1.1 Definir `ExtractionPort` (Protocol puro en `core/ports/`): entrada tipada por tipo de archivo → extracción estructurada (inventario/esquema/texto + `extractor_version`), sin importar frameworks. Verificación: `uv run lint-imports` verde y `uv run mypy` sin errores sobre el port. `[modelo: opus]`
- [x] 1.2 Agregar dependencias al `pyproject.toml` (`openpyxl`, `python-calamine`, `pypdf`, `mammoth`, `presidio-analyzer`) y grupo de tipos si aplica. Verificación: `uv sync` termina sin errores y las libs importan. `[modelo: sonnet]`

## 2. Subida y validación de seguridad

- [x] 2.1 Endpoint de subida multipart en `app/attachments/`: estado inicial `subiendo`, límite de tamaño por tipo (matriz ANEXO §9, config) y máx 5 adjuntos/mensaje. Verificación: escenarios "excede tamaño" y "sexto adjunto" de `attachments-pipeline` pasan con sus textos §10. `[modelo: sonnet]`
- [x] 2.2 Validación de tipo real: allowlist de extensiones tras decodificar el nombre (doble extensión/null bytes) + magic bytes + coherencia ext/firma; Content-Type del navegador ignorado. Verificación: escenarios "extensión falsificada" y "fuera del allowlist" de `attachments-security` pasan (ANEXO §4.1). `[modelo: opus]`
- [x] 2.3 Rechazos de formatos activos/peligrosos: macros (.xlsm/.docm/.pptm), comprimidos, ejecutables, .doc antiguo, PDF con contraseña — cada uno con su mensaje §10. Verificación: test "Excel con macros rechazado" (.xlsm), "ejecutable rechazado" y "PDF con contraseña" en verde (ANEXO §2.6, §4.2). `[modelo: opus]`
- [x] 2.4 Protección zip-bomb OOXML: abortar si el descomprimido supera tamaño/ratio configurado (default >100 MB o >50:1). Verificación: test "OOXML tipo zip-bomb abortado" deja el adjunto en `error` sin agotar memoria (ANEXO §4.1). `[modelo: opus]`
- [x] 2.5 Worker de parseo aislado con timeout (30 s) y memoria acotada; los parsers solo leen. Verificación: test "archivo malformado agota el timeout" → adjunto `error` y plataforma operativa (ANEXO §4.1, §8). `[modelo: opus]`

## 3. Extractores deterministas por tipo

- [x] 3.1 Extractor de hojas (`openpyxl`/`python-calamine` + CSV/TSV streaming): inventario + esquema + tabla MD/TSV; 150+20 filas si excede. Verificación: escenario "XLSX que excede el límite de filas" con su marcador de filas omitidas (ANEXO §2.1). `[modelo: sonnet]`
- [x] 3.2 Extractor de PDF (`pypdf`) por página con marcadores `--- página N ---` + detección de escaneado por umbral chars/página y oferta de OCR marcada DIFERIDA (V1.1). Verificación: escenarios "PDF con texto nativo" y "PDF escaneado ofrece OCR diferido" (ANEXO §2.2). `[modelo: sonnet]`
- [x] 3.3 Extractor DOCX (`mammoth` Python → Markdown estructurado; imágenes → `[imagen omitida: …]`). Verificación: escenario "DOCX con encabezados, tabla e imagen" preserva estructura (ANEXO §2.3). `[modelo: sonnet]`
- [x] 3.4 Extractor texto/código/logs: detección de encoding→UTF-8, bloque de código con lenguaje, logs tail-first. Verificación: escenario "Log en Windows-1252 se normaliza y se trunca tail-first" (ANEXO §2.5). `[modelo: sonnet]`
- [x] 3.5 Rechazo de imágenes en V1 con alternativa accionable (el adapter no las admite). Verificación: el tipo imagen produce el texto "Imagen (V1)" §10, sin aceptar la subida (ANEXO §2.4). `[modelo: sonnet]`

## 4. Sanitización y anti prompt-injection

- [ ] 4.1 Sanitización pre-inserción: strip de comentarios HTML/XML, texto oculto, zero-width y control; normalización NFC; contenido oculto marcado `[oculta]`. Verificación: escenario "columna oculta se extrae marcada" (ANEXO §4.3). `[modelo: opus]`
- [ ] 4.2 Spotlighting: envoltura `<adjunto id=aleatorio>` + declaración dato-no-instrucción en el system prompt estático; `id` aleatorio anti-escape. Verificación: el `id` cambia por adjunto y un cierre de etiqueta embebido no escapa del delimitador (ANEXO §4.3). `[modelo: opus]`
- [ ] 4.3 Heurística de instrucción embebida y de marcador de escalación: advierte + flag en `scan_result`/traza sin bloquear; un adjunto no dispara la escalación. Verificación: escenarios "instrucción embebida advertida" y "un adjunto no dispara el marcador de escalación" (ANEXO §4.3). `[modelo: opus]`

## 5. Escaneo de niveles de datos N2/N3

- [ ] 5.1 Escáner N3 (secretos: claves API, `Password=`, cadenas de conexión, JWT, private keys) sobre la extracción → estado `bloqueado` con línea/ubicación. Verificación: escenario "secreto detectado bloquea el adjunto" con su mensaje §10 (ANEXO §4.4). `[modelo: opus]`
- [ ] 5.2 Escáner N2 (PII: emails, teléfonos, CI/NIT bolivianos) con Presidio + reconocedores propios ES/BO → advertencia con detalle + checkbox "Confirmo que son datos de prueba" auditado. Verificación: escenario "PII detectada requiere confirmación registrada en el audit log" (ANEXO §4.4). `[modelo: opus]`
- [ ] 5.3 Persistir el resultado del escaneo en `scan_result` del adjunto (schema de `b04`), consultable por Admin. Verificación: `scan_result` refleja hallazgos N2/N3 y flags de inyección y es recuperable en telemetría (ANEXO §4.4). `[modelo: sonnet]`

## 6. Presupuesto, truncado y composición del mensaje

- [ ] 6.1 Conteo de tokens (tokenizer del proveedor vía gateway `b05`) y truncado por relevancia UNA VEZ: consciente de estructura (DOCX/MD/PDF), esquema-primero (hojas), head+tail (logs), con marcadores explícitos; persiste `inserted_text`/`token_count`/%. Verificación: escenario "DOCX que excede el presupuesto se trunca consciente de estructura" (ANEXO §3.1–3.2). `[modelo: sonnet]`
- [ ] 6.2 Fragmento nuevo desde `full_text` al pedir otra parte (append-only, sin re-parsear ni re-truncar). Verificación: escenario "pedir otra parte inserta un fragmento nuevo sin re-procesar" (ANEXO §3.2, §7 P4). `[modelo: sonnet]`
- [ ] 6.3 Composición server-side del mensaje: texto del usuario + `<adjunto id=…>inserted_text</adjunto>` AL FINAL; cuota (`d16`) evaluada con el mensaje completo antes de llamar al modelo; ramas reutilizan `inserted_text`. Verificación: escenario "el adjunto entra al final del mensaje del usuario" (ANEXO §7, §8). `[modelo: sonnet]`

## 7. Ciclo de vida y persistencia

- [ ] 7.1 Dedup por sha256 y almacenamiento una sola vez (reutilizar `full_text`) sobre el schema de `b04`. Verificación: escenario "resubida del mismo archivo reutiliza la extracción" sin re-parsear (ANEXO §2 P2, §5). `[modelo: sonnet]`
- [ ] 7.2 Retención configurable (default 90 días) del binario/`full_text` conservando `inserted_text`, y descarga auditada solo para dueño y Admin, sin URLs públicas. Verificación: escenarios "usuario ajeno intenta descargar" y "descarga por el dueño queda auditada" (ANEXO §5). `[modelo: sonnet]`

## 8. Frontend del composer (vista 07-composer)

- [ ] 8.1 `AttachmentAdapter` (sobre `CompositeAttachmentAdapter`): `add()` valida/sube, polling del estado de extracción, `send()` devuelve `attachment_id`; errores tipados mapeados a mensajes §10. Verificación: subir→procesar→listo funciona end-to-end contra el endpoint (ANEXO §6). `[modelo: sonnet]`
- [ ] 8.2 Chips de estado subiendo→procesando→listo/advertencia/bloqueado/error con causa específica; nunca silencioso. Verificación: escenarios "error de extracción muestra causa" y "adjunto bloqueado se ve como no enviable" (ANEXO §6, §10). `[modelo: sonnet]`
- [ ] 8.3 Panel "Ver lo que verá el agente" (extracción exacta + marcadores de truncado + tokens/%; pie permanente) con capa por rol (Funcional=% de espacio; Técnico/Admin=tokens). Verificación: escenarios "vista previa de un adjunto truncado" y "mismo adjunto, métricas por rol" (ANEXO §3.4). `[modelo: sonnet]`
- [x] 8.4 Portar los textos de UI del §10 en voseo (chips y errores/avisos) a los recursos i18n del frontend. Verificación: escenario "imagen rechazada con alternativa accionable" y presencia literal de los textos §10. `[modelo: haiku]`

## 9. Cierre

- [ ] 9.1 Suite de tests del pipeline (extractores por tipo + ciclo de vida) y de seguridad (xlsm rechazado, tipo falsificado, zip-bomb abortado, N3 bloqueado, N2 auditado, instrucción embebida advertida) en verde en CI. Verificación: `uv run pytest` cubre cada escenario de las 3 specs. `[modelo: sonnet]`
- [ ] 9.2 Review final del change: coherencia con el schema de `b04` (sin redefinirlo), cache-first respetado (extracción al final, truncado una vez), OWASP/anti-injection/N2-N3 completos, fronteras verificadas. Verificación: checklist del reviewer en el PR. `[modelo: opus]`
