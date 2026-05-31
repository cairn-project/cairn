"""Shared review primitives for the two-gate vetting queue (BUILD-PLAN §2).

The "human-verified" frame (REQUIREMENTS Frame 5) made structural: a reviewer is
just an id + a recorded decision (no auth backend, no UI — those are deferred).
Both gates (cause-vetting + finding-vetting) share:

  * ``ReviewStatus`` — the queue-item lifecycle (AWAITING_REVIEW → UNDER_REVIEW →
    VERDICT_RECORDED). The advanced state of the reviewed thing is NEVER set
    without a recorded verdict; this enum tracks WHERE in review an item is.
  * ``ReviewVerdict`` — the recorded human sign-off: reviewer id, decision, reason,
    and a timestamp from the ledger's injected clock. Auditable + reconstructable
    from the transparency log.
  * ``require_reason_on_reject`` — the no-silent-rejection rule (mirrors
    ``CauseRegistry.decide_cause``): a rejection REQUIRES a non-empty reason.

These primitives are mission-neutral and carry no domain content.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class VettingError(Exception):
    """Raised on an invalid vetting-queue operation (unknown item, missing verdict,
    silent rejection, double decision)."""


class ReviewStatus(str, Enum):
    """Lifecycle of a queue item awaiting human review.

    The item is enqueued AWAITING_REVIEW, moves to UNDER_REVIEW once a reviewer is
    assigned, and reaches VERDICT_RECORDED once a human verdict is recorded. The
    *advanced* state of the reviewed thing (a listable cause / a routable finding)
    is derived from the recorded verdict, never from this status alone.
    """

    AWAITING_REVIEW = "awaiting_review"
    UNDER_REVIEW = "under_review"
    VERDICT_RECORDED = "verdict_recorded"


@dataclass(frozen=True)
class ReviewVerdict:
    """One recorded human review verdict — the auditable sign-off.

    ``decision`` is the gate-specific decision string (e.g. "approve"/"reject" for
    the cause gate, "routable"/"reject" for the finding gate). ``reason`` is the
    human-supplied reason (REQUIRED non-empty on a reject — no silent rejection).
    ``recorded_at`` comes from the ledger's injected clock.
    """

    reviewer_id: str
    decision: str
    reason: str
    recorded_at: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "reviewer_id": self.reviewer_id,
            "decision": self.decision,
            "reason": self.reason,
            "recorded_at": self.recorded_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ReviewVerdict":
        return cls(
            reviewer_id=d["reviewer_id"],
            decision=d["decision"],
            reason=d["reason"],
            recorded_at=d["recorded_at"],
        )


def require_reason_on_reject(is_reject: bool, reason: str) -> str:
    """Enforce the no-silent-rejection rule and return the stripped reason.

    A rejection REQUIRES a non-empty reason (mirrors ``CauseRegistry.decide_cause``).
    An approval/advance also carries a reason for the audit trail, but the
    non-empty rule is load-bearing specifically for rejections.
    """
    cleaned = (reason or "").strip()
    if is_reject and not cleaned:
        raise VettingError(
            "a rejection requires a non-empty reason (no silent rejection)"
        )
    if not cleaned:
        raise VettingError("a review verdict requires a non-empty reason")
    return cleaned
