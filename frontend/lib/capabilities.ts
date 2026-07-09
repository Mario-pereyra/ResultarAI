import type { Role } from "./session-context";

/**
 * Matriz de capacidades (tarea 5.2, d10-design-system-shell).
 *
 * CONTRATO TEMPORAL — Decision 7 de
 * openspec/changes/d10-design-system-shell/design.md: `d20-gobernanza-plataforma`
 * reemplaza esta constante estática por configuración de instancia editable
 * por el Admin, preservando el tipo `Section[]` resuelto que consume el
 * sidebar (components/shell/sidebar.tsx vía `lib/session-context.tsx`) —
 * ningún componente debe importar `CAPABILITIES_BY_ROLE` directamente si el
 * día de mañana cambia el origen del dato; siempre a través de
 * `capabilitiesForRole(role)` (o, más arriba en la cadena,
 * `SessionContextValue.capabilities` ya resuelto).
 *
 * Valores EXACTOS de la tabla "Diferencias por rol" de
 * design/VISTAS/01-acceso-shell.md Vista 3 (fila "Catálogo · Chat ·
 * Workflows · Aprobaciones · Mi espacio" + fila "Administración ·
 * Construcción"). El test unitario (`capabilities.test.ts`) recorre los 3
 * roles contra esa misma tabla, pero con los valores escritos a mano en el
 * test (no derivados de esta constante) para que un cambio accidental acá
 * rompa el test en vez de validarse a sí mismo.
 */

export type Section =
  | "catalogo"
  | "chat"
  | "workflows"
  | "aprobaciones"
  | "mi-espacio"
  | "administracion"
  | "construccion";

const BASE_SECTIONS: Section[] = [
  "catalogo",
  "chat",
  "workflows",
  "aprobaciones",
  "mi-espacio",
];

export const CAPABILITIES_BY_ROLE: Record<Role, Section[]> = {
  funcional: [...BASE_SECTIONS],
  tecnico: [...BASE_SECTIONS],
  admin: [...BASE_SECTIONS, "administracion", "construccion"],
};

export function capabilitiesForRole(role: Role): Section[] {
  return CAPABILITIES_BY_ROLE[role];
}
