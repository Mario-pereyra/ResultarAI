"""Casos de uso de chat: sesiones, turnos, ramas, streaming, escalación, feedback y
composición de adjuntos (d13-chat-conversacion, d14-attachments tareas 6.1-6.3).
"""

from resultarai.app.use_cases.chat._attachments import (
    AttachmentNotFoundError,
    AttachmentNotSendableError,
    ComposedMessage,
    MessageTokenBudgetExceededError,
    SectionNotFoundError,
    request_attachment_fragment,
)
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
from resultarai.app.use_cases.chat.history import (
    InProgressTurn,
    SearchHit,
    SessionDetail,
    SessionSummary,
    get_session_detail,
    list_sessions,
    search_sessions,
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
    TurnAlreadyInProgressError,
    TurnCompletion,
    TurnFragment,
    filter_escalation_marker,
    start_turn_stream,
)
from resultarai.app.use_cases.chat.telemetry import (
    TECHNICAL_ROLES,
    RawTurnMetadata,
    build_raw_turn_metadata,
    is_technical_role,
    layer_turn_metadata,
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
    "TECHNICAL_ROLES",
    "AgentNotFoundError",
    "AttachmentNotFoundError",
    "AttachmentNotSendableError",
    "BufferedSseEvent",
    "ComposedMessage",
    "EmptyFallbackCascadeError",
    "EscalationDetected",
    "EscalationDisabledError",
    "EscalationMisconfiguredError",
    "EscalationPayload",
    "EscalationResult",
    "FeedbackMessageNotFoundError",
    "FeedbackResult",
    "FeedbackSubmitter",
    "InProgressTurn",
    "MessageEditForbiddenError",
    "MessageNotEligibleError",
    "MessageNotEligibleForFeedbackError",
    "MessageNotFoundError",
    "MessageTokenBudgetExceededError",
    "NoEligibleOriginMessageError",
    "OriginMessageNotEligibleError",
    "RawTurnMetadata",
    "RegenerateResult",
    "ResponseGenerator",
    "SearchHit",
    "SectionNotFoundError",
    "SessionDetail",
    "SessionNotFoundError",
    "SessionSummary",
    "StreamingResponseGenerator",
    "TextFragment",
    "TurnAlreadyInProgressError",
    "TurnCompletion",
    "TurnFragment",
    "TurnResult",
    "TurnStreamBuffer",
    "TurnStreamRegistry",
    "build_raw_turn_metadata",
    "create_session",
    "escalate_session",
    "filter_escalation_marker",
    "get_session_detail",
    "is_technical_role",
    "layer_turn_metadata",
    "list_sessions",
    "regenerate_response",
    "request_attachment_fragment",
    "search_sessions",
    "send_turn",
    "start_turn_stream",
    "submit_message_feedback",
]
