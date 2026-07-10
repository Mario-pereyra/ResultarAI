"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import { Textarea } from "@/components/ui/textarea";
import { csrfHeaders } from "@/lib/csrf";

export type FeedbackVote = "up" | "down";

export interface FeedbackActionsLabels {
  like: string;
  dislike: string;
  prompt: string;
  commentLabel: string;
  send: string;
  skip: string;
  error: string;
}

export interface FeedbackActionsProps {
  /** Id del mensaje `assistant` calificado (`POST /api/messages/{id}/feedback`). */
  messageId: string;
  labels: FeedbackActionsLabels;
}

/**
 * Acciones de feedback 👍/👎 bajo una respuesta del agente ya completada
 * (d13-chat-conversacion, tarea 3.6, `design/VISTAS/02-chat.md` vista 05:
 * "al pulsar 👍/👎 el ícono queda activo y aparece popover [...] con
 * textarea + «Enviar» + «Omitir»").
 *
 * El voto se registra recién al resolver el popover (Enviar u Omitir) --
 * ambos casos llaman a `POST /messages/{id}/feedback`, la única diferencia
 * es si viaja `comment`. Cambiar de ícono reemplaza el voto: el backend lo
 * trata como un score nuevo (ver `use_cases/chat/feedback.py`), nunca como
 * edición del anterior.
 *
 * El voto activo vive en estado LOCAL de este componente (se pierde en un
 * refresh): Langfuse es append-only y hoy no existe un `GET` que agregue
 * "mi voto actual" por mensaje -- ver `openspec/BACKLOG-DESCUBRIMIENTOS.md`
 * (tareas 1.8/3.6).
 */
export function FeedbackActions({ messageId, labels }: FeedbackActionsProps) {
  const [activeVote, setActiveVote] = useState<FeedbackVote | null>(null);
  const [pendingVote, setPendingVote] = useState<FeedbackVote | null>(null);
  const [popoverOpen, setPopoverOpen] = useState(false);
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(false);

  function selectVote(vote: FeedbackVote) {
    setActiveVote(vote);
    setPendingVote(vote);
    setComment("");
    setError(false);
    setPopoverOpen(true);
  }

  async function resolvePopover(withComment: boolean) {
    const vote = pendingVote;
    if (!vote) return;
    setSubmitting(true);
    setError(false);
    const trimmedComment = comment.trim();
    try {
      const res = await fetch(`/api/messages/${messageId}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...csrfHeaders() },
        body: JSON.stringify({
          vote,
          ...(withComment && trimmedComment ? { comment: trimmedComment } : {}),
        }),
      });
      if (!res.ok) throw new Error("feedback request failed");
      setPopoverOpen(false);
      setComment("");
    } catch {
      setError(true);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="msg-feedback">
      <div className="msg-feedback__buttons">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          aria-label={labels.like}
          aria-pressed={activeVote === "up"}
          className={activeVote === "up" ? "msg-feedback__btn is-active" : "msg-feedback__btn"}
          onClick={() => selectVote("up")}
        >
          👍
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          aria-label={labels.dislike}
          aria-pressed={activeVote === "down"}
          className={activeVote === "down" ? "msg-feedback__btn is-active" : "msg-feedback__btn"}
          onClick={() => selectVote("down")}
        >
          👎
        </Button>
      </div>
      {popoverOpen ? (
        <Panel variant="raised" className="msg-feedback__popover">
          <p className="msg-feedback__prompt">{labels.prompt}</p>
          <Textarea
            label={labels.commentLabel}
            value={comment}
            onChange={(event) => setComment(event.target.value)}
            rows={2}
          />
          <div className="msg-feedback__popover-actions">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={submitting}
              onClick={() => void resolvePopover(false)}
            >
              {labels.skip}
            </Button>
            <Button
              type="button"
              variant="primary"
              size="sm"
              disabled={submitting}
              onClick={() => void resolvePopover(true)}
            >
              {labels.send}
            </Button>
          </div>
          {error ? (
            <p className="msg-feedback__error" role="alert">
              {labels.error}
            </p>
          ) : null}
        </Panel>
      ) : null}
    </div>
  );
}
