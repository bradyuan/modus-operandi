"""Rule weights from evidence (see docs/DESIGN.md §4.1)."""

from __future__ import annotations

from typing import Any

ALWAYS = 0.8
PREFER = 0.5


def weight(hits: int, misses: int) -> float:
    """Beta(1,1) posterior mean: 1/1 -> 0.67, 12/13 -> 0.87."""
    return (hits + 1) / (hits + misses + 2)


def rule_weight(rule: dict[str, Any]) -> float:
    return weight(int(rule.get("hits", 0)), int(rule.get("misses", 0)))


def strength(w: float) -> str | None:
    if w >= ALWAYS:
        return "always"
    if w >= PREFER:
        return "prefer"
    return None
