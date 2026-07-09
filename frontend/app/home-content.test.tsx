import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { HomeContent } from "./home-content";

describe("HomeContent", () => {
  it("renderiza el título y el saludo recibidos por props", () => {
    render(
      <HomeContent
        title="ResultarAI"
        greeting="Bienvenido, escribí tu consulta."
      />,
    );

    const heading = screen.getByRole("heading", { name: "ResultarAI" });
    expect(heading.textContent).toBe("ResultarAI");

    const greeting = screen.getByText("Bienvenido, escribí tu consulta.");
    expect(greeting.textContent).toBe("Bienvenido, escribí tu consulta.");
  });
});
