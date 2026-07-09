# Paquete de diseño — Resultar Agents Platform

> **Documentación de diseño — no código de producción.** Los mockups son HTML estáticos de referencia visual con datos 100% ficticios. Las specs OpenSpec se derivan de este paquete.

## Qué es Resultar Agents Platform

Plataforma de agentes IA para consultorías TOTVS Protheus, con modelo de **instancia por cliente**: cada consultora despliega la suya y el branding, catálogo y usuarios son configuración de instancia. Primera instancia: Resultar Bolivia (~30 consultores).

- **Roles** (cerrado): **Admin** (todo: telemetría, consola admin, builders, registro de prompts), **Técnico** (ficha técnica de agentes: tools/costo/prompt-version/evals; sin telemetría), **Funcional** (experiencia limpia tipo ChatGPT, cero jerga técnica). **Una sola UI** con capa de capacidades por rol — jamás interfaces separadas. Sin registro público; TOTP obligatorio para Admin.
- **Agentes**: **DocAgent** (documental TDN/CST, citas obligatorias, abstención sin evidencia), **ValidationAgent** (valida parametrización contra checklists; selector cliente/ambiente + bridge; toda escritura pasa por HITL), **DevAgent** (AdvPL/TLPP solo-sugerencia con diffs). **Workflows** deterministas con formulario = sección propia, separada del catálogo.

## Cómo navegar el paquete (orden de lectura sugerido)

| # | Documento | Qué contiene |
|---|---|---|
| 1 | [`README.md`](README.md) | Este índice maestro |
| 2 | [`DESIGN-SYSTEM.md`](DESIGN-SYSTEM.md) | Tokens, dual-brand, temas, tipografía, componentes, contraste AA |
| 3 | [`FUNCIONALIDADES.md`](FUNCIONALIDADES.md) | Inventario funcional completo por módulo y rol |
| 4 | [`FLUJOS.md`](FLUJOS.md) | 9 flujos end-to-end usuario↔sistema con referencia a mockups |
| 5 | [`VISTAS/`](VISTAS/) | Specs detalladas por módulo (propósito, layout, datos, estados, roles, móvil, i18n) |
| 6 | [`mockups/index.html`](mockups/index.html) | Galería navegable de los 44 mockups (abrir en navegador) |
| 7 | [`ANEXO-ATTACHMENTS.md`](ANEXO-ATTACHMENTS.md) | Pipeline de extracción de adjuntos (estados, formatos, niveles de datos) |

Empezar por `DESIGN-SYSTEM.md` + `mockups/00-styleguide.html` para el lenguaje visual; luego `FLUJOS.md` con la galería abierta al lado.

## Decisiones de producto registradas

| # | Decisión |
|---|---|
| D1 | **Dual-brand por tokens**: brand `default` ("sala de control": #0a0d13, ámbar #ffb000, verde #3ddc97, Chakra Petch/Saira/JetBrains Mono) y brand `totvs` (paleta oficial). `html[data-brand]` |
| D2 | **Dark + light completos** en ambas marcas, WCAG 2.1 AA verificado. `html[data-theme]`, dark por defecto |
| D3 | **i18n ES/PT-BR**: UI en español, textos externalizables, prever +25% de largo |
| D4 | **Desktop-first**; móvil funcional para chat, catálogo y aprobaciones HITL (estas últimas, primera clase) |
| D5 | **Centro de notificaciones** propio (aprobaciones, cuotas, liberaciones, mantenimiento) |
| D6 | **Workflows = sección propia** del producto, separada del catálogo de agentes |
| D7 | **Attachments con pipeline de extracción transparente** (Subiendo→Extrayendo→Listo/Falló, advertencia N3) |
| D8 | **Auditoría personal**: cada usuario ve su propio rastro (Mi auditoría) además del audit global de Admin |
| D9 | **Mockups de todas las vistas**: 44/44 vistas spec'd tienen mockup HTML |
| D10 | **Nombre del producto**: Resultar Agents Platform (instancia por cliente; "Resultar" brandeable por instancia) |

## Inventario de vistas

Estado: ✓ = mockup existente en [`mockups/`](mockups/).

| Nº | Vista | Módulo | Mockup |
|----|-------|--------|--------|
| 00 | Styleguide del sistema de diseño | Fundación | ✓ |
| 01 | Login | Acceso y shell | ✓ |
| 02 | Primer acceso (wizard + acuerdo de uso) | Acceso y shell | ✓ |
| 03 | Shell de aplicación | Acceso y shell | ✓ |
| 04 | Centro de notificaciones | Acceso y shell | ✓ |
| 05 | Chat (experiencia Funcional) | Chat | ✓ |
| 06 | Chat con capa de telemetría | Chat | ✓ |
| 07 | Composer con adjuntos | Chat | ✓ |
| 08 | Escalación a Pro | Chat | ✓ |
| 09 | Edición y ramas | Chat | ✓ |
| 10 | Estados de error accionables | Chat | ✓ |
| 11 | Citas y evidencia (DocAgent) | Chat | ✓ |
| 12 | Historial de sesiones | Chat | ✓ |
| 13 | Catálogo de agentes | Catálogo | ✓ |
| 14 | Ficha de agente | Catálogo | ✓ |
| 15 | Lista de workflows | Workflows | ✓ |
| 16 | Formulario de workflow | Workflows | ✓ |
| 17 | Ejecución en vivo | Workflows | ✓ |
| 18 | Resultado de workflow | Workflows | ✓ |
| 19 | Historial de corridas | Workflows | ✓ |
| 20 | Cola de aprobaciones | HITL y validación | ✓ |
| 21 | Detalle de aprobación (tarjeta HITL) | HITL y validación | ✓ |
| 22 | Historial de decisiones | HITL y validación | ✓ |
| 23 | Mi consumo | Mi espacio | ✓ |
| 24 | Mi memoria | Mi espacio | ✓ |
| 25 | Mi auditoría | Mi espacio | ✓ |
| 26 | Configuración personal | Mi espacio | ✓ |
| 27 | Selector cliente-final / ambiente | HITL y validación | ✓ |
| 28 | Gestión de checklists | HITL y validación | ✓ |
| 29 | Revisión de checklist convertido | HITL y validación | ✓ |
| 30 | Tablero de operación | Admin · Operación | ✓ |
| 31 | Gestión de usuarios | Admin · Operación | ✓ |
| 32 | Grupos y equipos | Admin · Operación | ✓ |
| 33 | Cuotas y liberaciones | Admin · Operación | ✓ |
| 34 | Registro de prompts | Admin · Gobernanza | ✓ |
| 35 | Tools y permisos | Admin · Gobernanza | ✓ |
| 36 | Conexiones | Admin · Gobernanza | ✓ |
| 37 | Audit log global | Admin · Operación | ✓ |
| 38 | Flags y kill-switch | Admin · Gobernanza | ✓ |
| 39 | Salud del sistema | Admin · Operación | ✓ |
| 40 | Configuración de instancia | Admin · Gobernanza | ✓ |
| 41 | Builder de agentes | Builders | ✓ |
| 42 | Builder de skills | Builders | ✓ |
| 43 | Evals y gates de publicación | Admin · Gobernanza | ✓ |

**Nota**: documentación de diseño — no código de producción; las specs OpenSpec se derivan de este paquete.
