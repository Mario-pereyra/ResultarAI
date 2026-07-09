# Langfuse Tracing Adapter Naming Conventions

This directory implements the `TracePort` adapter for Langfuse telemetries.

## Naming Conventions
- **Trace Name**: `default_chat_turn`
- **Scores**:
  - Thumbs up/down: `user-thumbs` (BOOLEAN: 1 for 👍, 0 for 👎)
- **Tags**:
  - Regression candidates: `regression-candidate`

## URL Patterns (for Admin console redirects)
Admin dashboard panels link directly to the native Langfuse UI using these URL formats:
- **Trace URL**: `{LANGFUSE_HOST}/project/{project_id}/traces/{trace_id}`
- **Session URL**: `{LANGFUSE_HOST}/project/{project_id}/sessions/{session_id}`
