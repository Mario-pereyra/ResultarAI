import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

// @testing-library/react no limpia el DOM entre tests automáticamente a
// menos que detecte `afterEach` como global (no habilitado aquí a propósito,
// ver vitest.config.ts). Se limpia explícitamente para evitar fugas entre
// tests cuando un archivo define más de un `it`/`test`.
afterEach(() => {
  cleanup();
});
