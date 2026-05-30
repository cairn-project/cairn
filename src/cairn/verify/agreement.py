"""Semantic agreement — clustering N candidate results (PLAN §3.5 L2).

Agreement is NOT bit-equality. Heterogeneous LLM outputs never bit-match
(research 02 A.0/B.0), so the verify layer clusters candidate results by a
canonical AGREEMENT KEY and treats one cluster as "these results agree."

Two concrete agreement functions:
  * ``ObjectiveAgreement`` — deterministic outputs: exact / normalized-string /
    caller-supplied predicate key. The cheap path when the unit's output is
    machine-deterministic.
  * ``SubjectiveAgreement`` — delegates the key to a pluggable ``Judge`` (the
    LLM-as-judge seam; offline ``MockJudge`` this wave).

The output of both is a list of ``Cluster``s, each carrying its members and the
distinct ``model_family`` values present — the input the quorum + model-diversity
gate (PLAN §3.5 L1) consumes.
"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from ..execute.result import CandidateResult
from .judge import Judge

_WS = re.compile(r"\s+")


@dataclass(frozen=True)
class Cluster:
    """A set of candidate results that semantically agree.

    ``key`` is the shared canonical agreement key. ``members`` are the candidate
    results in this cluster. ``model_families`` is the set of distinct
    ``model_family`` values present — the model-diversity gate (L1) reads this.
    """

    key: str
    members: list[CandidateResult] = field(default_factory=list)

    @property
    def model_families(self) -> set[str]:
        return {m.model_family for m in self.members if m.model_family}

    @property
    def size(self) -> int:
        return len(self.members)


class AgreementFunction(ABC):
    """Partition candidate results into semantic-agreement clusters."""

    @abstractmethod
    def agreement_key(self, result: CandidateResult) -> str:
        """Canonical key for one result; same key ⇒ agreement."""
        raise NotImplementedError

    def cluster(self, results: list[CandidateResult]) -> list[Cluster]:
        """Group results by agreement key into clusters (stable order)."""
        buckets: dict[str, list[CandidateResult]] = {}
        order: list[str] = []
        for r in results:
            k = self.agreement_key(r)
            if k not in buckets:
                buckets[k] = []
                order.append(k)
            buckets[k].append(r)
        return [Cluster(key=k, members=buckets[k]) for k in order]


def _normalize_str(s: str) -> str:
    return _WS.sub(" ", s.strip().lower())


class ObjectiveAgreement(AgreementFunction):
    """Deterministic-output agreement (PLAN §3.5 L2 objective path).

    Key derivation, in priority order:
      * ``key_fn`` — caller predicate returning a hashable key (most general).
      * ``field`` — a dotted path into the result output whose value is the key.
      * default — the whole ``output`` dict.

    With ``normalize=True`` (default) string values are lowercased + whitespace-
    collapsed before keying, so trivially-different deterministic outputs still
    match. Set ``normalize=False`` for strict exact equality.
    """

    def __init__(
        self,
        key_fn: Optional[Callable[[CandidateResult], Any]] = None,
        field: Optional[str] = None,
        normalize: bool = True,
    ) -> None:
        self._key_fn = key_fn
        self._field = field
        self._normalize = normalize

    def _resolve_field(self, output: Any, dotted: str) -> Any:
        cur = output
        for part in dotted.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            elif isinstance(cur, list) and part.lstrip("-").isdigit():
                idx = int(part)
                if -len(cur) <= idx < len(cur):
                    cur = cur[idx]
                else:
                    return None
            else:
                return None
        return cur

    def _canonical(self, value: Any) -> Any:
        if not self._normalize:
            return value
        if isinstance(value, str):
            return _normalize_str(value)
        if isinstance(value, dict):
            return {k: self._canonical(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._canonical(v) for v in value]
        return value

    def agreement_key(self, result: CandidateResult) -> str:
        if self._key_fn is not None:
            return json.dumps(self._key_fn(result), sort_keys=True, default=str)
        if self._field is not None:
            value = self._resolve_field(result.output, self._field)
        else:
            value = result.output
        return json.dumps(self._canonical(value), sort_keys=True, ensure_ascii=False)


class SubjectiveAgreement(AgreementFunction):
    """Subjective-output agreement via a pluggable ``Judge`` (PLAN §3.5 L2).

    Delegates the agreement key to the judge. With ``MockJudge`` this is fully
    offline + deterministic; with a real LLM judge it is a network call (later
    increment). The clustering logic is identical — only the key source differs.
    """

    def __init__(self, judge: Judge) -> None:
        self._judge = judge

    def agreement_key(self, result: CandidateResult) -> str:
        return self._judge.agreement_key(result)
