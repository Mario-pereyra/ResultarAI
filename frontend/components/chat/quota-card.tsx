"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Tag } from "@/components/ui/tag";
import type { Role } from "@/lib/session-context";
import { ErrorCard, type ErrorCardLabels } from "./error-card";

const QUOTA_CODE = "QUOTA";

export interface QuotaCardLabels extends ErrorCardLabels {
  /** «Solicitar liberación» (acción primaria). */
  requestRelease: string;
  /** Tag verde tras solicitar (vista 10 §Estados "QUOTA → solicitud
   * enviada"): «Solicitud enviada». */
  requestSent: string;
  /** «Te avisamos cuando un admin la resuelva.» */
  requestSentNote: string;
}

export interface QuotaCardProps {
  role: Role;
  labels: QuotaCardLabels;
  /**
   * Noop documentado (tarea 6.2, no-objetivo del proposal "Sin enforcement
   * de cuotas"): este change SOLO muestra el estado UI -- ni crea ni
   * resuelve una solicitud real. `d16-cuotas-liberaciones` reemplaza este
   * callback por el `POST` real de la solicitud; hasta entonces, el único
   * efecto observable de clickear es local (el tag "solicitud enviada" de
   * abajo), sin llamada de red.
   */
  onRequestRelease?: () => void;
}

/**
 * Tarjeta `QUOTA` (tarea 6.2 de d13-chat-conversacion, `design/VISTAS/02-chat.md`
 * vista 10, estado UI únicamente): botón "Solicitar liberación" que, al
 * clickearse, colapsa a un tag "solicitud enviada" (vista 10 §Estados). El
 * bloqueo real del composer (`disabled` + motivo inline) lo aplica
 * `chat-content.tsx`/`composer.tsx`, no esta tarjeta -- ver el docstring de
 * `ChatContent` para por qué QUOTA es "bloqueo, no solo error de turno"
 * (vista 10 §Interacciones).
 */
export function QuotaCard({ role, labels, onRequestRelease }: QuotaCardProps) {
  const [requested, setRequested] = useState(false);

  function handleRequest() {
    setRequested(true);
    onRequestRelease?.();
  }

  return (
    <ErrorCard
      code={QUOTA_CODE}
      role={role}
      labels={labels}
      actions={
        requested ? (
          <>
            <Tag variant="money">{labels.requestSent}</Tag>
            <p className="error-card__note">{labels.requestSentNote}</p>
          </>
        ) : (
          <Button variant="primary" size="sm" onClick={handleRequest}>
            {labels.requestRelease}
          </Button>
        )
      }
    />
  );
}
