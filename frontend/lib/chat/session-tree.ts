import type { SessionTreeMessage } from "./types";

/**
 * Reconstruye el camino lineal de la rama ACTIVA de una sesión, desde la
 * raíz hasta `activeLeafId`, siguiendo `parent_id`.
 *
 * `GET /sessions/{id}` (tarea 2.3 del backend) expone el árbol COMPLETO,
 * incluidas las ramas descartadas por edición o "Seguir con Flash" -- el
 * selector de versiones que navega entre ramas es la tarea 5.4
 * (d13-chat-conversacion), fuera de las tareas 3.1/3.2 que corresponde
 * implementar acá. Mientras tanto, se renderiza solo la rama activa
 * (`active_leaf_id`), que es exactamente lo que la vista 05 muestra por
 * defecto al abrir una sesión.
 */
export function resolveActiveBranch(
  messages: readonly SessionTreeMessage[],
  activeLeafId: string | null,
): SessionTreeMessage[] {
  if (!activeLeafId) return [];

  const byId = new Map(messages.map((message) => [message.id, message]));
  const path: SessionTreeMessage[] = [];
  const visited = new Set<string>();
  let currentId: string | null = activeLeafId;

  while (currentId) {
    if (visited.has(currentId)) break; // salvaguarda ante un árbol corrupto con ciclos
    visited.add(currentId);
    const message = byId.get(currentId);
    if (!message) break;
    path.push(message);
    currentId = message.parent_id;
  }

  return path.reverse();
}
