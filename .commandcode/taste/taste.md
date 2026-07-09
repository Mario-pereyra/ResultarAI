# Taste (Continuously Learned by [CommandCode][cmd])

[cmd]: https://commandcode.ai/

# claude-code
- Route subagents to the appropriate Claude model (haiku for simple tasks like grep/file-search/git, sonnet for analysis/research, opus/fable only for complex architectural decisions or deep debugging) — do NOT let all subagents inherit the session model, especially when using Fable 5 (x5 cost). Use CLAUDE_CODE_SUBAGENT_MODEL env var or per-agent model field. Confidence: 0.75
- Use community meta-orchestration agents from VoltAgent/awesome-claude-code-subagents (especially categories/09-meta-orchestration/) for agent routing and installation. Install via the agent-installer.md when needed. Confidence: 0.65

