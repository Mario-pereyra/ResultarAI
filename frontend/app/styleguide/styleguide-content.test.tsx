import userEvent from "@testing-library/user-event";
import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import messages from "@/messages/es.json";
import { StyleguideContent } from "./styleguide-content";

function renderStyleguide() {
  return render(
    <NextIntlClientProvider locale="es" messages={messages}>
      <StyleguideContent />
    </NextIntlClientProvider>,
  );
}

beforeEach(() => {
  // El switcher parte siempre de dark·default en cada test (mismos
  // defaults que app/layout.tsx) — jsdom conserva el <html> entre tests.
  document.documentElement.removeAttribute("data-theme");
  document.documentElement.removeAttribute("data-brand");
});

afterEach(() => {
  document.documentElement.removeAttribute("data-theme");
  document.documentElement.removeAttribute("data-brand");
});

describe('Styleguide — escenario "Styleguide renderiza los 4 sets" (tarea 7.3)', () => {
  it("al montar, aplica dark·default a <html> (mismo default que la instancia)", () => {
    renderStyleguide();
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(document.documentElement.dataset.brand).toBe("default");
    expect(screen.getByText("Combinación activa: oscuro · default")).not.toBeNull();
  });

  it("el switcher alterna data-theme y data-brand en <html>, recorriendo las 4 combinaciones", async () => {
    const user = userEvent.setup();
    renderStyleguide();

    const seen = new Set<string>();
    seen.add(`${document.documentElement.dataset.theme}-${document.documentElement.dataset.brand}`);

    const themeButton = screen.getByRole("button", { name: /^Tema:/ });
    const brandButton = screen.getByRole("button", { name: /^Marca:/ });

    await user.click(brandButton); // dark·totvs
    seen.add(`${document.documentElement.dataset.theme}-${document.documentElement.dataset.brand}`);
    expect(document.documentElement.dataset.brand).toBe("totvs");

    await user.click(themeButton); // light·totvs
    seen.add(`${document.documentElement.dataset.theme}-${document.documentElement.dataset.brand}`);
    expect(document.documentElement.dataset.theme).toBe("light");

    await user.click(brandButton); // light·default
    seen.add(`${document.documentElement.dataset.theme}-${document.documentElement.dataset.brand}`);
    expect(document.documentElement.dataset.brand).toBe("default");

    await user.click(themeButton); // dark·default (vuelta al inicio)
    seen.add(`${document.documentElement.dataset.theme}-${document.documentElement.dataset.brand}`);

    expect(seen).toEqual(
      new Set(["dark-default", "dark-totvs", "light-totvs", "light-default"]),
    );
  });

  it("el grupo del switcher expone un aria-label de grupo (accesible por teclado/lector)", () => {
    renderStyleguide();
    expect(screen.getByRole("group", { name: "Vista previa: cambiar tema y marca" })).not.toBeNull();
  });

  it("la ruta no tiene navegación de shell (sin sidebar/topbar de producción) — es standalone", () => {
    const { container } = renderStyleguide();
    expect(container.querySelector(".shell-sidebar")).toBeNull();
    expect(container.querySelector(".shell-topbar")).toBeNull();
  });
});

describe("Styleguide — demo de cada componente base del inventario (tarea 7.3)", () => {
  it("botón: variantes primary/secondary/danger/ghost presentes", () => {
    renderStyleguide();
    // "Aprobar escritura" aparece más de una vez a propósito (default +
    // estado loading, ambos con el mismo label — el texto nunca se quita
    // en loading, design/DESIGN-SYSTEM.md §8.1).
    expect(screen.getAllByRole("button", { name: "Aprobar escritura" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("button", { name: "Ver evidencia" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("button", { name: "Eliminar usuario" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("button", { name: "Cancelar" }).length).toBeGreaterThan(0);
  });

  it("fields: input con hint, input con error y textarea están presentes", () => {
    renderStyleguide();
    // El label accesible incluye el indicador "*" de campo obligatorio
    // (Field/.req, design/DESIGN-SYSTEM.md §8.2), por eso el match es por
    // regex en vez de texto exacto.
    expect(screen.getByLabelText(/Nombre del cliente final/)).not.toBeNull();
    expect(screen.getByText("Ingresá un correo válido, p. ej. lucia@resultar.bo")).not.toBeNull();
    expect(screen.getByLabelText(/Comentario de aprobación/)).not.toBeNull();
  });

  it("tabla densa: caption, columna .num y fila seleccionada presentes", () => {
    const { container } = renderStyleguide();
    expect(screen.getByText("Validación de parámetros en Comercial Andina S.A. — ambiente TEST")).not.toBeNull();
    expect(container.querySelector(".table--dense")).not.toBeNull();
    expect(container.querySelector("tr.is-selected")).not.toBeNull();
    expect(container.querySelectorAll("td.num").length).toBeGreaterThan(0);
  });

  it("panel, tags y badges de rol: los 3 badge-rol están presentes", () => {
    const { container } = renderStyleguide();
    expect(container.querySelector(".badge-rol--admin")).not.toBeNull();
    expect(container.querySelector(".badge-rol--tecnico")).not.toBeNull();
    expect(container.querySelector(".badge-rol--funcional")).not.toBeNull();
    expect(screen.getByText("riesgo crítico")).not.toBeNull();
  });

  it("toast: disparar un toast info lo agrega al stack con su título/mensaje", async () => {
    const user = userEvent.setup();
    renderStyleguide();

    await user.click(screen.getByRole("button", { name: "Mostrar toast info" }));

    expect(screen.getByText("Sesión exportada")).not.toBeNull();
    expect(screen.getByText("El enlace se copió al portapapeles.")).not.toBeNull();
  });

  it("modal: abrir muestra el diálogo con trampa de foco (ya cubierta por components/ui/modal.test.tsx)", async () => {
    const user = userEvent.setup();
    renderStyleguide();

    await user.click(screen.getByRole("button", { name: "Abrir modal de ejemplo" }));

    expect(screen.getByRole("dialog", { name: "Eliminar usuario" })).not.toBeNull();
  });

  it("dropdown: abrir expone el menú con sus ítems", async () => {
    const user = userEvent.setup();
    renderStyleguide();

    await user.click(screen.getByRole("button", { name: "Menú de ejemplo" }));

    expect(screen.getByRole("menuitem", { name: "Ver evidencia" })).not.toBeNull();
    expect(screen.getByRole("menuitem", { name: "Cerrar sesión" })).not.toBeNull();
  });

  it("tooltip: el disparador lleva el atributo data-tip (burbuja CSS, ver styles/components/tooltip.css)", () => {
    renderStyleguide();
    const trigger = screen.getByRole("button", { name: "Pasá el mouse o enfocá con Tab" });
    expect(trigger.getAttribute("data-tip")).toBe("Prefijo servido desde cache: ahorro ~90%");
  });

  it("skeleton y empty state: ambos empty-state (con y sin CTA) están presentes", () => {
    renderStyleguide();
    expect(screen.getByText("Sin aprobaciones pendientes")).not.toBeNull();
    expect(screen.getByRole("button", { name: "Abrir catálogo" })).not.toBeNull();
  });
});

describe('Styleguide — escenario "Formato de fecha en es-BO" y muestras es-BO (tarea 6.3)', () => {
  it("muestra la fecha-hora de ejemplo formateada dd/mm/aaaa HH:mm vía Intl es-BO", () => {
    renderStyleguide();
    expect(screen.getByText("11/06/2026 14:32")).not.toBeNull();
    expect(screen.getByText("11/06/2026")).not.toBeNull();
  });

  it("muestra costo LLM, monto agregado, porcentaje y tokens abreviados en formato es-BO", () => {
    renderStyleguide();
    expect(screen.getByText("USD 0,0042")).not.toBeNull();
    expect(screen.getByText("USD 1.284,50")).not.toBeNull();
    expect(screen.getByText("82%")).not.toBeNull();
    expect(screen.getByText("12,4k tok")).not.toBeNull();
  });
});
