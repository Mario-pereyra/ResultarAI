import type { TurnStreamError } from "./use-turn-stream";

/**
 * Clasifica el error de un turno (`use-turn-stream.ts`) en uno de los
 * códigos de la tarjeta de error accionable del chat (tareas 6.1/6.2 de
 * d13-chat-conversacion, `design/VISTAS/02-chat.md` vista 10 -- subconjunto
 * `GATEWAY_OFFLINE`/`QUOTA` del proposal, ver su "Impact"). `null` para
 * cualquier otro error -- ese caso sigue mostrándose con el aviso genérico
 * `chat-shell__error` que ya existía (`chat-content.tsx`).
 *
 * `GATEWAY_OFFLINE`: el POST del turno nunca llegó a buen puerto -- falla de
 * red agotando los reintentos internos del hook (`error.status === null`,
 * ver el docstring de `runTurn` en `use-turn-stream.ts`) o una respuesta
 * 502/503 típica de un proxy/gateway delante de la API cuando el servicio de
 * modelo está caído (`resultarai/` hoy no emite estos códigos él mismo --
 * son de infraestructura, por eso no hace falta tocar el backend para que
 * esta clasificación tenga sentido). En AMBOS casos el backend nunca
 * procesó el turno (nada quedó persistido de ese intento), así que
 * reintentar con el MISMO texto es, literalmente, la primera vez que ese
 * contenido llega al servidor -- nunca duplica un mensaje ya guardado (ver
 * el docstring de `retryPendingTurn` en `chat-content.tsx`).
 *
 * `QUOTA`: el backend de `d13` todavía NO emite este código -- el
 * enforcement real de cuotas es `d16-cuotas-liberaciones` (ver el
 * no-objetivo "Sin enforcement de cuotas" del proposal de este change).
 * Hasta entonces, un `402` (Payment Required, sin otro uso en esta API) en
 * la respuesta del POST del turno es la señal simulada/inyectada que activa
 * el estado UI de la tarea 6.2 -- los tests de este change fuerzan un `402`
 * con un doble de `fetch` para ejercitar la tarjeta (ver
 * `chat-content.test.tsx`). `d16` reemplaza esta heurística por el contrato
 * real que ese change defina (probablemente un campo/evento estructurado
 * propio en vez de un código HTTP genérico) sin que el resto de esta
 * clasificación tenga que cambiar.
 */
export type ChatTurnErrorCode = "GATEWAY_OFFLINE" | "QUOTA";

const QUOTA_STATUS = 402;
const GATEWAY_OFFLINE_STATUSES: ReadonlySet<number> = new Set([502, 503]);

export function classifyTurnError(error: TurnStreamError | null): ChatTurnErrorCode | null {
  if (!error) return null;
  if (error.status === QUOTA_STATUS) return "QUOTA";
  if (error.status === null || GATEWAY_OFFLINE_STATUSES.has(error.status)) return "GATEWAY_OFFLINE";
  return null;
}
