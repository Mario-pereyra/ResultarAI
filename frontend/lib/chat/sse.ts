/**
 * Parseo de Server-Sent Events a mano (d13-chat-conversacion, tarea 3.1 del
 * frontend / contrato SSE de `resultarai/app/api/chat_stream.py`).
 *
 * El endpoint de envío de turno (`POST /sessions/{id}/messages/stream`) NO
 * es compatible con `EventSource` nativo del navegador (no soporta
 * método/body en la petición inicial) -- ver el docstring de
 * `chat_stream.py`. La UI lo consume con `fetch()` + `ReadableStream`
 * (mismo patrón que Vercel AI SDK/assistant-ui), así que hace falta
 * reimplementar el parseo de frames SSE (`id:`/`event:`/`data:` + línea en
 * blanco, comentarios `: heartbeat` a ignorar) en vez de apoyarse en el
 * parser interno del navegador. La reconexión (`GET /turns/{id}/stream`) SÍ
 * es compatible con `EventSource`, pero se usa el mismo parser acá para
 * unificar el código (ver `use-turn-stream.ts`).
 */

/** Un frame SSE de dominio ya parseado (heartbeats/comentarios se filtran antes). */
export interface SseFrame {
  id: number | null;
  event: string;
  data: string;
}

/**
 * Parsea un frame SSE crudo (las líneas entre dos separadores `\n\n`).
 * Devuelve `null` si el frame es solo un comentario de protocolo
 * (heartbeat, todas sus líneas empiezan con `:`) o si está incompleto (sin
 * `event:` -- p. ej. un frame cortado a mitad por un corte de conexión: se
 * descarta en vez de arriesgar procesar un `data` truncado).
 */
export function parseSseFrame(raw: string): SseFrame | null {
  let id: number | null = null;
  let event: string | null = null;
  const dataLines: string[] = [];
  let sawContentLine = false;

  for (const line of raw.split("\n")) {
    if (line.length === 0) continue;
    if (line.startsWith(":")) continue; // comentario de protocolo (heartbeat)
    sawContentLine = true;
    if (line.startsWith("id:")) {
      const parsed = Number.parseInt(line.slice(3).trim(), 10);
      id = Number.isNaN(parsed) ? null : parsed;
    } else if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trim());
    }
  }

  if (!sawContentLine || event === null) return null;
  return { id, event, data: dataLines.join("\n") };
}

/**
 * Consume un `ReadableStreamDefaultReader` de bytes como una secuencia de
 * frames SSE de dominio (los heartbeats se leen y se descartan en
 * silencio, nunca se producen como frame). No asume que un frame llegue
 * completo en un solo chunk de red: bufferiza hasta encontrar el separador
 * `\n\n` de cada frame (protocolo SSE); un resto sin separador final al
 * cerrarse el stream (corte de conexión a mitad de un frame) se descarta
 * sin intentar parsearlo -- mejor perder un fragmento a medio escribir que
 * arriesgar un `JSON.parse` sobre datos truncados.
 */
export async function* readSseFrames(
  reader: ReadableStreamDefaultReader<Uint8Array>,
): AsyncGenerator<SseFrame, void, unknown> {
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (value) buffer += decoder.decode(value, { stream: true });

    let separatorIndex = buffer.indexOf("\n\n");
    while (separatorIndex !== -1) {
      const rawFrame = buffer.slice(0, separatorIndex);
      buffer = buffer.slice(separatorIndex + 2);
      const frame = parseSseFrame(rawFrame);
      if (frame) yield frame;
      separatorIndex = buffer.indexOf("\n\n");
    }

    if (done) return;
  }
}
