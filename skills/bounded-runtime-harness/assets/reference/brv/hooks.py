from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable

HOOKS = (
    "before_model_output_accepted",
    "before_tool_call",
    "after_tool_call",
    "before_state_commit",
    "after_mutation",
    "before_next_turn",
    "on_budget_exhausted",
    "on_repeated_failure",
)

Decision = str  # ALLOW | DENY | RETRY | HALT


class HookRegistry:
    """Interception points only. Policy lives in the gates."""

    def __init__(self) -> None:
        self._subs: dict[str, list[Callable[..., Any]]] = defaultdict(list)

    def on(self, name: str, fn: Callable[..., Any]) -> None:
        if name not in HOOKS:
            raise ValueError(f"unknown hook {name}")
        self._subs[name].append(fn)

    def emit(self, name: str, **payload: Any) -> list[Any]:
        return [fn(**payload) for fn in self._subs.get(name, [])]
