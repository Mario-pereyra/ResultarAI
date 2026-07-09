"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import type { Role } from "@/lib/session-context";
import { WarnIcon } from "./icons";

/**
 * Estado global `GATEWAY_OFFLINE` (tarea 5.6, d10-design-system-shell).
 * `.error-card` (styles/tokens.css §5.13, portado en la tarea 4.x) con la
 * plantilla obligatoria de design/DESIGN-SYSTEM.md §9.6: qué pasó (título)
 * + por qué (1 línea) + qué hacer (Reintentar) — variante `danger` (base,
 * sin `--warn`): GATEWAY_OFFLINE es bloqueante para el contenido afectado,
 * no un degradado con modelo alterno (§9.6 distingue ambos casos).
 *
 * Redacción por rol (escenario "Redacción del error se adapta al rol",
 * specs/app-shell/spec.md, siguiendo DS §8.16/§9.6): Funcional NUNCA ve el
 * código `GATEWAY_OFFLINE` ni jerga ("El asistente no está disponible");
 * Técnico/Admin ven el código mono, copiable, y la redacción técnica.
 *
 * No lee `useSession()` directamente (a diferencia de otros componentes del
 * shell): recibe `role` por prop para poder testearse en aislamiento con
 * los 3 roles sin tener que envolver cada caso en `<SessionProvider>`.
 */

const GATEWAY_OFFLINE_CODE = "GATEWAY_OFFLINE";
/** Duración del spinner mock del botón Reintentar — sin backend real todavía (d12). */
const MOCK_RETRY_DURATION_MS = 600;

export type GatewayErrorLabels = {
  funcionalTitle: string;
  funcionalWhy: string;
  technicalTitle: string;
  technicalWhy: string;
  retry: string;
  retrying: string;
};

export type GatewayErrorProps = {
  role: Role;
  labels: GatewayErrorLabels;
  /** Callback opcional del intento de reintento real; d12 lo conecta al gateway. */
  onRetry?: () => void;
};

export function GatewayError({ role, labels, onRetry }: GatewayErrorProps) {
  const [retrying, setRetrying] = useState(false);
  const isTechnical = role !== "funcional";

  function handleRetry() {
    setRetrying(true);
    onRetry?.();
    window.setTimeout(() => setRetrying(false), MOCK_RETRY_DURATION_MS);
  }

  return (
    <div className="error-card" role="alert">
      <span className="error-card__icon" aria-hidden="true">
        <WarnIcon />
      </span>
      <div>
        {isTechnical ? <p className="error-card__code">{GATEWAY_OFFLINE_CODE}</p> : null}
        <p className="error-card__title">
          {isTechnical ? labels.technicalTitle : labels.funcionalTitle}
        </p>
        <p className="error-card__why">{isTechnical ? labels.technicalWhy : labels.funcionalWhy}</p>
        <div className="error-card__actions">
          <Button variant="secondary" size="sm" loading={retrying} onClick={handleRetry}>
            {retrying ? labels.retrying : labels.retry}
          </Button>
        </div>
      </div>
    </div>
  );
}
