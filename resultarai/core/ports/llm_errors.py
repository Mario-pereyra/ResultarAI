"""Typed exception hierarchy for the LLM port."""


class LLMError(Exception):
    """Base exception class for all LLM errors."""


class LLMProfileUnavailableError(LLMError):
    """Raised when a profile is unavailable (e.g. missing credentials or configuration)."""

    def __init__(self, profile_id: str, message: str | None = None) -> None:
        if message is None:
            message = f"LLM profile '{profile_id}' is unavailable."
        super().__init__(message)
        self.profile_id = profile_id


class LLMCascadeExhaustedError(LLMError):
    """Raised when the fallback cascade is exhausted."""

    def __init__(
        self,
        attempted_profiles: list[str],
        failures: dict[str, str],
        message: str | None = None,
    ) -> None:
        if message is None:
            message = (
                f"LLM fallback cascade exhausted after attempting: {attempted_profiles}. "
                f"Failures encountered: {failures}"
            )
        super().__init__(message)
        self.attempted_profiles = attempted_profiles
        self.failures = failures
