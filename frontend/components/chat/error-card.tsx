"use client";

import type { ReactNode } from "react";
import type { Role } from "@/lib/session-context";

/**
 * Tarjeta de error accionable genérica (tareas 6.1/6.2/6.3 de
 * d13-chat-conversacion, `design/VISTAS/02-chat.md` vista 10 -- subconjunto
 * `GATEWAY_OFFLINE`/`QUOTA` del proposal de este change). Comparte la
 * anatomía obligatoria qué-pasó/por-qué/qué-hacer (DS §8.16/§9.6) y la
 * redacción por rol (tarea 6.3, requirement "Redacción distinta por rol" de
 * `specs/chat-experience/spec.md`) entre `GatewayOfflineCard` y `QuotaCard`
 * -- este componente NO conoce el código ni las acciones concretas de cada
 * una, solo el layout/redacción comunes.
 *
 * Distinto de `components/shell/gateway-error.tsx` (el estado GLOBAL de
 * `d10-design-system-shell`, activado por la cookie de dev `?gateway=`): ese
 * cubre un banner del shell entero para cuando el gateway está caído en
 * general; este cubre el turno PUNTUAL de un chat, embebido en el flujo de
 * mensajes en el lugar de la respuesta fallida (vista 10 §Propósito) --
 * decisión documentada en el docstring de `chat-content.tsx`. Comparten la
 * clase `.error-card` (`app/globals.css` §5.13) por ser la MISMA anatomía
 * visual, pero son dos componentes distintos con datos y ciclos de vida
 * distintos: no vale la pena forzar una abstracción compartida entre un
 * banner de shell y una tarjeta embebida en un stream de turno.
 *
 * Redacción por rol (vista 10 §Quién la ve: "cambia la redacción del
 * porqué y la visibilidad del código"): el título ("qué pasó") es el MISMO
 * para los tres roles -- SOLO el "por qué" y la visibilidad del código
 * cambian. Técnico/Admin ven el código mono arriba (`error-card__code`,
 * igual que en `gateway-error.tsx`); Funcional lo ve en segundo plano al
 * pie de la tarjeta como «código para soporte: X» (vista 10 §Interacciones:
 * "el código de error siempre seleccionable/copiable" -- la copia queda
 * fuera de esta tarea, ver `openspec/BACKLOG-DESCUBRIMIENTOS.md`).
 */
export interface ErrorCardLabels {
  /** "Qué pasó" -- título humano, IGUAL para los tres roles. */
  title: string;
  /** "Por qué" técnico (Técnico/Admin). */
  technicalWhy: string;
  /** "Por qué" en lenguaje simple, sin jerga (Funcional). */
  funcionalWhy: string;
  /** Prefijo del código al pie para Funcional: «código para soporte:». */
  supportCodePrefix: string;
}

export interface ErrorCardProps {
  /** Código de error mono (`GATEWAY_OFFLINE`/`QUOTA`) -- mayúsculas, no
   * traducible (excluido del auditor de strings hardcodeados, ver
   * `scripts/check-hardcoded-strings.mjs`). */
  code: string;
  role: Role;
  labels: ErrorCardLabels;
  /** Nota extra entre el "por qué" y las acciones (tarea 6.1: el countdown
   * de reintento). `null`/`undefined` si el código no la necesita. */
  note?: ReactNode;
  /** Acciones (botones) de la tarjeta -- decididas por el caller. */
  actions?: ReactNode;
}

export function ErrorCard({ code, role, labels, note, actions }: ErrorCardProps) {
  const isTechnical = role !== "funcional";

  return (
    <div className="error-card" role="alert">
      <span className="error-card__icon" aria-hidden="true">
        ⛔
      </span>
      <div>
        {isTechnical ? <p className="error-card__code">{code}</p> : null}
        <p className="error-card__title">{labels.title}</p>
        <p className="error-card__why">{isTechnical ? labels.technicalWhy : labels.funcionalWhy}</p>
        {note}
        {actions ? <div className="error-card__actions">{actions}</div> : null}
        {isTechnical ? null : (
          <p className="error-card__support-code">
            {labels.supportCodePrefix} {code}
          </p>
        )}
      </div>
    </div>
  );
}
