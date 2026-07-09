# Proposal — d14-attachments

## Why

El chat gobernado necesita aceptar archivos (reportes Protheus, planillas, MITs, logs, código AdvPL) sin que un binario llegue jamás al modelo ni que un documento se convierta en vector de ataque o de fuga de datos. El schema de almacenamiento ya existe (`b04-persistencia-postgres`, [ANEXO §5](../../../design/ANEXO-ATTACHMENTS.md)), pero está vacío: falta el pipeline que valida, extrae, sanea, escanea y presupuesta el contenido, y la UI que lo hace transparente. Este slice vertical (backend + UI) porta a Python el pipeline completo del ANEXO, la fuente normativa del comportamiento.

## What Changes

- **Subida y validación (OWASP File Upload):** allowlist de extensiones tras decodificar el nombre + magic bytes (coherencia extensión/firma, nunca el Content-Type del navegador); límites de tamaño por tipo (matriz [ANEXO §9](../../../design/ANEXO-ATTACHMENTS.md) como config de instancia/agente); rechazo de macros (`.xlsm/.docm/.pptm`), comprimidos, ejecutables, `.doc` antiguo y PDF con contraseña; nombre original solo como metadato, binario en disco como UUID fuera del webroot; protección zip-bomb OOXML (ratio/tamaño descomprimido); parseo en worker aislado con timeout y memoria acotada ([ANEXO §4.1–4.2, §8](../../../design/ANEXO-ATTACHMENTS.md)).
- **Extracción determinista server-side por tipo, una sola vez y almacenada** ([ANEXO §2](../../../design/ANEXO-ATTACHMENTS.md)): XLSX/XLS (`openpyxl`/`python-calamine`: inventario de hojas + esquema + tabla MD/TSV, 150+20 filas si excede), CSV/TSV streaming, PDF texto nativo por página con marcadores (`pypdf`) + detección de PDF escaneado (umbral chars/página) con oferta de OCR **diferida (V1.1)**, DOCX (`mammoth` Python → Markdown estructurado, imágenes → marcador), TXT/MD/código/logs (encoding→UTF-8, bloque de código con lenguaje, logs tail-first). Imágenes: rechazo claro con alternativa accionable (V1).
- **Sanitización + anti prompt-injection (spotlighting, [ANEXO §4.3](../../../design/ANEXO-ATTACHMENTS.md)):** delimitadores `<adjunto id=aleatorio>` declarados como dato-no-instrucción en el system prompt estático; strip de texto oculto/zero-width/control; normalización Unicode NFC; heurística de instrucción embebida → advertencia + flag en la traza (no bloquea); un adjunto no puede disparar el marcador de escalación.
- **Escaneo de niveles de datos ([ANEXO §4.4](../../../design/ANEXO-ATTACHMENTS.md)):** N3 (credenciales/secretos: claves API, `Password=`, cadenas de conexión, JWT, private keys) → estado **bloqueado**, no enviable, con línea/ubicación; N2 (PII: emails, teléfonos, CI/NIT bolivianos) → advertencia con detalle + checkbox "Confirmo que son datos de prueba" **auditado** (Presidio + reconocedores propios ES/BO). El escaneo corre sobre la extracción, no el binario.
- **Presupuesto y truncado ([ANEXO §3](../../../design/ANEXO-ATTACHMENTS.md)):** 12k tokens/archivo, 24k/mensaje, máx 5 adjuntos (defaults de config); truncado por relevancia al insertar, **una vez** (consciente de estructura para DOCX/MD/PDF; esquema-primero para hojas; head+tail para logs), con marcadores explícitos; pedir otra parte = fragmento nuevo cortado de `full_text` (append-only, sin re-parsear).
- **Transparencia y UI (vista `07-composer`, [ANEXO §3.4, §10](../../../design/ANEXO-ATTACHMENTS.md)):** chips con estados subiendo → procesando → listo / advertencia / bloqueado / error, cada uno con causa específica (jamás fallar en silencio); acción "Ver lo que verá el agente" (extracción exacta + tokens estimados; % de espacio para el rol Funcional); textos UI del §10 en voseo.
- **Ciclo de vida ([ANEXO §5, §7](../../../design/ANEXO-ATTACHMENTS.md)):** dedup por sha256, retención 90 días default (config), descarga solo dueño y Admin (auditada), sin URLs públicas; ramas comparten `inserted_text`; la extracción entra al final del contexto como contenido del mensaje de usuario (cache-first).

## Capabilities

### New Capabilities

- `attachments-pipeline`: subida y validación de tamaño, extracción determinista por tipo (XLSX/XLS/CSV/TSV/PDF/DOCX/TXT/MD/código/logs), presupuesto de tokens y truncado por relevancia una sola vez, y ciclo de vida (dedup sha256, retención, descarga auditada, composición del mensaje al final del contexto).
- `attachments-security`: validación de tipo real (magic bytes + coherencia ext/firma), rechazos de seguridad (macros, comprimidos, ejecutables, `.doc`, PDF con contraseña, zip-bomb), sanitización y spotlighting anti prompt-injection, y escaneo de niveles N2/N3 con confirmación/bloqueo auditados.
- `attachments-ui`: chips de estado del composer con causa específica, panel de vista previa "Ver lo que verá el agente", textos accionables del ANEXO §10 (voseo) y capa por rol (Funcional ve % de espacio; Técnico/Admin ven tokens).

### Modified Capabilities

*(ninguna — `attachment-storage` de `b04` define el schema; este change lo consume sin cambiar sus requisitos)*

## No-objetivos

- **Sin OCR** de PDF escaneado ni de imágenes: la oferta se detecta y se comunica, pero la implementación queda **diferida a V1.1** ([ANEXO §2.2, §2.4](../../../design/ANEXO-ATTACHMENTS.md)).
- **Sin visión** (análisis de imágenes por modelo): las imágenes se rechazan con alternativa accionable; la capacidad de visión será un `model_profile` aparte con su propio análisis N0–N3 (Etapa P).
- **Sin RAG / ingesta** documental (`RetrievalPort` sigue con adapter nulo): parseo de layout, tablas complejas de PDF y servicios externos de extracción quedan fuera.
- **Sin resumen previo por IA** de archivos grandes ([ANEXO §3.3](../../../design/ANEXO-ATTACHMENTS.md)): el default es truncado determinista; el resumen opcional se difiere.
- **Sin adjuntos en workflows** (formulario con archivos esperados): es alcance de `e22-workflows-deterministas`.
- **Sin re-definir el schema de almacenamiento** (`attachments`, `extractions`, `message_attachments`): lo entregó `b04-persistencia-postgres`; aquí se referencia y se escribe en él.

## Bounded context afectado

Contexto **attachments** (satélite de producto). Toca `resultarai/app/` (endpoints de subida/estado/descarga y composición del mensaje), `resultarai/adapters/` (extractores por tipo, escáner N2/N3 con Presidio, worker de parseo aislado; detrás de un port de pipeline) y el **frontend** Next.js + assistant-ui (`AttachmentAdapter`, chips y panel de vista previa). No introduce lógica en `resultarai/core/` salvo, si corresponde, el contrato del port de extracción (Protocol puro). No pertenece al ERP: el escaneo N2/N3 es genérico (la personalización Protheus es Etapa P).

## Impact

- `resultarai/app/attachments/`: endpoints REST (subida multipart, polling de estado, descarga auditada) y composición server-side del mensaje (`<adjunto>` al final del contexto).
- `resultarai/adapters/`: extractores por tipo (`openpyxl`/`python-calamine`, `pypdf`, `mammoth`), escáner de datos (`presidio-analyzer` + reconocedores propios ES/BO), worker de parseo aislado; nuevas dependencias en `pyproject.toml`.
- `frontend/`: `AttachmentAdapter` (validar/subir/polling/`send`) sobre `CompositeAttachmentAdapter`, chips de estado y panel "Ver lo que verá el agente" (vista `07-composer`).
- Escribe en el schema de `b04` (`attachments`/`extractions`/`message_attachments`) y persiste `scan_result`; evalúa cuota de sesión (`d16`) con el mensaje ya compuesto, antes de llamar al modelo.
- Referencia normativa: [design/ANEXO-ATTACHMENTS.md](../../../design/ANEXO-ATTACHMENTS.md) completo, [design/FUNCIONALIDADES.md §5](../../../design/FUNCIONALIDADES.md) y [design/FLUJOS.md Flujo H](../../../design/FLUJOS.md); blueprint §2.4 (adjuntos como entrada gobernada al scaffolding).
