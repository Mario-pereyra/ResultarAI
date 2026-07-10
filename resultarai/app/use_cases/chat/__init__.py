"""Casos de uso de chat: sesiones, turnos, ramas, streaming, escalación y feedback
(d13-chat-conversacion).
"""

from resultarai.app.use_cases.chat.escalation import (
    EscalationDisabledError,
    EscalationMisconfiguredError,
    EscalationResult,
    NoEligibleOriginMessageError,
    OriginMessageNotEligibleError,
    escalate_session,
)
from resultarai.app.use_cases.chat.feedback import (
    FeedbackResult,
    FeedbackSubmitter,
    MessageNotEligibleForFeedbackError,
    submit_message_feedback,
)
from resultarai.app.use_cases.chat.feedback import (
    MessageNotFoundError as FeedbackMessageNotFoundError,
)
from resultarai.app.use_cases.chat.sessions import (
    AgentNotFoundError,
    EmptyFallbackCascadeError,
    create_session,
)
from resultarai.app.use_cases.chat.stream_registry import (
    BufferedSseEvent,
    TurnStreamBuffer,
    TurnStreamRegistry,
)
from resultarai.app.use_cases.chat.streaming import (
    EscalationDetected,
    EscalationPayload,
    StreamingResponseGenerator,
    TextFragment,
    TurnCompletion,
    TurnFragment,
    filter_escalation_marker,
    start_turn_stream,
)
from resultarai.app.use_cases.chat.turns import (
    MessageEditForbiddenError,
    MessageNotEligibleError,
    MessageNotFoundError,
    RegenerateResult,
    ResponseGenerator,
    SessionNotFoundError,
    TurnResult,
    regenerate_response,
    send_turn,
)

__all__ = [
    "AgentNotFoundError",
    "BufferedSseEvent",
    "EmptyFallbackCascadeError",
    "EscalationDetected",
    "EscalationDisabledError",
    "EscalationMisconfiguredError",
    "EscalationPayload",
    "EscalationResult",
    "FeedbackMessageNotFoundError",
    "FeedbackResult",
    "FeedbackSubmitter",
    "MessageEditForbiddenError",
    "MessageNotEligibleError",
    "MessageNotEligibleForFeedbackError",
    "MessageNotFoundError",
    "NoEligibleOriginMessageError",
    "OriginMessageNotEligibleError",
    "RegenerateResult",
    "ResponseGenerator",
    "SessionNotFoundError",
    "StreamingResponseGenerator",
    "TextFragment",
    "TurnCompletion",
    "TurnFragment",
    "TurnResult",
    "TurnStreamBuffer",
    "TurnStreamRegistry",
    "create_session",
    "escalate_session",
    "filter_escalation_marker",
    "regenerate_response",
    "send_turn",
    "start_turn_stream",
    "submit_message_feedback",
]
