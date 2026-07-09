# attachment-storage — Delta Spec (b04-persistencia-postgres)

> Alcance: **solo el schema y sus invariantes**. El pipeline de extracción (validación, parseo, sanitización, escaneo N2/N3, truncado) es `d14-attachments`.

## ADDED Requirements

### Requirement: Schema de attachments conforme al ANEXO §5

La base SHALL contener una tabla `attachments` con, como mínimo, los campos definidos en [design/ANEXO-ATTACHMENTS.md](../../../../design/ANEXO-ATTACHMENTS.md) §5: `id` (uuid), `session_id` / `message_id` (nullable hasta que el adjunto se envía), `uploaded_by`, `original_name`, `declared_mime`, `detected_type`, `size_bytes`, `sha256`, `storage_path` (uuid del binario en disco) y `scan_result` (jsonb con hallazgos N2/N3 y flags de inyección). El campo `status` SHALL restringirse por constraint al conjunto cerrado `uploaded | extracting | ready | blocked | error`.

#### Scenario: Una fila de adjunto persiste todos los campos del ANEXO §5

- **WHEN** se persiste un adjunto
- **THEN** la fila almacena `id`, referencias de sesión/mensaje, metadatos del archivo, `sha256`, `storage_path` y `scan_result`, y su `status` pertenece al conjunto cerrado permitido

#### Scenario: Se rechaza un status fuera del conjunto permitido

- **WHEN** se intenta persistir un adjunto con un `status` que no pertenece a `uploaded | extracting | ready | blocked | error`
- **THEN** la base lo rechaza por constraint

### Requirement: Schema de extraction con texto insertado inmutable

La base SHALL almacenar la extracción del adjunto con los campos del ANEXO §5: `full_text` (extracción completa, reutilizable por dedup), `inserted_text` (lo que ENTRÓ al mensaje, post-truncado), `token_count`, `truncated` (bool con % incluido) y `extractor_version`. Una vez fijado, `inserted_text` SHALL ser **inmutable**: la base no permite reescribirlo (es parte lógica del mensaje append-only).

#### Scenario: Se rechaza mutar inserted_text

- **WHEN** se intenta un UPDATE de `inserted_text` ya fijado
- **THEN** la base lo rechaza y el valor permanece byte-idéntico

#### Scenario: Una rama reutiliza inserted_text byte-idéntica

- **WHEN** una rama nueva referencia un adjunto ya insertado en el prefijo común
- **THEN** reutiliza la misma `inserted_text` sin re-truncar ni re-parsear (preserva el prefijo cacheable)

### Requirement: Dedup por sha256

El schema SHALL permitir deduplicar por `sha256` dentro de la misma instancia: subir el mismo archivo otra vez reutiliza la extracción `full_text` existente sin re-parsear el binario.

#### Scenario: Mismo archivo reutiliza la extracción existente

- **WHEN** se sube un archivo cuyo `sha256` ya existe en la instancia
- **THEN** la persistencia reutiliza el `full_text` existente y no crea una extracción duplicada

#### Scenario: Archivo distinto genera extracción propia

- **WHEN** se sube un archivo con un `sha256` no visto antes
- **THEN** se crean registros de adjunto y extracción nuevos

### Requirement: scan_result como metadato consultable

El resultado del escaneo N2/N3 y los flags de inyección SHALL persistir como metadato (`scan_result`) del adjunto, consultable para telemetría de Admin (ANEXO §4.4). Este change persiste el metadato; no ejecuta el escaneo (`d14`).

#### Scenario: El resultado del escaneo queda como metadato del adjunto

- **WHEN** un adjunto tiene un `scan_result` con hallazgos N2/N3
- **THEN** ese resultado se persiste junto al adjunto y es recuperable en consultas de telemetría por Admin

### Requirement: Retención configurable por instancia

El schema SHALL soportar retención **configurable por instancia** (default 90 días para el binario y su `full_text`, ANEXO §5). La `inserted_text` SHALL sobrevivir mientras viva la conversación: purgar el binario y el `full_text` no rompe la sesión.

#### Scenario: Purgar el binario preserva la sesión

- **WHEN** vence la retención configurada y se purgan el binario (`storage_path`) y el `full_text` de un adjunto
- **THEN** la `inserted_text` referenciada por los mensajes permanece intacta y la conversación sigue siendo consistente
