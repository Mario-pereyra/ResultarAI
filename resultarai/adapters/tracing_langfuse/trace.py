"""Langfuse tracing adapter implementing the TracePort protocol."""

from typing import Any

from resultarai.adapters.tracing_langfuse.client import get_langfuse_client, mask_user_identity
from resultarai.adapters.tracing_langfuse.models import TurnTrace
from resultarai.core.ports.trace import TracePort


class LangfuseTraceAdapter(TracePort):
    """Adapter for Langfuse tracing implementing TracePort."""

    def __init__(self, client: Any = None) -> None:
        """Initialize the adapter with a Langfuse client."""
        self.client = client if client is not None else get_langfuse_client()
        self._traces: dict[str, Any] = {}
        self._policy_decisions: dict[str, list[Any]] = {}

    def _get_or_create_trace(self, turn_id: str, inputs: dict[str, Any]) -> Any:
        """Retrieve an existing trace or lazily create a new one."""
        if turn_id in self._traces:
            return self._traces[turn_id]

        user_id = inputs.get("user_id") or inputs.get("user") or ""
        session_id = inputs.get("session_id") or inputs.get("thread_id") or ""
        prompt = inputs.get("prompt") or ""

        masked_user_id = mask_user_identity(user_id) if user_id else ""

        trace = self.client.trace(
            id=turn_id,
            name="default_chat_turn",
            user_id=masked_user_id,
            session_id=session_id,
            input=prompt,
        )
        self._traces[turn_id] = trace
        return trace

    def trace_step(
        self,
        step_name: str,
        inputs: dict[str, Any],
        outputs: dict[str, Any],
    ) -> None:
        """Trace a single execution step incrementally."""
        turn_id = inputs.get("turn_id") or outputs.get("turn_id")
        if not turn_id:
            return

        trace = self._get_or_create_trace(turn_id, inputs)

        # Merge scan_result from inputs/outputs if present
        scan_result = inputs.get("scan_result") or outputs.get("scan_result")
        if scan_result:
            trace.update(metadata=scan_result)

        # Check for prompt_version in inputs/outputs
        prompt_version = inputs.get("prompt_version") or outputs.get("prompt_version")
        if prompt_version:
            trace.update(metadata={"prompt_version": prompt_version})

        if step_name == "receive":
            prompt = inputs.get("prompt") or ""
            trace.update(input=prompt)

        elif step_name == "route":
            routing_dec = outputs.get("routing_decision")
            if routing_dec:
                trace.event(
                    name="routing_decision",
                    input={"reason": routing_dec.reason},
                    output={
                        "action": routing_dec.action,
                        "target": routing_dec.target,
                    },
                )

        elif step_name == "policy_gate":
            policy_dec = outputs.get("policy_decision")
            if policy_dec:
                trace.event(
                    name="policy_decision",
                    input={
                        "applied_policy": policy_dec.applied_policy,
                        "limits": policy_dec.limits,
                    },
                    output={
                        "effect": policy_dec.effect,
                        "reason": policy_dec.reason,
                    },
                )
                self._policy_decisions.setdefault(turn_id, []).append(policy_dec)
                # Update metadata on trace with all policy decisions so far
                trace.update(
                    metadata={
                        "policy_decisions": [
                            pd.model_dump() if hasattr(pd, "model_dump") else pd
                            for pd in self._policy_decisions[turn_id]
                        ]
                    }
                )

        elif step_name == "respond":
            response = outputs.get("response")
            if response:
                trace.update(output=response.text)

                # Handle alternate-model tag
                if response.is_alternate_model:
                    trace.update(tags=["alternate-model"])

                # Build usage details and cost details
                usage_details = {
                    "prompt_cache_hit_tokens": response.cache_hit_tokens,
                    "prompt_cache_miss_tokens": response.cache_miss_tokens,
                }
                cost_details = {
                    "cost_usd": response.cost_usd,
                }

                usage_dict: dict[str, Any] = {}
                hit = response.cache_hit_tokens
                miss = response.cache_miss_tokens
                if hit is not None or miss is not None:
                    input_tokens = (hit or 0) + (miss or 0)
                    usage_dict["input"] = input_tokens
                    if hit is not None and hit > 0:
                        usage_dict.setdefault("input_details", {})["cache_read"] = hit

                trace.generation(
                    name="llm_generation",
                    model=response.model_profile_id,
                    input=inputs.get("prompt") or "",
                    output=response.text,
                    usage=usage_dict,
                    metadata={
                        "usage_details": usage_details,
                        "cost_details": cost_details,
                    },
                )

        elif step_name == "compaction":
            trace.span(
                name="compaction",
                input={"usage": inputs.get("usage")},
                output={"compacted": outputs.get("compacted")},
            )

        elif step_name == "execute_graph":
            trace.span(
                name="execute_graph",
                input={},
                output={"status": outputs.get("status")},
            )

    def trace_turn(self, turn_trace: TurnTrace) -> None:
        """Trace an entire turn at once."""
        masked_user_id = mask_user_identity(turn_trace.user_id) if turn_trace.user_id else ""

        trace = self.client.trace(
            id=turn_trace.turn_id,
            name="default_chat_turn",
            user_id=masked_user_id,
            session_id=turn_trace.session_id,
            input=turn_trace.prompt,
        )

        metadata: dict[str, Any] = {}
        tags: list[str] = []

        if turn_trace.prompt_version:
            metadata["prompt_version"] = turn_trace.prompt_version

        if turn_trace.scan_result:
            metadata.update(turn_trace.scan_result)

        # Add routing decision if present
        if turn_trace.routing_decision:
            trace.event(
                name="routing_decision",
                input={"reason": turn_trace.routing_decision.reason},
                output={
                    "action": turn_trace.routing_decision.action,
                    "target": turn_trace.routing_decision.target,
                },
            )

        # Add policy decisions if present
        if turn_trace.policy_decisions:
            pds_dump = []
            for pd in turn_trace.policy_decisions:
                trace.event(
                    name="policy_decision",
                    input={
                        "applied_policy": pd.applied_policy,
                        "limits": pd.limits,
                    },
                    output={
                        "effect": pd.effect,
                        "reason": pd.reason,
                    },
                )
                pds_dump.append(pd.model_dump() if hasattr(pd, "model_dump") else pd)
            metadata["policy_decisions"] = pds_dump

        # Add response if present
        if turn_trace.response:
            resp = turn_trace.response
            trace.update(output=resp.text)

            if resp.is_alternate_model:
                tags.append("alternate-model")

            usage_details = {
                "prompt_cache_hit_tokens": resp.cache_hit_tokens,
                "prompt_cache_miss_tokens": resp.cache_miss_tokens,
            }
            cost_details = {
                "cost_usd": resp.cost_usd,
            }
            metadata["usage_details"] = usage_details
            metadata["cost_details"] = cost_details

            usage_dict: dict[str, Any] = {}
            hit = resp.cache_hit_tokens
            miss = resp.cache_miss_tokens
            if hit is not None or miss is not None:
                input_tokens = (hit or 0) + (miss or 0)
                usage_dict["input"] = input_tokens
                if hit is not None and hit > 0:
                    usage_dict.setdefault("input_details", {})["cache_read"] = hit

            trace.generation(
                name="llm_generation",
                model=resp.model_profile_id,
                input=turn_trace.prompt,
                output=resp.text,
                usage=usage_dict,
                metadata={
                    "usage_details": usage_details,
                    "cost_details": cost_details,
                },
            )

        # Finally update the trace with tags and metadata
        trace.update(tags=tags, metadata=metadata)
