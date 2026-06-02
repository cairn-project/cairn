"""Quorum + redundancy aggregation with the model-diversity gate.

Takes the agreement clusters (``agreement.py``) over N candidate results for ONE
work unit and decides a quorum status against the unit's ``RedundancyPolicy``:

  * ``ACCEPTED`` — a cluster reaches ``min_quorum`` AND satisfies the model-
    diversity requirement (≥ ``required_diversity`` distinct model families).
  * ``INSUFFICIENT_DIVERSITY`` — a cluster reaches ``min_quorum`` by SIZE but is
    formed by too few distinct model families (the anti-collusion rejection — a
    single model family is NOT a valid quorum; inverts BOINC
    homogeneity on purpose).
  * ``NO_QUORUM`` — no cluster reaches ``min_quorum`` (too few agreeing results).
  * ``DISPUTED`` — results split into competing clusters and none reaches quorum,
    BUT there are multiple non-trivial clusters (genuine disagreement, as opposed
    to simply too few results) — the signal the tiebreak policy escalates on.

Model-diversity requirement: read from ``RedundancyPolicy.model_diversity``.
The anti-collusion floor mandates ≥2 distinct families. The field defaults to 0
(unset); a value <= 1 is treated as "unset" and the safe
default of 2 is applied so the anti-collusion primitive is ON by default. An
explicit ``model_diversity = 1`` (deliberately configured) disables it for a benign cause.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..types import RedundancyPolicy
from .agreement import Cluster

STATUS_ACCEPTED = "ACCEPTED"
STATUS_NO_QUORUM = "NO_QUORUM"
STATUS_DISPUTED = "DISPUTED"
STATUS_INSUFFICIENT_DIVERSITY = "INSUFFICIENT_DIVERSITY"

# Safe default applied when the policy leaves model_diversity unset (<= 1).
DEFAULT_MODEL_DIVERSITY = 2


def required_diversity(policy: RedundancyPolicy) -> int:
    """Resolve the effective model-diversity requirement for a policy.

    A policy value <= 1 means "unset" -> apply the safe anti-collusion default of
    2 distinct families. An explicit value >= 2 is
    honored as-is. An explicit ``1`` (deliberately configured) disables diversity.
    """
    declared = policy.model_diversity
    if declared <= 0:
        return DEFAULT_MODEL_DIVERSITY
    return declared


@dataclass(frozen=True)
class QuorumResult:
    """Outcome of quorum + diversity aggregation over one unit's results."""

    status: str
    nresults: int
    clusters: list[Cluster] = field(default_factory=list)
    winning_cluster: Optional[Cluster] = None
    required_quorum: int = 0
    required_diversity: int = 0
    detail: str = ""

    @property
    def accepted(self) -> bool:
        return self.status == STATUS_ACCEPTED


def decide_quorum(
    clusters: list[Cluster], policy: RedundancyPolicy
) -> QuorumResult:
    """Decide a quorum status from agreement clusters + the redundancy policy.

    Acceptance requires BOTH size (``>= min_quorum``) AND diversity
    (``>= required_diversity`` distinct model families) on a single cluster.
    """
    nresults = sum(c.size for c in clusters)
    min_quorum = policy.min_quorum
    need_div = required_diversity(policy)

    # Largest cluster first (ties broken by more model families, then key).
    ranked = sorted(
        clusters, key=lambda c: (c.size, len(c.model_families), c.key), reverse=True
    )

    size_qualified = [c for c in ranked if c.size >= min_quorum]

    for cluster in size_qualified:
        if len(cluster.model_families) >= need_div:
            return QuorumResult(
                status=STATUS_ACCEPTED,
                nresults=nresults,
                clusters=ranked,
                winning_cluster=cluster,
                required_quorum=min_quorum,
                required_diversity=need_div,
                detail=(
                    f"cluster size {cluster.size} >= {min_quorum}, "
                    f"{len(cluster.model_families)} families >= {need_div}"
                ),
            )

    # A cluster met size but not diversity -> the anti-collusion rejection.
    if size_qualified:
        c = size_qualified[0]
        return QuorumResult(
            status=STATUS_INSUFFICIENT_DIVERSITY,
            nresults=nresults,
            clusters=ranked,
            winning_cluster=None,
            required_quorum=min_quorum,
            required_diversity=need_div,
            detail=(
                f"largest qualifying cluster has {len(c.model_families)} model "
                f"family/families ({sorted(c.model_families)}), need {need_div}; "
                "single/low-diversity consensus is not a valid quorum"
            ),
        )

    # No cluster reached min_quorum. DISPUTED if there is genuine split
    # (multiple clusters each with >1 member), else NO_QUORUM (too few results).
    contested = [c for c in ranked if c.size >= 2]
    if len(contested) >= 2:
        status = STATUS_DISPUTED
        detail = (
            f"{len(contested)} competing clusters, none reaching quorum "
            f"{min_quorum} (sizes {[c.size for c in contested]})"
        )
    else:
        status = STATUS_NO_QUORUM
        detail = (
            f"no cluster reached quorum {min_quorum} "
            f"(largest {ranked[0].size if ranked else 0})"
        )

    return QuorumResult(
        status=status,
        nresults=nresults,
        clusters=ranked,
        winning_cluster=None,
        required_quorum=min_quorum,
        required_diversity=need_div,
        detail=detail,
    )
