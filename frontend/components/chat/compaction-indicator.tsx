"use client";

export interface CompactionIndicatorProps {
  label: string;
}

/**
 * Indicador discreto de compaction (tarea 5.6 de d13-chat-conversacion,
 * requirement "Indicador discreto de compaction" de
 * `specs/chat-experience/spec.md`, contrato `context-compaction` de
 * `b06-runtime-grafos`, `docs/03-glosario-dominio.md` §Compaction: "resumen
 * automático del historial al 80% de la ventana de contexto; ocurre una sola
 * vez, en frontera de turno").
 *
 * Se monta en el PUNTO exacto de la conversación donde ocurrió: el turno del
 * agente cuyo `turn_metadata.compacted === true` (ver `ChatMessageItem.compacted`
 * en `message-column.tsx`, que lo renderiza ANTES de la respuesta de ese
 * turno). Como `compacted` viaja siempre para los tres roles
 * (`layer_turn_metadata`, `resultarai/app/use_cases/chat/telemetry.py`), este
 * indicador NO tiene variantes por rol.
 *
 * Línea puramente informativa (`role="note"`): no bloquea ni interrumpe el
 * flujo, no tiene acción propia. El requirement "permitir que el usuario
 * reenvíe contenido compactado como mensaje nuevo" se satisface con el
 * composer normal (`components/chat/composer.tsx`) -- si el usuario necesita
 * que algo resumido vuelva a estar presente para el modelo, simplemente lo
 * vuelve a escribir/pegar como un mensaje nuevo; no hace falta ningún botón
 * ni flujo adicional acá.
 */
export function CompactionIndicator({ label }: CompactionIndicatorProps) {
  return (
    <div className="chat-compaction" role="note">
      <span className="chat-compaction__line" aria-hidden="true" />
      <span className="chat-compaction__label">{label}</span>
      <span className="chat-compaction__line" aria-hidden="true" />
    </div>
  );
}
