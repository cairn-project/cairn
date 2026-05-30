"""Shared builders for the wave-3 verify-layer tests.

A tiny factory for ``CandidateResult``s so the verify tests can construct N
results from N nodes with controllable output + model_family without standing up
the whole execute flow.
"""

from __future__ import annotations

from typing import Any, Optional

from cairn.execute.result import CandidateResult
from cairn.types import RedundancyPolicy


def make_result(
    output: dict[str, Any],
    *,
    node: str,
    family: str,
    task_id: str = "unit-1",
) -> CandidateResult:
    return CandidateResult(
        task_id=task_id,
        output=output,
        adapter_name=node,
        model_family=family,
        adapter_version="1",
        produced_at="2026-01-01T00:00:00Z",
    )


def policy(
    target_nresults: int = 3,
    min_quorum: int = 2,
    model_diversity: int = 0,
) -> RedundancyPolicy:
    return RedundancyPolicy(
        target_nresults=target_nresults,
        min_quorum=min_quorum,
        model_diversity=model_diversity,
    )
