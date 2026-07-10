"use client";

import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Tag } from "@/components/ui/tag";

/**
 * Estados explícitos de la tarjeta de escalación (tarea 5.3 de
 * d13-chat-conversacion, `design/VISTAS/02-chat.md` vista 08 §Estados):
 *
 * - `idle` (reposo): ambos botones activos -- «Continuar con Pro» y
 *   «Seguir con Flash».
 * - `loading`: tras «Continuar con Pro»; botones deshabilitados, spinner en el
 *   primario mientras se crea la sesión Pro. El click dispara UNA sola llamada
 *   a `/escalate` (ver la garantía de idempotencia más abajo).
 * - `escalated`: la escalación quedó hecha; la tarjeta colapsa a una
 *   nota-enlace «Continuaste esta consulta en Pro — abrir conversación»
 *   (idempotencia: la tarjeta no puede re-usarse).
 * - `dismissed` (descartada): tras «Seguir con Flash»; colapsa a una línea
 *   atenuada «Decidiste seguir con Flash» y la conversación continúa en el
 *   perfil original. NO llama a ningún endpoint.
 */
export type EscalationCardStatus = "idle" | "loading" | "escalated" | "dismissed";

export interface EscalationCardLabels {
  /** Título de la tarjeta (`escalation.title`): «Este caso amerita el modelo Pro». */
  title: string;
  /** Consecuencia explícita (`escalation.consequence`): «Se abre una
   * conversación nueva con el contexto de esta.» -- estática, complementa la
   * `reason` dinámica del evento (vista 08 §Datos). */
  consequence: string;
  /** Prefijo accesible del tag del perfil de destino (`escalation.targetProfileLabel`):
   * el nombre del perfil se muestra 1 vez para todos los roles (decisión de
   * transparencia de la vista 08 §Diferencias por rol), este prefijo le da un
   * nombre accesible al tag mono sin repetir el valor. */
  targetProfileLabel: string;
  /** CTA primaria (`escalation.confirm`): «Continuar con Pro». */
  confirm: string;
  /** Acción secundaria (`escalation.dismiss`): «Seguir con Flash». */
  dismiss: string;
  /** Nota-enlace post-escalación (`escalation.doneLink`, vista 08 §Estados):
   * «Continuaste esta consulta en Pro — abrir conversación». */
  doneLink: string;
  /** Línea atenuada al descartar (`escalation.dismissedNote`, vista 08
   * §Estados): «Decidiste seguir con Flash». */
  dismissedNote: string;
}

export interface EscalationCardProps {
  /** `escalation.reason` del evento del stream (1-2 líneas generadas por el
   * agente antes del marcador -- por qué amerita Pro, vista 08 §Datos). */
  reason: string;
  /** `escalation.target_profile` del evento: el perfil de destino
   * (`deepseek-v4-pro`). Visible 1 vez para TODOS los roles (vista 08
   * §Diferencias por rol: transparencia, coherente con «modelo alterno»).
   * `null` si el evento no lo trajo -- entonces el tag no se renderiza. */
  targetProfile: string | null;
  labels: EscalationCardLabels;
  /**
   * Estado inicial de la máquina. Por defecto `idle`. `escalated` lo usa
   * `chat-content.tsx` al RECONSTRUIR la tarjeta tras recargar una sesión que
   * ya fue escalada (persistencia, tarea 5.3 punto 5): la tarjeta arranca
   * directamente en la nota-enlace, no en reposo. Los demás estados no se
   * inyectan de entrada -- son transiciones internas.
   */
  initialStatus?: EscalationCardStatus;
  /** id de la sesión escalada, disponible de entrada SOLO en el caso
   * reconstruido (`initialStatus="escalated"`); en el flujo vivo lo devuelve
   * `onEscalate`. Alimenta la nota-enlace. */
  escalatedSessionId?: string | null;
  /**
   * Dispara la escalación real (`POST /sessions/{id}/escalate`). DEBE devolver
   * el id de la sesión escalada. El backend es idempotente: una segunda llamada
   * sobre el mismo turno de origen (doble pestaña) responde `200` con la MISMA
   * sesión (`created:false`) -- este componente no distingue ese caso, navega
   * al id devuelto igual, sin tarjeta de error. Si rechaza, la tarjeta vuelve a
   * `idle` para permitir reintentar (no hay tarjeta de error de escalación en
   * la vista 08 fuera de la variante de cuota, que es `d16`).
   */
  onEscalate: () => Promise<{ escalatedSessionId: string }>;
  /** Navega a la sesión escalada (`router.push(/chat/{id})`). Se invoca tras
   * el éxito de `onEscalate` Y desde la nota-enlace. */
  onNavigateEscalated: (sessionId: string) => void;
  /** Aviso opcional de descarte (para telemetría/estado del caller). La
   * conversación sigue operativa con o sin este callback. */
  onDismiss?: () => void;
}

/**
 * Tarjeta de escalación manual a Pro (tarea 5.3 de d13-chat-conversacion,
 * `design/VISTAS/02-chat.md` vista 08, Flujo D de `design/FLUJOS.md`).
 *
 * Entra como contenido del stream, EMBEBIDA en el flujo de mensajes tras la
 * respuesta del turno que la disparó -- nunca un modal, no roba foco (vista 08
 * §Layout, DS §8.15). El montaje mismo lo gatea `chat-content.tsx`: si el
 * Agent Manifest tiene la escalación deshabilitada, esta tarjeta NO SE MONTA
 * JAMÁS (defensa en profundidad -- el backend ya suprime el marcador; la UI lo
 * re-verifica con `escalation_enabled` antes de montar, ver `renderEscalation`
 * en `chat-content.tsx`).
 *
 * ── Aserción de diseño (idempotencia + "nunca escala sola") ──
 * La escalación NUNCA ocurre por sí sola: ninguna ruta de código llama a
 * `onEscalate` sin el click explícito del usuario en «Continuar con Pro». El
 * doble clic / doble pestaña es idempotente por DOS barreras independientes:
 *   1. Cliente: un guard (`escalatingRef` + el estado `loading` que deshabilita
 *      el botón) bloquea toda re-entrada mientras hay una llamada en vuelo, así
 *      que dos clicks rápidos disparan UNA sola llamada.
 *   2. Servidor: `/escalate` es idempotente (segunda llamada sobre el mismo
 *      turno -> `200` con la misma sesión); si por carrera real (otra pestaña)
 *      la llamada retorna la sesión existente, este componente navega a ella
 *      igual, sin error.
 */
export function EscalationCard({
  reason,
  targetProfile,
  labels,
  initialStatus = "idle",
  escalatedSessionId = null,
  onEscalate,
  onNavigateEscalated,
  onDismiss,
}: EscalationCardProps) {
  const [status, setStatus] = useState<EscalationCardStatus>(initialStatus);
  const [resolvedSessionId, setResolvedSessionId] = useState<string | null>(escalatedSessionId);
  // Guard sincrónico de re-entrada: se fija ANTES del primer `await`, así un
  // segundo click que llegue en el mismo tick (antes de que React re-renderice
  // y deshabilite el botón) queda bloqueado -- garantiza una sola llamada a
  // `onEscalate`. `disabled` del botón es la segunda barrera, no la única.
  const escalatingRef = useRef(false);

  async function handleConfirm() {
    if (escalatingRef.current) return;
    escalatingRef.current = true;
    setStatus("loading");
    try {
      const result = await onEscalate();
      setResolvedSessionId(result.escalatedSessionId);
      setStatus("escalated");
      onNavigateEscalated(result.escalatedSessionId);
    } catch {
      // Sin tarjeta de error de escalación (vista 08): se vuelve a reposo para
      // permitir reintentar; se libera el guard para que un nuevo click valga.
      escalatingRef.current = false;
      setStatus("idle");
    }
  }

  function handleDismiss() {
    setStatus("dismissed");
    onDismiss?.();
  }

  if (status === "escalated") {
    return (
      <div className="escalate-card escalate-card--collapsed">
        <button
          type="button"
          className="escalate-card__done-link"
          onClick={() => {
            if (resolvedSessionId) onNavigateEscalated(resolvedSessionId);
          }}
        >
          <span className="escalate-card__branch-icon" aria-hidden="true">
            ↳
          </span>
          {labels.doneLink}
        </button>
      </div>
    );
  }

  if (status === "dismissed") {
    return (
      <div className="escalate-card escalate-card--collapsed">
        <p className="escalate-card__dismissed">{labels.dismissedNote}</p>
      </div>
    );
  }

  const loading = status === "loading";

  return (
    <div className="escalate-card" role="group" aria-label={labels.title}>
      <p className="escalate-card__title">
        <span className="escalate-card__icon" aria-hidden="true">
          ⚡
        </span>
        {labels.title}
      </p>
      <p className="escalate-card__reason">{reason}</p>
      <p className="escalate-card__consequence">{labels.consequence}</p>
      {targetProfile ? (
        <Tag variant="alt" outline className="escalate-card__profile" aria-label={`${labels.targetProfileLabel} ${targetProfile}`}>
          {targetProfile}
        </Tag>
      ) : null}
      <div className="escalate-card__actions">
        <Button variant="primary" loading={loading} onClick={handleConfirm}>
          {labels.confirm}
        </Button>
        <Button variant="ghost" disabled={loading} onClick={handleDismiss}>
          {labels.dismiss}
        </Button>
      </div>
    </div>
  );
}
