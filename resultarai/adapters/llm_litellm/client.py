"""LiteLLM adapter client implementing the LLMPort protocol."""

from typing import Any

import litellm

from resultarai.core.model_profile import ModelProfile
from resultarai.core.ports.llm import LLMPort, LLMResponse
from resultarai.core.ports.llm_errors import LLMCascadeExhaustedError


class LiteLLMClient(LLMPort):
    """Adapter client for LiteLLM completion services."""

    def __init__(self, model_profiles: dict[str, ModelProfile]) -> None:
        """Initialize the LiteLLM client with the given model profiles."""
        self.model_profiles = model_profiles

    def generate(self, prompt: str, **kwargs: Any) -> LLMResponse:
        """Generate response text from a given prompt, using the fallback cascade."""
        fallback_cascade = kwargs.get("fallback_cascade", [])
        if not fallback_cascade:
            raise LLMCascadeExhaustedError(
                attempted_profiles=[],
                failures={"general": "No fallback cascade provided in call arguments."},
            )

        attempted_profiles: list[str] = []
        failures: dict[str, str] = {}
        first_failure_message: str | None = None
        first_profile_id: str | None = None

        for profile_id in fallback_cascade:
            if first_profile_id is None:
                first_profile_id = profile_id

            attempted_profiles.append(profile_id)

            # 1. Check if the profile ID exists and is active
            profile = self.model_profiles.get(profile_id)
            if not profile:
                err_msg = f"Profile '{profile_id}' not found in configuration."
                failures[profile_id] = err_msg
                if first_failure_message is None:
                    first_failure_message = err_msg
                continue

            if not profile.active:
                err_msg = f"Profile '{profile_id}' is inactive."
                failures[profile_id] = err_msg
                if first_failure_message is None:
                    first_failure_message = err_msg
                continue

            # 2. Call litellm.completion
            messages = [{"role": "user", "content": prompt}]
            try:
                response = litellm.completion(
                    model=profile.model,
                    messages=messages,
                    **profile.parameters,
                )

                # 3. Translate successful response to LLMResponse
                text = ""
                if response.choices and len(response.choices) > 0:
                    # choices[0].message could be a dict or object
                    message_obj = response.choices[0].message
                    if hasattr(message_obj, "content"):
                        text = message_obj.content or ""
                    elif isinstance(message_obj, dict):
                        text = message_obj.get("content") or ""

                usage = getattr(response, "usage", None)
                prompt_tokens: int | None = None
                cache_hit_tokens: int | None = None
                cache_miss_tokens: int | None = None

                if usage is not None:
                    prompt_tokens = getattr(usage, "prompt_tokens", None)
                    if prompt_tokens is None and hasattr(usage, "get"):
                        prompt_tokens = usage.get("prompt_tokens")

                    # OpenAI style
                    pt_details = getattr(usage, "prompt_tokens_details", None)
                    if pt_details is None and hasattr(usage, "get"):
                        pt_details = usage.get("prompt_tokens_details")

                    cached_tokens: int | None = None
                    if pt_details is not None:
                        cached_tokens = getattr(pt_details, "cached_tokens", None)
                        if cached_tokens is None and hasattr(pt_details, "get"):
                            cached_tokens = pt_details.get("cached_tokens")

                    # Anthropic style
                    cache_read: int | None = None
                    cache_read = getattr(usage, "cache_read_input_tokens", None)
                    if cache_read is None and hasattr(usage, "get"):
                        cache_read = usage.get("cache_read_input_tokens")

                    if cached_tokens is not None:
                        cache_hit_tokens = cached_tokens
                        if prompt_tokens is not None:
                            cache_miss_tokens = max(0, prompt_tokens - cached_tokens)
                    elif cache_read is not None:
                        cache_hit_tokens = cache_read
                        if prompt_tokens is not None:
                            cache_miss_tokens = max(0, prompt_tokens - cache_read)

                # Calculate cost
                cost_usd: float | None = None
                if cache_hit_tokens is not None and cache_miss_tokens is not None:
                    cost_usd = (cache_hit_tokens * profile.cache_hit_rate) + (
                        cache_miss_tokens * profile.cache_miss_rate
                    )
                elif prompt_tokens is not None:
                    cost_usd = float(prompt_tokens * profile.cache_miss_rate)

                is_alternate = profile_id != first_profile_id

                return LLMResponse(
                    text=text,
                    model_profile_id=profile_id,
                    is_alternate_model=is_alternate,
                    primary_model_profile_id=first_profile_id if is_alternate else None,
                    fallback_reason=first_failure_message if is_alternate else None,
                    cache_hit_tokens=cache_hit_tokens,
                    cache_miss_tokens=cache_miss_tokens,
                    cost_usd=cost_usd,
                    needs_pro=False,
                )

            except Exception as e:
                err_msg = str(e) or type(e).__name__
                failures[profile_id] = err_msg
                if first_failure_message is None:
                    first_failure_message = err_msg
                continue

        # If all profiles failed, raise error
        raise LLMCascadeExhaustedError(
            attempted_profiles=attempted_profiles,
            failures=failures,
        )
