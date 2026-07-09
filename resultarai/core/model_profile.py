"""ModelProfile schema definition."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ModelProfile(BaseModel):
    """Pydantic model representing a model profile configuration."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)
    cache_hit_rate: float = Field(ge=0.0)
    cache_miss_rate: float = Field(ge=0.0)
    active: bool = True
