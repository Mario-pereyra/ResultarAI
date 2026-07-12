"use client";

import { useEffect, useState } from "react";

/**
 * Datos del panel "Ver lo que verá el agente" (d14-attachments, tarea 8.3).
 * Fuente normativa: `design/ANEXO-ATTACHMENTS.md` §3.4 ("Vista previa de
 * extracción — patrón de transparencia") + spec
 * `openspec/changes/d14-attachments/specs/attachments-ui/spec.md`
 * (Requirement "Vista previa 'Ver lo que verá el agente'").
 *
 * Mismo criterio de separación que `useAttachmentAdapter`
 * (`attachment-adapter.ts`, docstring de módulo): el `fetch` vive ACÁ, el
 * componente (`components/chat/attachment-preview-panel.tsx`) es puramente
 * presentacional y solo consume el resultado tipado de este hook -- mismo
 * patrón que `AttachmentChip` consumiendo `AttachmentItem`.
 *
 * Espejo de `AttachmentPreviewResponse`
 * (`resultarai/app/api/attachments.py::preview_attachment_endpoint`,
 * `GET /api/attachments/{id}/preview`, endpoint ya existente de tareas
 * anteriores -- este hook NO lo modifica, solo lo consume): `text` es la
 * `inserted_text` EXACTA (con sus marcadores de truncado) si el adjunto ya
 * se envió en algún mensaje de la sesión, o el `full_text` tal cual si
 * todavía no -- ver el docstring de esa clase para la semántica pre/post
 * inserción completa.
 */
export interface AttachmentPreviewPayload {
  id: string;
  inserted: boolean;
  text: string;
  tokenCount: number;
  includedPercent: number;
  truncated: boolean;
}

export type AttachmentPreviewState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; payload: AttachmentPreviewPayload };

/** Espejo snake_case del payload HTTP (`AttachmentPreviewResponse`). */
interface AttachmentPreviewResponsePayload {
  id: string;
  inserted: boolean;
  text: string;
  token_count: number;
  included_percent: number;
  truncated: boolean;
}

/**
 * `attachmentId` es el `Attachment.id` REAL del backend
 * (`AttachmentItem.attachmentId`, NO el id local de UI que usa `remove()`/
 * `onOpenPreview`) -- `null` mantiene el hook en `idle` (panel cerrado, o
 * defensivamente, un adjunto sin id backend todavía: la acción de vista
 * previa solo se ofrece en `ready`, que siempre tiene `attachmentId`
 * asignado, así que este caso no debería ocurrir en la práctica).
 *
 * Vuelve a pedir el dato cada vez que `attachmentId` cambia (abrir un
 * adjunto distinto, o reabrir el mismo tras cerrarlo con `null` en el medio)
 * -- sin cache propia: el panel siempre muestra el dato fresco al abrir,
 * nunca el último valor cacheado del polling de `GET /api/attachments/{id}`
 * (que es una estimación más temprana, ver `AttachmentItem.tokenCount` en
 * `attachment-adapter.ts`).
 */
export function useAttachmentPreview(attachmentId: string | null): AttachmentPreviewState {
  // `fetchState` solo importa mientras `attachmentId` no es `null` -- el
  // caso `null` se devuelve como `idle` DERIVADO (sin pasar por un
  // `setState` dentro del efecto, ver más abajo: `react-hooks/set-state-in-effect`
  // marca ese patrón -- "resetear con un guard clause + return" -- como un
  // caso que Effects no debería resolver, ver
  // https://react.dev/learn/you-might-not-need-an-effect) en vez de quedar
  // un tick desactualizado mientras el efecto todavía no corrió.
  const [fetchState, setFetchState] = useState<AttachmentPreviewState>({ status: "idle" });

  useEffect(() => {
    if (!attachmentId) return;

    let cancelled = false;

    // Función async LOCAL (un `useEffect` no puede ser `async` él mismo) --
    // el `setFetchState` de "loading" vive ACÁ adentro (no como primera
    // instrucción del cuerpo del efecto): `react-hooks/set-state-in-effect`
    // (React Compiler) marca un `setState` síncrono suelto en el cuerpo del
    // efecto como el antipatrón "esto debería ser un valor derivado, no un
    // efecto" -- acá el fetch ES la sincronización real con un sistema
    // externo (ver https://react.dev/learn/you-might-not-need-an-effect,
    // "Fetching data"), así que el `setState` va dentro de la función que
    // hace ese trabajo, no suelto en el cuerpo del efecto.
    async function loadPreview(): Promise<void> {
      setFetchState({ status: "loading" });
      try {
        const response = await fetch(`/api/attachments/${attachmentId}/preview`);
        if (!response.ok) throw new Error("attachment_preview_not_ready");
        const payload = (await response.json()) as AttachmentPreviewResponsePayload;
        if (cancelled) return;
        setFetchState({
          status: "ready",
          payload: {
            id: payload.id,
            inserted: payload.inserted,
            text: payload.text,
            tokenCount: payload.token_count,
            includedPercent: payload.included_percent,
            truncated: payload.truncated,
          },
        });
      } catch {
        if (!cancelled) setFetchState({ status: "error" });
      }
    }

    void loadPreview();

    return () => {
      cancelled = true;
    };
  }, [attachmentId]);

  return attachmentId === null ? { status: "idle" } : fetchState;
}
