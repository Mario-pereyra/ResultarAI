"use client";

export interface StarterSuggestionsProps {
  /**
   * `agent.starter_prompts[]` (`GET /api/agents/{id}`, tarea 3.5): contenido
   * de catálogo, no strings de UI -- vienen ya en español desde el Agent
   * Manifest, así que NO pasan por el catálogo i18n (`design/VISTAS/02-chat.md`
   * vista 05, notas i18n: "El saludo y las sugerencias vienen de la config
   * del agente -- se traducen como datos de catálogo").
   */
  prompts: string[];
  /** Click en una sugerencia: inserta el texto en el composer y le da foco,
   * SIN enviar el turno (`chat-content.tsx` decide qué hacer con el texto). */
  onSelect: (text: string) => void;
}

/**
 * Sugerencias de inicio clicables (d13-chat-conversacion, tarea 3.5). Solo
 * la renderiza quien la use en el estado "sesión nueva sin mensajes"
 * (`message-column.tsx`, slot `emptyStateExtra`) -- este componente no
 * decide cuándo mostrarse, solo qué mostrar dado el array de prompts.
 */
export function StarterSuggestions({ prompts, onSelect }: StarterSuggestionsProps) {
  if (prompts.length === 0) return null;

  return (
    <div className="chat-starters">
      {prompts.map((prompt) => (
        <button
          key={prompt}
          type="button"
          className="chat-starters__item"
          onClick={() => onSelect(prompt)}
        >
          {prompt}
        </button>
      ))}
    </div>
  );
}
