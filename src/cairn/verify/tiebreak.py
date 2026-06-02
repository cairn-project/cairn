"""Disagreement / tiebreak policy.

Gensyn-style "tiebreak the disputed unit only": when a unit fails to reach a
valid quorum because results SPLIT (``DISPUTED``) or there were simply too few
(``NO_QUORUM`` / ``INSUFFICIENT_DIVERSITY``), the cheapest correct response is to
escalate ONE more node for *that unit only* rather than re-running the campaign.

This module emits a ``TiebreakDecision`` — a returned policy decision, NOT a live
re-dispatch. Transport (actually pulling another node) is the ledger/transport
layer; here we only DECIDE whether escalation is warranted and by how many nodes,
bounded by the unit's ``target_nresults`` headroom (don't escalate past the
budget the policy set).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..types import RedundancyPolicy
from .quorum import (
    STATUS_ACCEPTED,
    STATUS_DISPUTED,
    STATUS_INSUFFICIENT_DIVERSITY,
    STATUS_NO_QUORUM,
    QuorumResult,
)


@dataclass(frozen=True)
class TiebreakDecision:
    """Whether (and how much) to escalate a non-accepted unit.

    ``escalate`` — escalate one (or more) additional node(s) for this unit only.
    ``extra_nodes`` — how many to escalate (1 = the Gensyn single-tiebreak).
    ``reason`` — human-readable justification. ``unit_task_id`` — the unit.
    A returned POLICY, never a live re-dispatch (transport = ledger layer).
    """

    escalate: bool
    extra_nodes: int
    reason: str
    unit_task_id: str = ""


def decide_tiebreak(
    quorum: QuorumResult,
    policy: RedundancyPolicy,
    unit_task_id: str = "",
) -> TiebreakDecision:
    """Decide whether to escalate one more node for a non-accepted unit.

    Escalate (by 1) when the unit is DISPUTED / NO_QUORUM / INSUFFICIENT_DIVERSITY
    AND there is headroom under ``target_nresults`` (i.e. fewer results were
    collected than the policy budgeted). No escalation when ACCEPTED, or when the
    unit already consumed its ``target_nresults`` budget (escalating past budget
    is the policy's call to widen, not an automatic loop).
    """
    if quorum.status == STATUS_ACCEPTED:
        return TiebreakDecision(
            escalate=False,
            extra_nodes=0,
            reason="quorum reached; no tiebreak needed",
            unit_task_id=unit_task_id,
        )

    headroom = policy.target_nresults - quorum.nresults
    if headroom <= 0:
        return TiebreakDecision(
            escalate=False,
            extra_nodes=0,
            reason=(
                f"unit unresolved ({quorum.status}) but target_nresults "
                f"{policy.target_nresults} already consumed "
                f"({quorum.nresults} results); escalating past budget is an "
                "owner/policy decision, not automatic"
            ),
            unit_task_id=unit_task_id,
        )

    if quorum.status in (
        STATUS_DISPUTED,
        STATUS_NO_QUORUM,
        STATUS_INSUFFICIENT_DIVERSITY,
    ):
        return TiebreakDecision(
            escalate=True,
            extra_nodes=1,
            reason=(
                f"{quorum.status}: escalate 1 more node for this unit only "
                f"(headroom {headroom} under target_nresults "
                f"{policy.target_nresults})"
            ),
            unit_task_id=unit_task_id,
        )

    return TiebreakDecision(
        escalate=False,
        extra_nodes=0,
        reason=f"no tiebreak rule for status {quorum.status}",
        unit_task_id=unit_task_id,
    )
