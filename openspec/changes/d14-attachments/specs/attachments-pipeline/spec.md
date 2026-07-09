# attachments-pipeline — Delta Spec (d14-attachments)

> Fuente normativa: [design/ANEXO-ATTACHMENTS.md](../../../../design/ANEXO-ATTACHMENTS.md) (pipeline §8, matriz §9), [design/FUNCIONALIDADES.md §5](../../../../design/FUNCIONALIDADES.md), [design/FLUJOS.md Flujo H](../../../../design/FLUJOS.md). El schema de almacenamiento lo define `b04-persistencia-postgres` (capability `attachment-storage`); aquí se consume, no se redefine.

## ADDED Requirements

### Requirement: Subida con límites de tamaño y de cantidad por mensaje

El endpoint de subida SHALL aceptar archivos por multipart, asignar el estado inicial `subiendo` y aplicar un límite de tamaño **por tipo** (matriz [ANEXO §9](../../../../design/ANEXO-ATTACHMENTS.md)) y un máximo de **5 adjuntos por mensaje**, ambos como configuración de instancia/agente, no como constantes de código. Superar cualquiera de los dos límites SHALL rechazar el adjunto con el texto accionable de [ANEXO §10](../../../../design/ANEXO-ATTACHMENTS.md), sin fallar en silencio.

#### Scenario: Archivo que excede el límite de tamaño de su tipo

- **WHEN** se sube un Excel de 25 MB con el límite de tipo Excel en 20 MB
- **THEN** el adjunto se rechaza antes de extraer y el sistema devuelve el mensaje "Demasiado grande" de [ANEXO §10](../../../../design/ANEXO-ATTACHMENTS.md) con el límite concreto

#### Scenario: Sexto adjunto en el mismo mensaje

- **WHEN** un mensaje ya tiene 5 adjuntos y se intenta agregar uno más
- **THEN** el sistema rechaza el sexto con el mensaje "Máximo 5 archivos por mensaje" de [ANEXO §10](../../../../design/ANEXO-ATTACHMENTS.md)

### Requirement: Extracción determinista de hojas de cálculo

Para `.xlsx/.xls/.csv/.tsv` el pipeline SHALL extraer, en este orden, inventario de hojas (nombre, dimensiones, hoja activa), esquema por hoja (encabezados + tipo inferido + no-vacíos) y datos como tabla Markdown o TSV, usando `openpyxl`/`python-calamine` para Excel y parseo streaming para CSV/TSV ([ANEXO §2.1](../../../../design/ANEXO-ATTACHMENTS.md)). El detalle SHALL cubrir hasta 200 filas por hoja; si excede, SHALL incluir primeras 150 + últimas 20 filas con marcador de filas omitidas, conservando siempre el inventario y el esquema.

#### Scenario: XLSX que excede el límite de filas de detalle

- **WHEN** se extrae una hoja con 500 filas de datos
- **THEN** la extracción conserva inventario y esquema completos e incluye las primeras 150 y las últimas 20 filas con un marcador `… (N filas omitidas) …`

### Requirement: Extracción determinista de PDF con detección de escaneado

Para `.pdf` el pipeline SHALL extraer texto nativo **por página** con `pypdf`, conservando marcadores de página (`--- página N ---`) ([ANEXO §2.2](../../../../design/ANEXO-ATTACHMENTS.md)). Si el promedio de caracteres extraídos por página cae por debajo del umbral configurado (~50 chars/página), el PDF SHALL clasificarse como escaneado y el sistema SHALL ofrecer OCR de forma explícita, marcado como **diferido a V1.1** — nunca procesar en silencio.

#### Scenario: PDF con texto nativo

- **WHEN** se extrae un PDF con texto seleccionable de 8 páginas
- **THEN** la extracción incluye el texto por página con sus marcadores `--- página N ---`

#### Scenario: PDF escaneado ofrece OCR diferido

- **WHEN** un PDF supera el límite de páginas legibles pero su promedio de caracteres por página está por debajo del umbral
- **THEN** el sistema no procesa en silencio, marca el adjunto con la oferta de OCR ("PDF escaneado", [ANEXO §10](../../../../design/ANEXO-ATTACHMENTS.md)) y no ejecuta OCR en esta versión (diferido a V1.1)

### Requirement: Extracción determinista de DOCX

Para `.docx` el pipeline SHALL convertir el documento a Markdown estructurado con `mammoth` (Python), preservando títulos, listas y tablas Word reales, y SHALL reemplazar cada imagen embebida por un marcador `[imagen omitida: nombre]` (sin visión) ([ANEXO §2.3](../../../../design/ANEXO-ATTACHMENTS.md)).

#### Scenario: DOCX con encabezados, tabla e imagen

- **WHEN** se extrae un DOCX con títulos numerados, una tabla y una imagen embebida
- **THEN** la extracción produce Markdown con los encabezados y la tabla preservados y un marcador `[imagen omitida: …]` en lugar de la imagen

### Requirement: Extracción determinista de texto, código y logs

Para `.txt/.md`, código (`.prw/.prx/.tlpp/.sql/.json/.xml/.yml/.ini`) y `.log` el pipeline SHALL detectar el encoding y convertirlo a UTF-8, normalizar saltos de línea y envolver el contenido en un bloque de código con lenguaje (` ```advpl `, ` ```sql `, ` ```log `) ([ANEXO §2.5](../../../../design/ANEXO-ATTACHMENTS.md)). Los logs SHALL truncarse tail-first (priorizando el final).

#### Scenario: Log en Windows-1252 se normaliza y se trunca tail-first

- **WHEN** se extrae un `.log` codificado en Windows-1252 que excede el presupuesto
- **THEN** el contenido se convierte a UTF-8, se envuelve en ` ```log ` y el truncado prioriza el final del archivo (head 25% + tail 70%) con marcador en el medio

### Requirement: Extracción una sola vez, determinista y almacenada

La extracción SHALL ejecutarse **una sola vez por binario** y almacenarse (`full_text`); el pipeline SHALL registrar la versión del extractor para trazabilidad y SHALL reutilizar `full_text` ante un archivo ya visto (dedup por sha256, [ANEXO §2 P2, §5](../../../../design/ANEXO-ATTACHMENTS.md)), sin re-parsear el binario.

#### Scenario: Resubida del mismo archivo reutiliza la extracción

- **WHEN** se sube un archivo cuyo sha256 ya existe en la misma instancia
- **THEN** el pipeline reutiliza el `full_text` almacenado y no vuelve a parsear el binario

### Requirement: Presupuesto de tokens y truncado por relevancia una sola vez

El pipeline SHALL contar tokens de la extracción y, si supera el presupuesto (default 12.000 tokens por archivo y 24.000 por mensaje, configurables), SHALL truncar por relevancia **una única vez al insertar**, persistiendo `inserted_text`, `token_count` y el % incluido ([ANEXO §3.1–3.2, §7 P4](../../../../design/ANEXO-ATTACHMENTS.md)). La estrategia SHALL ser consciente de estructura (DOCX/MD/PDF: conservar todos los títulos + secciones más relacionadas), esquema-primero (hojas: nunca truncar inventario ni esquema) o head+tail (logs/texto plano), siempre con marcadores explícitos en cada hueco. El pipeline SHALL NO re-truncar una extracción ya insertada (reescribiría historia).

#### Scenario: DOCX que excede el presupuesto se trunca consciente de estructura

- **WHEN** un DOCX extraído supera los 12.000 tokens
- **THEN** `inserted_text` conserva todos los títulos y las secciones más relacionadas con el texto del mensaje, cada sección omitida lleva su marcador, y `truncated` registra el % incluido

#### Scenario: Pedir otra parte inserta un fragmento nuevo sin re-procesar

- **WHEN** el usuario pide una sección del archivo que quedó omitida por el truncado
- **THEN** el sistema corta un fragmento nuevo del `full_text` ya almacenado y lo inserta como mensaje nuevo (append-only), sin re-parsear el binario ni re-truncar la inserción anterior

### Requirement: Composición del mensaje con la extracción al final del contexto

Al enviar, el servidor SHALL componer el mensaje del usuario con su texto seguido de la extracción envuelta en `<adjunto id=…>inserted_text</adjunto>` **al final del contexto**, nunca en el system prompt ni en mensajes anteriores, para preservar el prefijo cacheable ([ANEXO §7](../../../../design/ANEXO-ATTACHMENTS.md)). La cuota de sesión SHALL evaluarse con el mensaje completo **antes** de llamar al modelo, y las ramas SHALL reutilizar la misma `inserted_text` byte-idéntica.

#### Scenario: El adjunto entra al final del mensaje del usuario

- **WHEN** se envía un mensaje con un adjunto en estado `listo`
- **THEN** el servidor inserta la `inserted_text` dentro de `<adjunto id=…>` al final del contenido del mensaje del usuario, evalúa la cuota con el mensaje ya compuesto y solo entonces llama al modelo

### Requirement: Ciclo de vida — dedup, retención y descarga auditada

El pipeline SHALL deduplicar por sha256, aplicar retención configurable (default 90 días para el binario y su `full_text`) y permitir la descarga del binario **solo al dueño y a Admin**, siempre **auditada** y sin URLs públicas ([ANEXO §5](../../../../design/ANEXO-ATTACHMENTS.md)). La `inserted_text` SHALL sobrevivir mientras viva la conversación aunque se purgue el binario.

#### Scenario: Un usuario ajeno intenta descargar un adjunto

- **WHEN** un usuario que no es dueño del adjunto ni Admin solicita su descarga
- **THEN** el sistema rechaza la descarga y no expone ninguna URL pública del archivo

#### Scenario: Descarga por el dueño queda auditada

- **WHEN** el dueño del adjunto descarga su binario
- **THEN** la descarga se sirve por endpoint autenticado y queda registrada en el audit log
