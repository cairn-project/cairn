"""verify_unit — the verify-layer entry point.

Wires the defense-in-depth layers over N ``CandidateResult``s for ONE work unit:

  L2  semantic agreement  -> cluster the results (``AgreementFunction``)
  L1  quorum + diversity  -> decide ACCEPTED / NO_QUORUM / DISPUTED /
                             INSUFFICIENT_DIVERSITY against the RedundancyPolicy
  L4  honeypot (optional) -> if the unit is a gold-standard seed, score each node
                             against the known answer (catches collusion L1/L2 miss)
  L3  reputation deltas   -> emit per-node + per-family deltas from consensus
                             membership + honeypot outcomes (earned, not asserted)
      tiebreak policy     -> emit an escalate-one-more-node decision for a
                             non-accepted unit (returned, not dispatched)

Returns a single ``VerifyVerdict``. This is the layer's outcome-altitude entry
point: invoke it with freshly-produced candidates and no pre-arranged verdict
state to get the full trust decision. Reputation deltas are RETURNED (and
optionally applied to a passed-in ``Reputation``) — persistence is the ledger layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ..execute.result import CandidateResult
from ..types import RedundancyPolicy
from .agreement import AgreementFunction, Cluster, ObjectiveAgreement
from .honeypot import Honeypot, HoneypotScore
from .quorum import QuorumResult, decide_quorum
from .reputation import (
    EVENT_AGREE,
    EVENT_DISAGREE,
    EVENT_HONEYPOT_FAIL,
    EVENT_HONEYPOT_PASS,
    Reputation,
    ReputationDelta,
    family_subject,
)
from .tiebreak import TiebreakDecision, decide_tiebreak


@dataclass(frozen=True)
class VerifyVerdict:
    """The trust verdict for one work unit over N candidate results."""

    status: str
    quorum: QuorumResult
    tiebreak: TiebreakDecision
    honeypot_scores: list[HoneypotScore] = field(default_factory=list)
    reputation_updates: list[ReputationDelta] = field(default_factory=list)
    accepted_output: Optional[dict[str, Any]] = None

    @property
    def accepted(self) -> bool:
        return self.quorum.accepted


def _consensus_deltas(quorum: QuorumResult) -> list[ReputationDelta]:
    """AGREE for nodes in the winning cluster, DISAGREE for the rest.

    Only emitted when a unit is ACCEPTED — a node only earns/loses consensus
    reputation when there IS a consensus to be in or out of. For non-accepted
    units the honeypot (if any) still drives reputation, but ambiguous
    non-consensus is not charged as a disagreement (it may just be too few
    results).
    """
    deltas: list[ReputationDelta] = []
    if not quorum.accepted or quorum.winning_cluster is None:
        return deltas
    winners = {id(m) for m in quorum.winning_cluster.members}
    for cluster in quorum.clusters:
        in_consensus = any(id(m) in winners for m in cluster.members)
        event = EVENT_AGREE if in_consensus else EVENT_DISAGREE
        for m in cluster.members:
            deltas.append(ReputationDelta(subject=m.adapter_name, event=event))
            deltas.append(
                ReputationDelta(subject=family_subject(m.model_family), event=event)
            )
    return deltas


def _honeypot_deltas(scores: list[HoneypotScore]) -> list[ReputationDelta]:
    deltas: list[ReputationDelta] = []
    for s in scores:
        event = EVENT_HONEYPOT_PASS if s.passed else EVENT_HONEYPOT_FAIL
        deltas.append(ReputationDelta(subject=s.node_id, event=event))
        deltas.append(
            ReputationDelta(subject=family_subject(s.model_family), event=event)
        )
    return deltas


def verify_unit(
    results: list[CandidateResult],
    policy: RedundancyPolicy,
    *,
    agreement: Optional[AgreementFunction] = None,
    honeypot: Optional[Honeypot] = None,
    reputation: Optional[Reputation] = None,
    unit_task_id: str = "",
) -> VerifyVerdict:
    """Aggregate N candidate results into a trust verdict for one unit.

    Args:
      results: the candidate results collected for ONE work unit (N nodes).
      policy: the unit's ``RedundancyPolicy`` (target_nresults / min_quorum /
        model_diversity).
      agreement: the ``AgreementFunction`` (default normalized
        ``ObjectiveAgreement``); pass ``SubjectiveAgreement(judge)`` for the
        subjective path.
      honeypot: if this unit is a gold-standard seed, the ``Honeypot`` to score
        each node against. Its scoring uses its OWN agreement
        function.
      reputation: if provided, the returned deltas are applied to it (in-memory;
        persistence = ledger layer). Always returned regardless.
      unit_task_id: the unit id, threaded into the tiebreak decision.

    Returns a ``VerifyVerdict``.
    """
    agreement = agreement or ObjectiveAgreement()

    clusters: list[Cluster] = agreement.cluster(results)
    quorum = decide_quorum(clusters, policy)

    honeypot_scores: list[HoneypotScore] = []
    if honeypot is not None:
        honeypot_scores = honeypot.score(results)

    deltas: list[ReputationDelta] = []
    deltas.extend(_consensus_deltas(quorum))
    deltas.extend(_honeypot_deltas(honeypot_scores))

    if reputation is not None:
        reputation.apply_all(deltas)

    tiebreak = decide_tiebreak(quorum, policy, unit_task_id=unit_task_id)

    accepted_output = None
    if quorum.accepted and quorum.winning_cluster is not None:
        # Representative output from the winning cluster (first member).
        accepted_output = quorum.winning_cluster.members[0].output

    return VerifyVerdict(
        status=quorum.status,
        quorum=quorum,
        tiebreak=tiebreak,
        honeypot_scores=honeypot_scores,
        reputation_updates=deltas,
        accepted_output=accepted_output,
    )
