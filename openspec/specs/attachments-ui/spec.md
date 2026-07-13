# attachments-ui Specification

## Purpose
TBD - created by archiving change d14-attachments. Update Purpose after archive.
## Requirements
### Requirement: Chip de adjunto con estados y causa específica

El composer SHALL mostrar por cada adjunto un chip con los estados `subiendo` → `procesando` → `listo` / `advertencia` / `bloqueado` / `error`, y cada estado no exitoso SHALL exponer una **causa específica** con el texto correspondiente de [ANEXO §10](../../../../design/ANEXO-ATTACHMENTS.md). El sistema SHALL NO dejar jamás un adjunto en un estado ambiguo o silencioso (anti-patrón "adjunto enviado que nunca llega", [ANEXO §6, Flujo H paso 5](../../../../design/ANEXO-ATTACHMENTS.md)).

#### Scenario: Error de extracción muestra causa accionable

- **WHEN** la extracción de un archivo dañado falla
- **THEN** el chip pasa a estado `error` con el texto "No se pudo procesar" y una causa accionable (p. ej. "Error genérico de extracción" de [ANEXO §10](../../../../design/ANEXO-ATTACHMENTS.md)), nunca un fallo silencioso

#### Scenario: Adjunto bloqueado se ve como no enviable

- **WHEN** el escaneo N3 bloquea un adjunto
- **THEN** el chip muestra el estado `bloqueado` con el texto "Bloqueado — contiene credenciales" y el composer no permite enviar el mensaje con ese adjunto

### Requirement: Vista previa "Ver lo que verá el agente"

El chip en estado `listo` SHALL ofrecer la acción "Ver lo que verá el agente", que abre un panel con la **extracción exacta** (incluidos los marcadores de truncado), los tokens estimados y el % del archivo incluido, con el pie permanente "Contenido extraído automáticamente — puede diferir del documento original" ([ANEXO §3.4, §10](../../../../design/ANEXO-ATTACHMENTS.md)).

#### Scenario: Vista previa de un adjunto truncado

- **WHEN** el usuario abre "Ver lo que verá el agente" sobre un adjunto truncado al 62%
- **THEN** el panel muestra la `inserted_text` exacta con sus marcadores de secciones omitidas, el conteo de tokens y el % incluido, y el pie permanente de contenido extraído

### Requirement: Transparencia de espacio por capa de rol

El chip y la vista previa SHALL adaptar la métrica de espacio al rol: para el rol **Funcional** el consumo se muestra como "% del espacio del mensaje"; para **Técnico** y **Admin** se muestra en tokens ([ANEXO §3.4, §10](../../../../design/ANEXO-ATTACHMENTS.md)).

#### Scenario: Mismo adjunto, métricas por rol

- **WHEN** un adjunto en estado `listo` se muestra a un usuario Funcional y a uno Técnico
- **THEN** el Funcional ve "Listo · usa 34% del espacio del mensaje" y el Técnico ve "Listo · 8.200 tokens", según [ANEXO §10](../../../../design/ANEXO-ATTACHMENTS.md)

### Requirement: Textos accionables del ANEXO §10 en voseo

Todos los rechazos, advertencias y avisos SHALL usar exactamente los textos de [ANEXO §10](../../../../design/ANEXO-ATTACHMENTS.md) en voseo (tipo no soportado, tipo falsificado, macros, demasiado grande, PDF protegido, PDF escaneado, imagen V1, Word antiguo, archivo vacío, truncado, tablas PDF, N2, N3, instrucción embebida, cuota, demasiados adjuntos), cada uno con su alternativa accionable.

#### Scenario: Imagen rechazada con alternativa accionable

- **WHEN** el usuario intenta adjuntar una imagen (`.png/.jpg/.gif/.webp`) en V1
- **THEN** el sistema muestra el texto "Imagen (V1)" de [ANEXO §10](../../../../design/ANEXO-ATTACHMENTS.md) ("pegá el texto del mensaje… o exportalo a PDF o Excel"), sin aceptar la subida
