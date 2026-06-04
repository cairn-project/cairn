"""Honeypots / gold-standard seeded units.

L4 is *the single most important mechanism for the safety-mission insider
threat*. A honeypot is a work unit whose correct
answer is known in advance. Each node's result is scored against that known
answer; a node that fails a known-answer unit is flagged and down-weighted
**regardless of peer agreement**. This is precisely the collusion that L1
quorum + L2 agreement miss: a colluding majority can make a wrong answer *agree*,
but it cannot make a wrong answer match an independently-seeded gold standard.

Scoring composes the same ``AgreementFunction`` used for quorum: a node's result
"passes" the honeypot iff it agrees (same cluster key) with the expected output.
The per-node scores feed the reputation accumulator (``reputation.py``, L3).

This release builds the honeypot SCORING + the reputation-feed seam. WHICH units
are honeypots and how densely they are seeded is the trusted core's
responsibility — not built here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..execute.result import CandidateResult
from .agreement import AgreementFunction, ObjectiveAgreement


@dataclass(frozen=True)
class HoneypotScore:
    """One node's score against a honeypot's known answer."""

    node_id: str
    model_family: str
    passed: bool
    detail: str = ""


@dataclass
class Honeypot:
    """A seeded unit carrying a known-expected answer.

    ``expected_output`` is the gold-standard result output. ``agreement`` is the
    function used to decide whether a node's output matches it — defaults to a
    normalized ``ObjectiveAgreement`` (the deterministic path). For subjective
    gold standards a ``SubjectiveAgreement(MockJudge())`` (or real judge) is
    passed in.
    """

    expected_output: dict[str, Any]
    agreement: AgreementFunction = field(default_factory=ObjectiveAgreement)

    def _expected_key(self) -> str:
        # Score against a synthetic gold CandidateResult so the same
        # agreement-key logic applies to both expected and produced outputs.
        gold = CandidateResult(
            task_id="__honeypot_gold__",
            output=self.expected_output,
            adapter_name="__gold__",
            model_family="__gold__",
            adapter_version="0",
            produced_at="",
        )
        return self.agreement.agreement_key(gold)

    def score(self, results: list[CandidateResult]) -> list[HoneypotScore]:
        """Score each node's result against the known answer.

        ``node_id`` is taken from the candidate's ``adapter_name`` (the per-node
        identity available this release; a real node identity arrives with the
        ledger). Pass iff the result's agreement key equals the expected key —
        i.e. the node's answer semantically matches the gold standard.
        """
        expected = self._expected_key()
        scores: list[HoneypotScore] = []
        for r in results:
            actual = self.agreement.agreement_key(r)
            passed = actual == expected
            scores.append(
                HoneypotScore(
                    node_id=r.adapter_name,
                    model_family=r.model_family,
                    passed=passed,
                    detail=(
                        "matches gold standard"
                        if passed
                        else "diverges from gold standard (flagged regardless of peer agreement)"
                    ),
                )
            )
        return scores
