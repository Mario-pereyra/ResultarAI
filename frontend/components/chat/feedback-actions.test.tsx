import userEvent from "@testing-library/user-event";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { FeedbackActions } from "./feedback-actions";

/**
 * Tests de componente del feedback 👍/👎 (d13-chat-conversacion, tarea 3.6):
 * votar sin comentario registra el voto igual; cambiar de ícono reemplaza el
 * voto anterior con un segundo `POST`; el popover ofrece un comentario
 * opcional.
 */

const LABELS = {
  like: "Me gusta",
  dislike: "No me gusta",
  prompt: "¿Querés agregar un comentario? (opcional)",
  commentLabel: "Comentario",
  send: "Enviar",
  skip: "Omitir",
  error: "No pudimos registrar tu voto. Probá de nuevo.",
};

afterEach(() => {
  vi.unstubAllGlobals();
});

function stubFetchOk() {
  const fetchMock = vi.fn(async () => new Response(JSON.stringify({}), { status: 201 }));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("FeedbackActions — votar sin comentario (tarea 3.6)", () => {
  it("pulsar 👍 y «Omitir» registra el voto sin comentario", async () => {
    const user = userEvent.setup();
    const fetchMock = stubFetchOk();
    render(<FeedbackActions messageId="msg-1" labels={LABELS} />);

    await user.click(screen.getByRole("button", { name: "Me gusta" }));

    // El popover aparece con el comentario opcional.
    expect(screen.getByText(LABELS.prompt)).toBeTruthy();
    expect(screen.getByLabelText("Comentario")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Omitir" }));

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/messages/msg-1/feedback");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ vote: "up" });

    // El popover se cierra tras resolver.
    expect(screen.queryByText(LABELS.prompt)).toBeNull();
  });
});

describe("FeedbackActions — cambiar de voto reemplaza el anterior (tarea 3.6)", () => {
  it("votar 👍 y omitir, y luego 👎 dispara un segundo POST con vote down", async () => {
    const user = userEvent.setup();
    const fetchMock = stubFetchOk();
    render(<FeedbackActions messageId="msg-1" labels={LABELS} />);

    await user.click(screen.getByRole("button", { name: "Me gusta" }));
    await user.click(screen.getByRole("button", { name: "Omitir" }));
    expect(fetchMock).toHaveBeenCalledTimes(1);

    // Cambia de ícono: el popover de comentario vuelve a aparecer.
    await user.click(screen.getByRole("button", { name: "No me gusta" }));
    expect(screen.getByText(LABELS.prompt)).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Omitir" }));

    expect(fetchMock).toHaveBeenCalledTimes(2);
    const [, secondInit] = fetchMock.mock.calls[1] as unknown as [string, RequestInit];
    expect(JSON.parse(secondInit.body as string)).toEqual({ vote: "down" });
  });

  it("«Enviar» con un comentario lo incluye en el POST", async () => {
    const user = userEvent.setup();
    const fetchMock = stubFetchOk();
    render(<FeedbackActions messageId="msg-2" labels={LABELS} />);

    await user.click(screen.getByRole("button", { name: "Me gusta" }));
    await user.type(screen.getByLabelText("Comentario"), "Muy útil, gracias");
    await user.click(screen.getByRole("button", { name: "Enviar" }));

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({
      vote: "up",
      comment: "Muy útil, gracias",
    });
  });
});
