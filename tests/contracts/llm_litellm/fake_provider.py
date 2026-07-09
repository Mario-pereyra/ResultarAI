"""Fake LiteLLM provider for contract testing."""

from typing import Any


class FakePromptTokensDetails:
    def __init__(self, cached_tokens: int) -> None:
        self.cached_tokens = cached_tokens

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


class FakeUsage:
    def __init__(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        prompt_tokens_details: FakePromptTokensDetails | None = None,
        cache_read_input_tokens: int | None = None,
    ) -> None:
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens
        self.prompt_tokens_details = prompt_tokens_details
        self.cache_read_input_tokens = cache_read_input_tokens

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


class FakeMessage:
    def __init__(self, content: str, role: str = "assistant") -> None:
        self.content = content
        self.role = role

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


class FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = FakeMessage(content)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


class FakeCompletionResponse:
    def __init__(
        self,
        content: str,
        model: str,
        usage: FakeUsage | None = None,
    ) -> None:
        self.choices = [FakeChoice(content)]
        self.model = model
        self.usage = usage

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


class ModelBehavior:
    def __init__(
        self,
        response_text: str = "Success response",
        prompt_tokens: int = 100,
        completion_tokens: int = 50,
        cached_tokens: int | None = None,
        cache_read_input_tokens: int | None = None,
        exception: Exception | None = None,
        absent_usage: bool = False,
        absent_cache: bool = False,
    ) -> None:
        self.response_text = response_text
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.cached_tokens = cached_tokens
        self.cache_read_input_tokens = cache_read_input_tokens
        self.exception = exception
        self.absent_usage = absent_usage
        self.absent_cache = absent_cache


class FakeProvider:
    def __init__(self) -> None:
        self.behaviors: dict[str, ModelBehavior] = {}
        self.calls: list[dict[str, Any]] = []

    def configure_behavior(self, model: str, behavior: ModelBehavior) -> None:
        self.behaviors[model] = behavior

    def completion(self, model: str, messages: list[dict[str, Any]], **kwargs: Any) -> Any:
        self.calls.append({"model": model, "messages": messages, "kwargs": kwargs})

        behavior = ModelBehavior() if model not in self.behaviors else self.behaviors[model]

        if behavior.exception is not None:
            raise behavior.exception

        if behavior.absent_usage:
            usage = None
        elif behavior.absent_cache:
            usage = FakeUsage(
                prompt_tokens=behavior.prompt_tokens,
                completion_tokens=behavior.completion_tokens,
                total_tokens=behavior.prompt_tokens + behavior.completion_tokens,
            )
        else:
            pt_details = None
            if behavior.cached_tokens is not None:
                pt_details = FakePromptTokensDetails(cached_tokens=behavior.cached_tokens)

            usage = FakeUsage(
                prompt_tokens=behavior.prompt_tokens,
                completion_tokens=behavior.completion_tokens,
                total_tokens=behavior.prompt_tokens + behavior.completion_tokens,
                prompt_tokens_details=pt_details,
                cache_read_input_tokens=behavior.cache_read_input_tokens,
            )

        return FakeCompletionResponse(
            content=behavior.response_text,
            model=model,
            usage=usage,
        )
