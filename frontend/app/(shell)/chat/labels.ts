import type { getTranslations } from "next-intl/server";
import type { ChatContentLabels } from "./chat-content";

type Translator = Awaited<ReturnType<typeof getTranslations>>;

/**
 * Agente con el que `chat/page.tsx` crea la sesión nueva al primer envío.
 * El selector de agente (`agent.starter_prompts`, catálogo completo) es
 * `d15` -- ver `openspec/BACKLOG-DESCUBRIMIENTOS.md`. Todavía no existe un
 * endpoint de catálogo que exponga `display_name` al frontend (solo
 * `manifests/agents/default_chat.yaml`, que no se lee desde acá), así que
 * el nombre mostrado en el composer ("Escribile a {agent}…", vista 05)
 * queda hardcodeado con el `name` literal del manifiesto hasta que `d15`
 * lo resuelva dinámicamente.
 *
 * Exportados (no solo `const` de módulo): `history-labels.ts` (tarea 7.1,
 * historial vista 12) los reutiliza para el filtro por agente y el nombre
 * visible de cada fila, sin duplicar el literal.
 */
export const DEFAULT_CHAT_AGENT_ID = "default_chat";
export const DEFAULT_CHAT_AGENT_DISPLAY_NAME = "Chat por Defecto";

/** Arma `ChatContentLabels` desde el namespace `Chat` de `messages/es.json`,
 * compartido por `chat/page.tsx` y `chat/[sessionId]/page.tsx`. */
export function buildChatLabels(t: Translator): ChatContentLabels {
  return {
    agentId: DEFAULT_CHAT_AGENT_ID,
    // Header del chat (`ChatHeader`): valor inicial/de reserva de
    // `agentName` mientras `GET /api/agents/{id}` no resolvió todavía (o
    // falló) -- mismo literal que ya usa el placeholder del composer más
    // abajo, reexportado como campo propio para que `chat-content.tsx` no
    // tenga que importar `./labels.ts` (evita el import circular con el
    // tipo `ChatContentLabels` que este módulo ya importa desde ahí).
    defaultAgentName: DEFAULT_CHAT_AGENT_DISPLAY_NAME,
    header: {
      sessionMenuLabel: t("header.sessionMenuLabel"),
    },
    emptyGreeting: t("empty.greeting"),
    stoppedCaption: t("message.stopped"),
    streamingDoneAnnouncement: t("streaming.doneAnnouncement"),
    cursorAriaLabel: t("streaming.cursorAriaLabel"),
    activity: {
      consulting: t("activity.consulting"),
    },
    newMessages: t("stream.newMessages"),
    feedback: {
      like: t("actions.like"),
      dislike: t("actions.dislike"),
      prompt: t("feedback.prompt"),
      commentLabel: t("feedback.commentLabel"),
      send: t("feedback.send"),
      skip: t("feedback.skip"),
      error: t("feedback.error"),
    },
    composer: {
      placeholder: t("composer.placeholder", { agent: DEFAULT_CHAT_AGENT_DISPLAY_NAME }),
      send: t("composer.send"),
      stop: t("composer.stop"),
      hint: t("composer.hint"),
      textareaLabel: t("composer.textareaLabel"),
      attach: t("composer.attach"),
      attachmentsListLabel: t("composer.attachmentsListLabel"),
      // Plantilla ICU-lite (mismo patrón que `versionAriaLabel`/
      // `reprocessWarningOne` de más abajo): `{file}` es el nombre del
      // archivo, un dato de runtime -- `AttachmentChip` hace el `.split`/
      // `.join` con el valor real.
      removeAttachment: t("composer.removeAttachment", { file: "{file}" }),
      // Tarea 8.2 (chip de estado): plantillas ICU-lite con `{percent}`/
      // `{tokens}` sin resolver -- `AttachmentChip` interpola el valor de
      // runtime (`tokenCount`/`includedPercent`, rol) contra ESTE texto.
      attachmentStates: {
        uploading: t("attachments.states.uploading", { percent: "{percent}" }),
        processing: t("attachments.states.processing"),
        readyTechAdmin: t("attachments.states.readyTechAdmin", { tokens: "{tokens}" }),
        readyFunctional: t("attachments.states.readyFunctional", { percent: "{percent}" }),
        readyTruncated: t("attachments.states.readyTruncated", { percent: "{percent}" }),
        warning: t("attachments.states.warning"),
        blocked: t("attachments.states.blocked"),
        error: t("attachments.states.error"),
      },
      attachmentPiiConfirmation: t("attachments.warnings.piiConfirmation"),
      attachmentPiiCancel: t("attachments.warnings.piiCancel"),
      attachmentPreviewAction: t("attachments.preview.action"),
    },
    loading: t("session.loading"),
    loadError: t("session.loadError"),
    sendError: t("session.sendError"),
    taximeter: {
      label: t("taximeter.label"),
      srLabelPrefix: t("taximeter.srLabelPrefix"),
      degradedTooltip: t("taximeter.degradedTooltip"),
    },
    telemetry: {
      cacheHit: t("telemetry.cacheHit"),
      cacheMiss: t("telemetry.cacheMiss"),
      cacheWrite: t("telemetry.cacheWrite"),
      cacheHitAriaLabelPrefix: t("telemetry.cacheHitAriaLabelPrefix"),
      cacheHitAriaLabelSuffix: t("telemetry.cacheHitAriaLabelSuffix"),
      cacheMissAriaLabelPrefix: t("telemetry.cacheMissAriaLabelPrefix"),
      cacheMissAriaLabelSuffix: t("telemetry.cacheMissAriaLabelSuffix"),
      cacheWriteAriaLabelPrefix: t("telemetry.cacheWriteAriaLabelPrefix"),
      cacheWriteAriaLabelSuffix: t("telemetry.cacheWriteAriaLabelSuffix"),
      cacheHitTooltip: t("telemetry.cacheHitTooltip"),
      cacheMissTooltip: t("telemetry.cacheMissTooltip"),
      cacheWriteTooltip: t("telemetry.cacheWriteTooltip"),
      viewTrace: t("telemetry.viewTrace"),
      viewTraceAriaLabel: t("telemetry.viewTraceAriaLabel"),
    },
    alternateModel: {
      label: t("alternateModel.label"),
      funcionalExplanation: t("alternateModel.funcionalExplanation"),
      profilePrefix: t("alternateModel.profilePrefix"),
      reasonPrefix: t("alternateModel.reasonPrefix"),
    },
    toolCall: {
      parametersLabel: t("toolCall.parametersLabel"),
      latencyLabel: t("toolCall.latencyLabel"),
    },
    versionSelector: {
      // Plantilla ICU-lite: el componente interpola {n}/{m} con la versión en
      // vivo (dato de runtime del cliente, no resoluble acá). El "N/M" visual
      // no se traduce (DS §4.2); esto es solo el `aria-label` del selector.
      versionAriaLabel: t("branch.versionAriaLabel", { n: "{n}", m: "{m}" }),
      previousVersion: t("branch.previousVersion"),
      nextVersion: t("branch.nextVersion"),
    },
    escalation: {
      title: t("escalation.title"),
      consequence: t("escalation.consequence"),
      targetProfileLabel: t("escalation.targetProfileLabel"),
      confirm: t("escalation.confirm"),
      dismiss: t("escalation.dismiss"),
      doneLink: t("escalation.doneLink"),
      dismissedNote: t("escalation.dismissedNote"),
    },
    escalationOriginLink: t("escalation.originLink"),
    messageEdit: {
      action: t("edit.action"),
      textareaLabel: t("edit.textareaLabel"),
      cancel: t("edit.cancel"),
      confirm: t("edit.confirm"),
      // Plantilla ICU-lite (mismo patrón que `versionAriaLabel` arriba):
      // `reprocessCount` es un dato de runtime del cliente (cuántos mensajes
      // posteriores tiene la rama visible en el momento de editar, ver
      // `lib/chat/session-tree.ts::countMessagesAfter`), así que acá solo se
      // resuelve el TEXTO fijo con el placeholder `{n}` sin interpolar --
      // `message-edit.tsx` hace el `.replace("{n}", …)` con el valor real y
      // elige One/Other según `Intl.PluralRules` (el aviso de la vista 09
      // solo se muestra desde N=3, así que "One" es un caso borde que hoy
      // nunca se renderiza, pero queda resuelto correctamente igual).
      reprocessWarningOne: t("branch.reprocessWarningOne", { n: "{n}" }),
      reprocessWarningOther: t("branch.reprocessWarningOther", { n: "{n}" }),
    },
    compactionIndicator: t("compaction.label"),
    gatewayOffline: {
      title: t("gatewayOffline.title"),
      technicalWhy: t("gatewayOffline.technicalWhy"),
      funcionalWhy: t("gatewayOffline.funcionalWhy"),
      supportCodePrefix: t("errorCard.supportCodePrefix"),
      retryNow: t("gatewayOffline.retryNow"),
      // Plantilla ICU-lite (mismo patrón que `versionAriaLabel`/
      // `reprocessWarningOne` arriba): `{n}` son los segundos restantes,
      // un dato de runtime del cliente -- `GatewayOfflineCard` resuelve el
      // `.replace("{n}", …)` con el valor real del countdown.
      retryingIn: t("gatewayOffline.retryingIn", { n: "{n}" }),
    },
    quota: {
      title: t("quota.title"),
      technicalWhy: t("quota.technicalWhy"),
      funcionalWhy: t("quota.funcionalWhy"),
      supportCodePrefix: t("errorCard.supportCodePrefix"),
      requestRelease: t("quota.requestRelease"),
      requestSent: t("quota.requestSent"),
      requestSentNote: t("quota.requestSentNote"),
    },
    quotaComposerDisabledReason: t("quota.composerDisabledReason"),
    // Tarea 7.3 (historial vista 12): motivo inline del composer cuando el
    // agente de la sesión ya no es invocable (`GET /api/agents/{id}` -> 404) --
    // la sesión se puede LEER pero no continuar, ver `chat-content.tsx`.
    agentDisabledComposerReason: t("agentDisabled.composerReason"),
    // Tarea 8.1 (d14-attachments): textos §10 que `useAttachmentAdapter`
    // mapea desde los `error_code`/causas tipadas de la subida/escaneo -- ver
    // `lib/chat/attachment-adapter.ts` para el subconjunto de
    // `Chat.attachments.errors`/`Chat.attachments.fileTypes` que realmente
    // consume (el resto -- vista previa truncada, cuota de mensaje -- son
    // texto de 8.2/8.3, no de este adapter; "PDF escaneado" SÍ es de este
    // adapter, aunque el OCR en sí siga diferido a V1.1).
    attachments: {
      errors: {
        unsupportedType: t("attachments.errors.unsupportedType", { extension: "{extension}" }),
        falsifiedType: t("attachments.errors.falsifiedType", { extension: "{extension}" }),
        withMacros: t("attachments.errors.withMacros", { extension: "{extension}" }),
        tooLarge: t("attachments.errors.tooLarge", { limitMb: "{limitMb}", fileType: "{fileType}" }),
        pdfProtected: t("attachments.errors.pdfProtected"),
        // Cobertura d14-attachments (ANEXO §2.2/§10): "PDF escaneado (oferta OCR)" --
        // el OCR sigue diferido a V1.1, pero la advertencia (nunca bloquea) YA la
        // produce el escaneo de estado terminal, ver `attachment-adapter.ts`.
        pdfScanned: t("attachments.errors.pdfScanned"),
        imageNotSupported: t("attachments.errors.imageNotSupported"),
        wordLegacy: t("attachments.errors.wordLegacy"),
        tooManyAttachments: t("attachments.errors.tooManyAttachments", { limit: "{limit}" }),
        credentialsDetected: t("attachments.errors.credentialsDetected", { detail: "{detail}" }),
        piiDetected: t("attachments.errors.piiDetected", { detail: "{detail}" }),
        embeddedInstruction: t("attachments.errors.embeddedInstruction", { detail: "{detail}" }),
        genericError: t("attachments.errors.genericError"),
      },
      fileTypes: {
        excel: t("attachments.fileTypes.excel"),
        csv: t("attachments.fileTypes.csv"),
        pdf: t("attachments.fileTypes.pdf"),
        docx: t("attachments.fileTypes.docx"),
        text: t("attachments.fileTypes.text"),
        code: t("attachments.fileTypes.code"),
        log: t("attachments.fileTypes.log"),
      },
      // Tarea 8.2: etiquetas amigables por `entity_type` de Presidio para el
      // `{detail}` de `errors.piiDetected` -- ver el docstring de
      // `piiEntityLabels` en `lib/chat/attachment-adapter.ts`. Los `BO_PHONE`/
      // `PHONE_NUMBER` comparten redacción (ambos son "número de teléfono"
      // para el usuario, la distinción ES/BO-vs-genérico es solo del
      // reconocedor, no de la UI).
      piiEntityLabels: {
        EMAIL_ADDRESS: {
          one: t("attachments.piiEntityLabels.emailOne"),
          other: t("attachments.piiEntityLabels.emailOther"),
        },
        PHONE_NUMBER: {
          one: t("attachments.piiEntityLabels.phoneOne"),
          other: t("attachments.piiEntityLabels.phoneOther"),
        },
        BO_PHONE: {
          one: t("attachments.piiEntityLabels.phoneOne"),
          other: t("attachments.piiEntityLabels.phoneOther"),
        },
        PERSON: {
          one: t("attachments.piiEntityLabels.personOne"),
          other: t("attachments.piiEntityLabels.personOther"),
        },
        BO_CI: {
          one: t("attachments.piiEntityLabels.ciOne"),
          other: t("attachments.piiEntityLabels.ciOther"),
        },
        BO_NIT: {
          one: t("attachments.piiEntityLabels.nitOne"),
          other: t("attachments.piiEntityLabels.nitOther"),
        },
      },
    },
    // Tarea 8.3: panel "Ver lo que verá el agente" (`AttachmentPreviewPanel`).
    // `metricTechAdmin`/`metricFunctional` reutilizan LAS MISMAS plantillas
    // que `composer.attachmentStates.readyTechAdmin`/`readyFunctional` de
    // arriba (mismo texto literal del ANEXO §10) -- ver el docstring de
    // `AttachmentPreviewPanelLabels` para el porqué. `truncatedNotice`
    // reutiliza `attachments.errors.truncatedPreview` (portado en la tarea
    // 8.4, sin consumidor hasta esta tarea).
    attachmentPreview: {
      title: t("attachments.preview.title"),
      closeLabel: t("attachments.preview.closeLabel"),
      footer: t("attachments.preview.footer"),
      loading: t("attachments.preview.loading"),
      error: t("attachments.preview.error"),
      metricTechAdmin: t("attachments.states.readyTechAdmin", { tokens: "{tokens}" }),
      metricFunctional: t("attachments.states.readyFunctional", { percent: "{percent}" }),
      truncatedNotice: t("attachments.errors.truncatedPreview", { percent: "{percent}" }),
    },
  };
}
