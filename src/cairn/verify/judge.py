"""Judge seam + deterministic offline MockJudge.

Heterogeneous LLM outputs never bit-match, so semantic
agreement cannot be exact-equality on raw text. A ``Judge`` maps a
``CandidateResult`` to an ``agreement_key`` — two results that the judge regards
as semantically equivalent share a key and therefore cluster together.

The real judge is an LLM-as-judge that makes a network call (cross-model majority
voting raised precision 73.1% -> 95.6%, arXiv 2411.06535). That is a FOLLOW-ON
increment — this release ships ONLY the abstract seam plus a deterministic,
fully-offline ``MockJudge`` so the verify layer is testable with no network.

``MockJudge`` canonicalizes an output to a normal form (lowercase, collapsed
whitespace, dict keys sorted) so semantically-equal-but-not-bit-equal outputs
produce the same key. It is intentionally simple — it is a TEST DOUBLE for the
real judge, not a real semantic model.
"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any, Callable, Optional

from ..execute.result import CandidateResult

_WS = re.compile(r"\s+")


class Judge(ABC):
    """Abstract semantic-agreement judge.

    Implementations return a stable ``agreement_key`` for a candidate result;
    results sharing a key are treated as semantically agreeing. The real
    implementation is an LLM-as-judge (network) — a later increment.
    """

    @abstractmethod
    def agreement_key(self, result: CandidateResult) -> str:
        """Return a canonical agreement key for one candidate result."""
        raise NotImplementedError


def _canonicalize(value: Any) -> Any:
    """Recursively normalize a value: strings lowered + whitespace-collapsed,
    dict keys sorted (handled at serialization), lists preserved in order."""
    if isinstance(value, str):
        return _WS.sub(" ", value.strip().lower())
    if isinstance(value, dict):
        return {k: _canonicalize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_canonicalize(v) for v in value]
    return value


class MockJudge(Judge):
    """Deterministic offline judge — a test double for the real LLM judge.

    Canonical form: recursively lowercase + whitespace-collapse strings, then
    serialize with ``sort_keys=True`` so dict ordering is irrelevant. Two outputs
    that differ only by casing, whitespace, or key order share a key.

    ``normalize_fn`` optionally pre-transforms the output dict before
    canonicalization (e.g. drop a volatile ``timestamp`` field) — the hook a real
    judge's prompt would encode.
    """

    def __init__(self, normalize_fn: Optional[Callable[[dict], dict]] = None) -> None:
        self._normalize_fn = normalize_fn

    def agreement_key(self, result: CandidateResult) -> str:
        output = result.output
        if self._normalize_fn is not None:
            output = self._normalize_fn(output)
        canonical = _canonicalize(output)
        return json.dumps(canonical, sort_keys=True, ensure_ascii=False)
