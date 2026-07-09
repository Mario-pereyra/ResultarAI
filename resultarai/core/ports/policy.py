"""PolicyPort Protocol definition."""

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from resultarai.core.manifests import PolicyManifest
    from resultarai.core.policy import ActionRequest, PolicyDecision


class PolicyPort(Protocol):
    """Protocol for the policy gate evaluation.

    Allows replacing the Policy Gate engine without modifying callers.
    """

    def evaluate(
        self,
        request: "ActionRequest",
        active_policies: list["PolicyManifest"],
    ) -> "PolicyDecision":
        """Evaluate an ActionRequest against active policies to return a PolicyDecision."""
        ...
