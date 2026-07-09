import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AiBanner } from "./ai-banner";

const TEXT_FULL = "Respuestas generadas por IA — verificá antes de aplicar en cliente";
const TEXT_SHORT = "Respuestas generadas por IA — verificá antes de aplicar";

describe("AiBanner", () => {
  it('escenario "Banner presente sin acción de cierre": .ai-banner está presente y no expone ningún botón/gesto de cierre', () => {
    const { container } = render(<AiBanner textFull={TEXT_FULL} textShort={TEXT_SHORT} />);

    const banner = container.querySelector(".ai-banner");
    expect(banner).not.toBeNull();
    expect(banner?.querySelector("button")).toBeNull();
    expect(banner?.querySelector("[aria-label]")).toBeNull();
  });

  it('escenario "Banner se acorta en móvil sin desaparecer": ambas variantes de texto/clase están presentes en el DOM', () => {
    const { container } = render(<AiBanner textFull={TEXT_FULL} textShort={TEXT_SHORT} />);

    const full = container.querySelector(".ai-banner__text--full");
    const short = container.querySelector(".ai-banner__text--short");

    expect(full?.textContent).toBe(TEXT_FULL);
    expect(short?.textContent).toBe(TEXT_SHORT);
  });
});
