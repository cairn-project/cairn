"""cairn.vetting — the human-in-the-loop TWO-GATE vetting queue.

The "human-verified" frame (REQUIREMENTS Frame 5) made concrete + STRUCTURAL: two
DISTINCT review gates, each FAIL-CLOSED — nothing advances past a gate without a
recorded human verdict. The guarantee is enforced by the ABSENCE of an
advance-path, not by policy.

  * Cause-vetting gate (``CauseVetQueue``) — a human cause-vetter reviews a
    REQUESTED cause before it can become approved/listed. ``apply_cause_verdict`` is
    the ONLY path from the queue into the EXISTING ``CauseRegistry.decide_cause``
    (``cause/registry.py``); it refuses unless a human verdict was recorded, so no
    cause becomes publicly listable without a recorded human cause-vetter verdict.
  * Finding-vetting gate (``FindingVetQueue``) — a human finding-vetter reviews a
    flagged, mission-neutral ``Finding`` (a ``packet_hash`` reference + a generic
    automated verdict) before it may be marked ROUTABLE. ``is_routable`` is True
    ONLY after a recorded human ROUTABLE verdict; there is no setter that marks a
    finding routable without a verdict.

Every queue event + verdict is appended to the SAME append-only transparency log
(new ``KIND_*`` following the existing pattern), covered by the unchanged
``verify_log``. Items / findings / verdicts are persisted over ``ledger.blobs``;
timestamps come from the ledger's injected clock. Composes on the cause registry +
capture packet store + ledger; forks nothing.

DEFERRED (later, separately-security-reviewed waves): onward routing to real
external recipients (network-touching; this gate only produces the ROUTABLE state),
reviewer authn/authz + UI (a reviewer is just an id + a recorded decision), real
detection logic / domain finding content, multi-reviewer quorum/escalation on the
human gate, and a ``cairn vet`` CLI (library-only this wave).
"""

from __future__ import annotations

from .cause_queue import (
    CAUSE_DECISION_APPROVE,
    CAUSE_DECISION_REJECT,
    CauseVetQueue,
    PendingCauseReview,
)
from .finding import AutomatedVerdict, Finding, FindingState
from .finding_queue import (
    FINDING_DECISION_REJECT,
    FINDING_DECISION_ROUTABLE,
    FindingVetQueue,
    PendingFindingReview,
)
from .review import ReviewStatus, ReviewVerdict, VettingError

__all__ = [
    # shared review primitives
    "ReviewStatus",
    "ReviewVerdict",
    "VettingError",
    # cause-vetting gate
    "CauseVetQueue",
    "PendingCauseReview",
    "CAUSE_DECISION_APPROVE",
    "CAUSE_DECISION_REJECT",
    # finding model
    "Finding",
    "AutomatedVerdict",
    "FindingState",
    # finding-vetting gate
    "FindingVetQueue",
    "PendingFindingReview",
    "FINDING_DECISION_ROUTABLE",
    "FINDING_DECISION_REJECT",
]
