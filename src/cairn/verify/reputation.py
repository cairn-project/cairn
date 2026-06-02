"""Reputation hook — earned reliability, never self-asserted.

A minimal per-node and per-``model_family`` reliability accumulator. Reputation
is EARNED via two signals:
  * agreement-with-consensus (a node in the winning quorum cluster gains; a node
    in a losing/minority cluster loses), and
  * honeypot outcomes (L4 — a honeypot pass gains, a honeypot FAIL is penalized
    hardest, because failing a known-answer unit is the strongest reliability
    signal available and the one a colluder cannot fake).

A new identity has no entry and therefore the neutral prior — the Sybil
*reset-to-zero-on-new-identity* and persistence belong to the ledger layer; this
module sets the prior + the in-memory accumulation. Scores are bounded to [0, 1].

Subjects are namespaced strings: a bare node id (``adapter_name`` this release) or
``family:<model_family>`` for the per-family aggregate. The verify aggregator
emits one delta per node AND one per family so both views accumulate.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

EVENT_AGREE = "AGREE"
EVENT_DISAGREE = "DISAGREE"
EVENT_HONEYPOT_PASS = "HONEYPOT_PASS"
EVENT_HONEYPOT_FAIL = "HONEYPOT_FAIL"

NEUTRAL_PRIOR = 0.5

# Per-event weights. Honeypot-fail (L4) is the harshest because a missed
# known-answer is the strongest negative reliability signal; a single peer
# disagreement (L1) is softer. Honeypot-pass rewards more than ordinary agree.
_EVENT_WEIGHTS = {
    EVENT_AGREE: +0.05,
    EVENT_DISAGREE: -0.10,
    EVENT_HONEYPOT_PASS: +0.10,
    EVENT_HONEYPOT_FAIL: -0.40,
}


@dataclass(frozen=True)
class ReputationDelta:
    """A single reputation-affecting event for one subject.

    ``subject`` is a node id or ``family:<x>``. ``event`` is one of the EVENT_*
    constants. ``weight`` is the score delta (defaults to the per-event weight;
    an explicit weight overrides, e.g. for confidence-scaled updates later).
    """

    subject: str
    event: str
    weight: float = 0.0

    def effective_weight(self) -> float:
        if self.weight:
            return self.weight
        return _EVENT_WEIGHTS.get(self.event, 0.0)


def family_subject(model_family: str) -> str:
    """Namespace a model family as a reputation subject."""
    return f"family:{model_family}"


class Reputation(ABC):
    """Earned-reputation accumulator interface.

    ``score`` returns a subject's current reliability in [0, 1] (neutral prior
    for an unknown subject). ``apply`` folds in one delta.
    """

    @abstractmethod
    def score(self, subject: str) -> float:
        raise NotImplementedError

    @abstractmethod
    def apply(self, delta: ReputationDelta) -> float:
        """Apply one delta; return the subject's new score."""
        raise NotImplementedError

    def apply_all(self, deltas: list[ReputationDelta]) -> None:
        for d in deltas:
            self.apply(d)


class InMemoryReputation(Reputation):
    """In-memory bounded reputation accumulator (persistence = ledger layer)."""

    def __init__(self, prior: float = NEUTRAL_PRIOR) -> None:
        self._prior = prior
        self._scores: dict[str, float] = {}

    def score(self, subject: str) -> float:
        return self._scores.get(subject, self._prior)

    def apply(self, delta: ReputationDelta) -> float:
        current = self.score(delta.subject)
        updated = current + delta.effective_weight()
        # Bound to [0, 1].
        updated = max(0.0, min(1.0, updated))
        self._scores[delta.subject] = updated
        return updated

    def known_subjects(self) -> list[str]:
        return sorted(self._scores)
