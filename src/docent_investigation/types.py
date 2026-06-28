"""Primitive types shared across the investigation toolkit."""

from __future__ import annotations

from enum import Enum


class OracleLabel(str, Enum):
    """Third-party resolution label (a proxy for "solved") of a SWE-bench agent run.

    RESOLVED: the agent's patch made the hidden tests pass.
    UNRESOLVED: a patch was submitted but tests still failed.
    EMPTY_PATCH: the agent produced no patch at all.
    """

    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    EMPTY_PATCH = "empty_patch"

    @property
    def is_resolved(self) -> bool:
        return self is OracleLabel.RESOLVED
