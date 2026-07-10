import { describe, expect, it } from "vitest";
import {
  ROOT_PARENT_KEY,
  resolveVisiblePath,
  siblingGroups,
  versionInfo,
  versionNav,
  type BranchChoices,
  type SessionBranchTree,
} from "./session-tree";
import type { SessionTreeMessage } from "./types";

/** Constructor breve de un mensaje del árbol (solo los campos que usa la
 * navegación de ramas; el resto se rellena inerte). */
function msg(
  id: string,
  parentId: string | null,
  role: "user" | "assistant",
  content: string,
  createdAt: string,
): SessionTreeMessage {
  return {
    id,
    parent_id: parentId,
    role,
    content,
    status: "complete",
    created_at: createdAt,
    turn_metadata: null,
  };
}

/**
 * Árbol con bifurcación en el MEDIO: el usuario editó el 2º mensaje, así que
 * hay dos versiones (`u2a`/`u2b`) con una respuesta cada una. La rama activa
 * (hoja más reciente) es la editada (`a2b`).
 *
 *   u1 ── a1 ─┬─ u2a ── a2a        (versión 1)
 *             └─ u2b ── a2b        (versión 2, editada = activa)
 */
const MIDDLE_EDIT: SessionTreeMessage[] = [
  msg("u1", null, "user", "Hola", "2026-07-10T14:00:00Z"),
  msg("a1", "u1", "assistant", "Respuesta inicial", "2026-07-10T14:00:03Z"),
  msg("u2a", "a1", "user", "Pregunta A", "2026-07-10T14:01:00Z"),
  msg("a2a", "u2a", "assistant", "rama A", "2026-07-10T14:01:05Z"),
  msg("u2b", "a1", "user", "Pregunta B", "2026-07-10T14:02:00Z"),
  msg("a2b", "u2b", "assistant", "rama B", "2026-07-10T14:02:05Z"),
];
const MIDDLE_EDIT_TREE: SessionBranchTree = { messages: MIDDLE_EDIT, activeLeafId: "a2b" };
const NO_CHOICES: BranchChoices = new Map();

describe("siblingGroups", () => {
  it("agrupa por parent_id (raíz bajo ROOT_PARENT_KEY) y ordena cada grupo por created_at asc", () => {
    const groups = siblingGroups(MIDDLE_EDIT);
    expect(groups.get(ROOT_PARENT_KEY)?.map((m) => m.id)).toEqual(["u1"]);
    // El grupo del punto de bifurcación (hijos de `a1`) tiene las dos versiones,
    // la más vieja primero.
    expect(groups.get("a1")?.map((m) => m.id)).toEqual(["u2a", "u2b"]);
    expect(groups.get("u2a")?.map((m) => m.id)).toEqual(["a2a"]);
    expect(groups.get("u2b")?.map((m) => m.id)).toEqual(["a2b"]);
  });

  it("desempata hermanos con el mismo created_at por id ascendente (espeja al backend)", () => {
    const sameInstant: SessionTreeMessage[] = [
      msg("r", null, "user", "raíz", "2026-07-10T14:00:00Z"),
      msg("b", "r", "assistant", "b", "2026-07-10T14:00:03Z"),
      msg("a", "r", "assistant", "a", "2026-07-10T14:00:03Z"),
    ];
    expect(siblingGroups(sameInstant).get("r")?.map((m) => m.id)).toEqual(["a", "b"]);
  });
});

describe("resolveVisiblePath — default sigue active_leaf_id", () => {
  it("con choices vacío muestra la rama activa (la editada), no la descartada", () => {
    const path = resolveVisiblePath(MIDDLE_EDIT_TREE, NO_CHOICES).map((m) => m.id);
    expect(path).toEqual(["u1", "a1", "u2b", "a2b"]);
  });

  it("elegir la otra versión en el punto de bifurcación produce el camino de la rama 1", () => {
    // Elegir `u2a` (versión 1) en el grupo cuyo parent es `a1`.
    const choices: BranchChoices = new Map([["a1", "u2a"]]);
    const path = resolveVisiblePath(MIDDLE_EDIT_TREE, choices).map((m) => m.id);
    expect(path).toEqual(["u1", "a1", "u2a", "a2a"]);
  });

  it("no muta el árbol ni las choices al resolver (ambas ramas siguen completas)", () => {
    resolveVisiblePath(MIDDLE_EDIT_TREE, new Map([["a1", "u2a"]]));
    // Los dos leafs de ambas ramas siguen presentes en el árbol original.
    expect(MIDDLE_EDIT.map((m) => m.id)).toContain("a2a");
    expect(MIDDLE_EDIT.map((m) => m.id)).toContain("a2b");
  });
});

describe("versionInfo / versionNav — mensaje editado en el medio", () => {
  it("versionInfo da 1/2 y 2/2 para las dos versiones del mensaje editado", () => {
    expect(versionInfo(MIDDLE_EDIT, "u2a")).toEqual({ index: 1, count: 2 });
    expect(versionInfo(MIDDLE_EDIT, "u2b")).toEqual({ index: 2, count: 2 });
  });

  it("los mensajes sin hermanos reportan count 1 (no muestran selector)", () => {
    expect(versionInfo(MIDDLE_EDIT, "u1")).toEqual({ index: 1, count: 1 });
    expect(versionInfo(MIDDLE_EDIT, "a1")).toEqual({ index: 1, count: 1 });
  });

  it("versionInfo devuelve null para un id ausente del árbol (turno optimista)", () => {
    expect(versionInfo(MIDDLE_EDIT, "local-1")).toBeNull();
  });

  it("versionNav expone parentKey, prevId y nextId para navegar el grupo", () => {
    expect(versionNav(MIDDLE_EDIT, "u2a")).toEqual({
      index: 1,
      count: 2,
      parentKey: "a1",
      prevId: null,
      nextId: "u2b",
    });
    expect(versionNav(MIDDLE_EDIT, "u2b")).toEqual({
      index: 2,
      count: 2,
      parentKey: "a1",
      prevId: "u2a",
      nextId: null,
    });
  });
});

describe("resolveVisiblePath / versionInfo — raíz editada (parent_id null)", () => {
  // El usuario editó el PRIMER mensaje: dos raíces hermanas, cada una con su
  // respuesta. La activa es la editada (`rb`).
  const rootEdit: SessionTreeMessage[] = [
    msg("ra", null, "user", "Pregunta original", "2026-07-10T14:00:00Z"),
    msg("aa", "ra", "assistant", "rama A", "2026-07-10T14:00:03Z"),
    msg("rb", null, "user", "Pregunta editada", "2026-07-10T14:05:00Z"),
    msg("ab", "rb", "assistant", "rama B", "2026-07-10T14:05:03Z"),
  ];
  const tree: SessionBranchTree = { messages: rootEdit, activeLeafId: "ab" };

  it("las dos raíces son hermanas bajo ROOT_PARENT_KEY, con selector 1/2 y 2/2", () => {
    expect(versionInfo(rootEdit, "ra")).toEqual({ index: 1, count: 2 });
    expect(versionInfo(rootEdit, "rb")).toEqual({ index: 2, count: 2 });
    expect(versionNav(rootEdit, "ra")?.parentKey).toBe(ROOT_PARENT_KEY);
  });

  it("default muestra la raíz activa; elegir la otra raíz cambia toda la conversación", () => {
    expect(resolveVisiblePath(tree, NO_CHOICES).map((m) => m.id)).toEqual(["rb", "ab"]);
    const choices: BranchChoices = new Map([[ROOT_PARENT_KEY, "ra"]]);
    expect(resolveVisiblePath(tree, choices).map((m) => m.id)).toEqual(["ra", "aa"]);
  });
});

describe("versionInfo — respuesta regenerada dos veces (3 versiones)", () => {
  // `POST /messages/{id}/regenerate` crea hermanos bajo el MISMO mensaje de
  // usuario: tres respuestas => `versión 1/3`, `2/3`, `3/3`.
  const regenerated: SessionTreeMessage[] = [
    msg("u1", null, "user", "Pregunta", "2026-07-10T14:00:00Z"),
    msg("a1", "u1", "assistant", "respuesta v1", "2026-07-10T14:00:03Z"),
    msg("a2", "u1", "assistant", "respuesta v2", "2026-07-10T14:01:03Z"),
    msg("a3", "u1", "assistant", "respuesta v3", "2026-07-10T14:02:03Z"),
  ];

  it("cada regeneración es una versión hermana cronológica (1/3, 2/3, 3/3)", () => {
    expect(versionInfo(regenerated, "a1")).toEqual({ index: 1, count: 3 });
    expect(versionInfo(regenerated, "a2")).toEqual({ index: 2, count: 3 });
    expect(versionInfo(regenerated, "a3")).toEqual({ index: 3, count: 3 });
  });

  it("default muestra la más reciente (3/3 = active_leaf); las flechas navegan el medio", () => {
    const tree: SessionBranchTree = { messages: regenerated, activeLeafId: "a3" };
    expect(resolveVisiblePath(tree, NO_CHOICES).map((m) => m.id)).toEqual(["u1", "a3"]);
    expect(versionNav(regenerated, "a2")).toEqual({
      index: 2,
      count: 3,
      parentKey: "u1",
      prevId: "a1",
      nextId: "a3",
    });
  });
});
