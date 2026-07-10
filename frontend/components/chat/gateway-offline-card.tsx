"use client";

import { Button } from "@/components/ui/button";
import { useRetryBackoff } from "@/lib/chat/use-retry-backoff";
import type { Role } from "@/lib/session-context";
import { ErrorCard, type ErrorCardLabels } from "./error-card";

const GATEWAY_OFFLINE_CODE = "GATEWAY_OFFLINE";

export interface GatewayOfflineCardLabels extends ErrorCardLabels {
  /** «Reintentar ahora». */
  retryNow: string;
  /** Plantilla ICU-lite con placeholder literal `{n}` (segundos restantes):
   * «Reintentando en {n} s» (vista 10 §Datos, columna "Qué hacer" de
   * `GATEWAY_OFFLINE`). */
  retryingIn: string;
}

export interface GatewayOfflineCardProps {
  /** Intento consecutivo actual (1-based) -- ver el docstring de
   * `useRetryBackoff`. `chat-content.tsx` lo incrementa en cada fallo nuevo
   * sobre el mismo turno pendiente. */
  attempt: number;
  role: Role;
  labels: GatewayOfflineCardLabels;
  /** Reenvía el turno pendiente con el MISMO texto (tarea 6.1) -- lo decide
   * el caller (`chat-content.tsx`, `retryPendingTurn`); este componente no
   * conoce `use-turn-stream` ni el modelo de mensajes. */
  onRetry: () => void;
}

/**
 * Tarjeta `GATEWAY_OFFLINE` (tarea 6.1 de d13-chat-conversacion,
 * `design/VISTAS/02-chat.md` vista 10): countdown de reintento con backoff
 * 5→15→60 s (`useRetryBackoff`) + botón "Reintentar ahora" que dispara el
 * mismo reintento de inmediato. Presentacional: mantenida montada por
 * `chat-content.tsx` mientras `attempt > 0` (ver su docstring), este
 * componente solo traduce `attempt` en un countdown visible y expone el
 * botón manual -- ambos caminos usan la MISMA garantía de "un solo
 * reintento" del hook.
 */
export function GatewayOfflineCard({ attempt, role, labels, onRetry }: GatewayOfflineCardProps) {
  const { secondsRemaining, retryNow } = useRetryBackoff({ attempt, onRetry });

  return (
    <ErrorCard
      code={GATEWAY_OFFLINE_CODE}
      role={role}
      labels={labels}
      note={
        <p className="error-card__countdown" role="status">
          {labels.retryingIn.replace("{n}", String(secondsRemaining))}
        </p>
      }
      actions={
        <Button variant="secondary" size="sm" onClick={retryNow}>
          {labels.retryNow}
        </Button>
      }
    />
  );
}
