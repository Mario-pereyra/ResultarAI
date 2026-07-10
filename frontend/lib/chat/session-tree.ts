import type { SessionTreeMessage } from "./types";

/**
 * Clave del grupo de hermanos de la RAÍZ en `siblingGroups`: los mensajes con
 * `parent_id null` (raíz de la conversación, y sus versiones hermanas cuando se
 * editó el primer mensaje) comparten esta clave sintética -- `null` no puede ser
 * clave de un `Map<string, ...>` sin perder el tipado, y usar un centinela evita
 * confundirlo con un id real (los ids son uuid, nunca esta cadena).
 */
export const ROOT_PARENT_KEY = "__root__";

/**
 * Versión elegida por el usuario en cada punto de bifurcación: mapea la clave del
 * grupo de hermanos (`parent_id` del grupo, o `ROOT_PARENT_KEY`) al id del hermano
 * seleccionado. Estado LOCAL de la UI (tarea 5.4): alternar de versión solo agrega
 * o reemplaza una entrada acá; el árbol de mensajes NUNCA se muta, así la rama no
 * seleccionada queda intacta en memoria y se puede volver a ella.
 */
export type BranchChoices = ReadonlyMap<string, string>;

/** Árbol plano de una sesión + su hoja activa (subconjunto de `SessionDetail`). */
export interface SessionBranchTree {
  messages: readonly SessionTreeMessage[];
  activeLeafId: string | null;
}

/** Información de versión de un mensaje ramificado para el selector "N/M". */
export interface VersionNav {
  /** Posición 1-based del mensaje entre sus hermanos (cronológica). */
  index: number;
  /** Cantidad total de versiones hermanas (incluida esta). */
  count: number;
  /** Clave del grupo de hermanos (para indexar `BranchChoices`). */
  parentKey: string;
  /** Id de la versión anterior (más vieja), o `null` si esta es la primera. */
  prevId: string | null;
  /** Id de la versión siguiente (más nueva), o `null` si esta es la última. */
  nextId: string | null;
}

/** Clave del grupo de hermanos de un mensaje: su `parent_id`, o el centinela raíz. */
function parentKeyOf(message: SessionTreeMessage): string {
  return message.parent_id ?? ROOT_PARENT_KEY;
}

/**
 * Orden canónico entre hermanos: `created_at` ascendente, empate por `id`
 * ascendente. Espeja EXACTAMENTE la semántica del backend (`_branching.py`:
 * `order_by(created_at, id)`) para que "versión 1/2" acá signifique lo mismo que
 * `version`/`version_count` de `POST /messages/{id}/regenerate`. Como los ids son
 * uuid7 (ordenados en el tiempo), el desempate por id respeta igual el orden
 * temporal ante dos hermanos creados en el mismo instante.
 */
function compareSiblings(a: SessionTreeMessage, b: SessionTreeMessage): number {
  if (a.created_at !== b.created_at) return a.created_at < b.created_at ? -1 : 1;
  if (a.id !== b.id) return a.id < b.id ? -1 : 1;
  return 0;
}

/**
 * Reconstruye el camino lineal de la rama ACTIVA de una sesión, desde la
 * raíz hasta `activeLeafId`, siguiendo `parent_id`.
 *
 * Es el DEFAULT del selector de versiones (tarea 5.4): con un `BranchChoices`
 * vacío, `resolveVisiblePath` reproduce exactamente este camino. Se conserva
 * como función propia porque `resolveVisiblePath` lo usa para saber, en cada
 * bifurcación, cuál hermano cae sobre la rama activa (el que se muestra por
 * defecto al abrir la sesión, vista 05).
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

/**
 * Agrupa los mensajes por punto de bifurcación (`parent_id`, o `ROOT_PARENT_KEY`
 * para la raíz), cada grupo ordenado con `compareSiblings`. Dos mensajes en el
 * mismo grupo son versiones hermanas: editar un mensaje o regenerar una respuesta
 * agrega un hermano al grupo del `parent_id` correspondiente (regla append-only de
 * la vista 09). Un grupo con más de un elemento es exactamente donde aparece el
 * selector "N/M".
 */
export function siblingGroups(
  messages: readonly SessionTreeMessage[],
): Map<string, SessionTreeMessage[]> {
  const groups = new Map<string, SessionTreeMessage[]>();
  for (const message of messages) {
    const key = parentKeyOf(message);
    const group = groups.get(key);
    if (group) {
      group.push(message);
    } else {
      groups.set(key, [message]);
    }
  }
  for (const group of groups.values()) group.sort(compareSiblings);
  return groups;
}

/**
 * Camino lineal VISIBLE del árbol dado un conjunto de versiones elegidas.
 *
 * Baja desde la raíz siguiendo, en cada bifurcación, al hermano indicado por
 * `choices`; si el grupo no tiene elección explícita, cae al DEFAULT: el hermano
 * que está sobre la rama activa (camino hacia `activeLeafId`) y, si ninguno lo
 * está (subárbol entrado por una elección previa), al más nuevo del grupo -- misma
 * noción de "rama activa = hoja más reciente" del backend (`_branching.py`).
 *
 * Función PURA: no muta ni el árbol ni `choices`. Alternar de versión solo cambia
 * `choices` y vuelve a llamar acá, por eso la rama no seleccionada nunca se pierde.
 */
export function resolveVisiblePath(
  tree: SessionBranchTree,
  choices: BranchChoices,
): SessionTreeMessage[] {
  const groups = siblingGroups(tree.messages);
  const activePathIds = new Set(
    resolveActiveBranch(tree.messages, tree.activeLeafId).map((message) => message.id),
  );

  const path: SessionTreeMessage[] = [];
  const visited = new Set<string>();
  let key = ROOT_PARENT_KEY;

  for (;;) {
    const group = groups.get(key);
    if (!group || group.length === 0) break;

    const choiceId = choices.get(key);
    const chosen =
      (choiceId ? group.find((message) => message.id === choiceId) : undefined) ??
      group.find((message) => activePathIds.has(message.id)) ??
      group[group.length - 1];

    if (visited.has(chosen.id)) break; // salvaguarda ante un árbol corrupto con ciclos
    visited.add(chosen.id);
    path.push(chosen);
    key = chosen.id;
  }

  return path;
}

/** Grupo de hermanos de `messageId` (ordenado) y su índice 0-based, o `null`. */
function siblingGroupOf(
  messages: readonly SessionTreeMessage[],
  messageId: string,
): { group: SessionTreeMessage[]; index: number } | null {
  const target = messages.find((message) => message.id === messageId);
  if (!target) return null;
  const key = parentKeyOf(target);
  const group = messages.filter((message) => parentKeyOf(message) === key).sort(compareSiblings);
  const index = group.findIndex((message) => message.id === messageId);
  if (index === -1) return null;
  return { group, index };
}

/**
 * Posición del mensaje entre sus versiones hermanas ("N/M"), o `null` si el id no
 * está en el árbol. El caller muestra el selector solo cuando `count > 1`.
 */
export function versionInfo(
  messages: readonly SessionTreeMessage[],
  messageId: string,
): { index: number; count: number } | null {
  const found = siblingGroupOf(messages, messageId);
  if (!found) return null;
  return { index: found.index + 1, count: found.group.length };
}

/**
 * Todo lo que el selector de versiones necesita para un mensaje ramificado:
 * `index`/`count` para el texto "N/M", `prevId`/`nextId` para las flechas ‹ › y
 * `parentKey` para registrar la elección en `BranchChoices`. `null` si el id no
 * está en el árbol.
 */
export function versionNav(
  messages: readonly SessionTreeMessage[],
  messageId: string,
): VersionNav | null {
  const found = siblingGroupOf(messages, messageId);
  if (!found) return null;
  const { group, index } = found;
  return {
    index: index + 1,
    count: group.length,
    parentKey: parentKeyOf(group[index]),
    prevId: index > 0 ? group[index - 1].id : null,
    nextId: index < group.length - 1 ? group[index + 1].id : null,
  };
}
