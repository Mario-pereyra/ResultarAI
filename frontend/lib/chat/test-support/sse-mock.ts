/**
 * Helpers de test para simular el contrato SSE de `chat_stream.py` sin
 * depender de una `Response`/`ReadableStream` nativa real (evita cualquier
 * incertidumbre sobre qué globals de streams provee el entorno jsdom de
 * Vitest). Usado por `lib/chat/use-turn-stream.test.ts` y
 * `components/chat/message-column.test.tsx`.
 *
 * NO es código de producción: vive bajo `lib/chat/test-support/` a
 * propósito, fuera de los directorios auditados por
 * `scripts/check-hardcoded-strings.mjs`/`check-hardcoded-colors.mjs` (que
 * solo miran `app/`, `components/`, `styles/`) y sin sufijo `.test.ts`
 * (Vitest solo ejecuta como test lo que matchea `**\/*.test.{ts,tsx}`).
 */

type ChunkReadResult = { done: boolean; value?: Uint8Array };

/**
 * Cola controlable a mano que imita un `ReadableStreamDefaultReader<Uint8Array>`:
 * el test decide exactamente cuándo "llega" cada chunk (`push`) y cuándo se
 * corta la conexión (`close`, sin haber llegado nunca al evento `done` de
 * dominio -- simula un corte de red) en vez de depender del scheduling
 * asíncrono real de un `ReadableStream`.
 */
export function createControlledReader() {
  const encoder = new TextEncoder();
  const queue: ChunkReadResult[] = [];
  let pendingResolve: ((chunk: ChunkReadResult) => void) | null = null;

  function deliver(chunk: ChunkReadResult) {
    if (pendingResolve) {
      const resolve = pendingResolve;
      pendingResolve = null;
      resolve(chunk);
    } else {
      queue.push(chunk);
    }
  }

  return {
    /** Entrega un chunk de texto crudo (ya con el formato de frame SSE, ver `sseFrame`). */
    push(text: string) {
      deliver({ done: false, value: encoder.encode(text) });
    },
    /** Cierra el stream (con o sin haber mandado un evento `done` de dominio antes). */
    close() {
      deliver({ done: true });
    },
    reader: {
      read(): Promise<ChunkReadResult> {
        if (queue.length > 0) {
          const next = queue.shift();
          if (next) return Promise.resolve(next);
        }
        return new Promise((resolve) => {
          pendingResolve = resolve;
        });
      },
    },
  };
}

export interface MockSseResponseInit {
  status?: number;
  headers?: Record<string, string>;
  /** Cuerpo JSON devuelto por `.json()` (para simular el 409 con `turn_id`). */
  jsonBody?: unknown;
}

/**
 * Objeto duck-typed compatible con lo que `use-turn-stream.ts` espera de
 * `fetch()` -- solo usa `.ok`/`.status`/`.headers.get`/`.body.getReader`/`.json`,
 * nunca la clase `Response` real.
 */
export function mockSseResponse(
  reader: { read: () => Promise<ChunkReadResult> },
  init: MockSseResponseInit = {},
) {
  const status = init.status ?? 200;
  const headerMap = new Map(Object.entries(init.headers ?? {}));
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: (name: string) => headerMap.get(name) ?? null },
    body: { getReader: () => reader },
    json: async () => init.jsonBody ?? {},
  };
}

/** Un frame SSE crudo (`id:`/`event:`/`data:` + línea en blanco), ver `lib/chat/sse.ts`. */
export function sseFrame(id: number, event: string, data: unknown): string {
  return `id: ${id}\nevent: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

/** Un comentario SSE de heartbeat (`: heartbeat`), sin `id`/`event`/`data`. */
export function heartbeatFrame(): string {
  return ": heartbeat\n\n";
}
