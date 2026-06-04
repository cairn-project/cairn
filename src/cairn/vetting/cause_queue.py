"""Cause-vetting gate — the human review queue feeding the existing cause decision.

The first of the two fail-closed gates (Gate 1). A human
cause-vetter reviews a REQUESTED cause before it can become approved/listed. This
composes on the EXISTING cause request→decision path (``cause/registry.py``); it
does NOT fork the cause decision. It adds:

  * the QUEUE — pending cause-requests awaiting human review (``enqueue`` /
    ``list_pending``);
  * reviewer assignment (``assign``);
  * a recorded human verdict (``record_verdict`` — approve/reject + REQUIRED reason);
  * the fail-closed bridge (``apply_cause_verdict``) — the ONLY path from the queue
    into the existing ``CauseRegistry.decide_cause``. It refuses unless a human
    verdict has been recorded, so no cause becomes publicly listable without a
    recorded human cause-vetter verdict.

Every queue event + verdict is appended to the SAME append-only transparency log
(``CAUSE_VET_ENQUEUED`` / ``CAUSE_VET_ASSIGNED`` / ``CAUSE_VET_VERDICT``), covered
by the unchanged ``verify_log``. Items + verdicts are persisted over
``ledger.blobs``; timestamps come from the ledger's injected clock. Forks nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..cause.gate import GateCheckResult
from ..cause.model import Cause, CauseStatus
from ..cause.registry import CauseRegistry
from ..ledger.ledger import Ledger
from ..ledger.translog import (
    KIND_CAUSE_VET_ASSIGNED,
    KIND_CAUSE_VET_ENQUEUED,
    KIND_CAUSE_VET_VERDICT,
)
from .review import ReviewStatus, ReviewVerdict, VettingError, require_reason_on_reject

# Gate-specific decision strings for the cause gate.
CAUSE_DECISION_APPROVE = "approve"
CAUSE_DECISION_REJECT = "reject"


@dataclass(frozen=True)
class PendingCauseReview:
    """One cause awaiting (or having completed) human review.

    ``status`` tracks the review lifecycle; ``verdict`` is the recorded human
    sign-off (``None`` until one is recorded). The reviewed cause becomes listable
    only via ``apply_cause_verdict`` AFTER a recorded approve verdict — never from
    this item's status alone.
    """

    cause_id: str
    status: ReviewStatus
    enqueued_at: float
    assigned_to: str | None = None
    verdict: ReviewVerdict | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "cause_id": self.cause_id,
            "status": self.status.value,
            "enqueued_at": self.enqueued_at,
            "assigned_to": self.assigned_to,
            "verdict": self.verdict.to_dict() if self.verdict else None,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PendingCauseReview:
        v = d.get("verdict")
        return cls(
            cause_id=d["cause_id"],
            status=ReviewStatus(d["status"]),
            enqueued_at=d["enqueued_at"],
            assigned_to=d.get("assigned_to"),
            verdict=ReviewVerdict.from_dict(v) if v else None,
        )


class CauseVetQueue:
    """Persist + queue + assign + record the human cause-vetting gate over the ledger."""

    def __init__(self, ledger: Ledger) -> None:
        self._ledger = ledger
        self._clock = ledger._clock  # noqa: SLF001
        self._index_dir = Path(ledger._root) / "cause_vet_queue"  # noqa: SLF001
        self._index_dir.mkdir(parents=True, exist_ok=True)

    # --- enqueue --------------------------------------------------

    def enqueue(self, cause: Cause) -> PendingCauseReview:
        """Enqueue a REQUESTED cause for human review; log ``CAUSE_VET_ENQUEUED``.

        Refuses a cause that is not in the REQUESTED state (an already-decided
        cause has left the request→decision intake; re-queuing it is invalid).
        """
        if cause.status != CauseStatus.REQUESTED:
            raise VettingError(
                f"only a REQUESTED cause can enter the cause-vet queue; "
                f"cause {cause.cause_id} is {cause.status.value}"
            )
        existing = self._load(cause.cause_id)
        if existing is not None:
            raise VettingError(f"cause {cause.cause_id} is already in the cause-vet queue")
        item = PendingCauseReview(
            cause_id=cause.cause_id,
            status=ReviewStatus.AWAITING_REVIEW,
            enqueued_at=self._clock.now(),
        )
        self._persist(item)
        self._ledger.translog.append(
            KIND_CAUSE_VET_ENQUEUED,
            {"cause_id": cause.cause_id, "name": cause.name},
        )
        return item

    # --- assign ---------------------------------------------------

    def assign(self, cause_id: str, reviewer_id: str) -> PendingCauseReview:
        """Assign a pending item to a reviewer (AWAITING_REVIEW → UNDER_REVIEW)."""
        item = self._require(cause_id)
        if item.status == ReviewStatus.VERDICT_RECORDED:
            raise VettingError(f"cause {cause_id} already has a recorded verdict; cannot reassign")
        updated = PendingCauseReview(
            cause_id=item.cause_id,
            status=ReviewStatus.UNDER_REVIEW,
            enqueued_at=item.enqueued_at,
            assigned_to=reviewer_id,
            verdict=item.verdict,
        )
        self._persist(updated)
        self._ledger.translog.append(
            KIND_CAUSE_VET_ASSIGNED,
            {"cause_id": cause_id, "reviewer_id": reviewer_id},
        )
        return updated

    # --- record human verdict -------------------------------------

    def record_verdict(
        self, cause_id: str, approve: bool, reason: str, reviewer_id: str
    ) -> PendingCauseReview:
        """Record the human cause-vetter verdict; log ``CAUSE_VET_VERDICT``.

        A REJECT with an empty/whitespace reason is refused (no silent rejection).
        A verdict can be recorded only once per cause.
        """
        item = self._require(cause_id)
        if item.verdict is not None:
            raise VettingError(f"cause {cause_id} already has a recorded human verdict")
        cleaned = require_reason_on_reject(is_reject=not approve, reason=reason)
        verdict = ReviewVerdict(
            reviewer_id=reviewer_id,
            decision=CAUSE_DECISION_APPROVE if approve else CAUSE_DECISION_REJECT,
            reason=cleaned,
            recorded_at=self._clock.now(),
        )
        updated = PendingCauseReview(
            cause_id=item.cause_id,
            status=ReviewStatus.VERDICT_RECORDED,
            enqueued_at=item.enqueued_at,
            assigned_to=item.assigned_to,
            verdict=verdict,
        )
        self._persist(updated)
        self._ledger.translog.append(
            KIND_CAUSE_VET_VERDICT,
            {
                "cause_id": cause_id,
                "reviewer_id": reviewer_id,
                "decision": verdict.decision,
                "reason": verdict.reason,
            },
        )
        return updated

    # --- the fail-closed bridge into the existing cause decision --

    def apply_cause_verdict(
        self,
        cause_id: str,
        registry: CauseRegistry,
        gate_result: GateCheckResult,
    ) -> Cause:
        """Feed the recorded human verdict into the EXISTING cause decision.

        This is the ONLY path from the cause-vet queue into
        ``CauseRegistry.decide_cause`` (``cause/registry.py``). It refuses unless a
        human verdict has been recorded for this cause — so an un-reviewed cause can
        never be approved and therefore never become publicly listable (fail-closed
        by the ABSENCE of any other advance-path, not by policy).

        The human verdict supplies the approve/reject decision, the reason, and the
        reviewer id (the decider of record). The existing decision still enforces
        its own rules (non-empty reason + complete five-frame gate-check), which we
        do not re-implement here.
        """
        item = self._require(cause_id)
        if item.verdict is None:
            raise VettingError(
                f"cause {cause_id} has no recorded human cause-vetter verdict; "
                "it cannot be approved/listed (fail-closed cause-vetting gate)"
            )
        verdict = item.verdict
        return registry.decide_cause(
            cause_id,
            approve=(verdict.decision == CAUSE_DECISION_APPROVE),
            reason=verdict.reason,
            decider=verdict.reviewer_id,
            gate_result=gate_result,
        )

    # --- queries -------------------------------------------------------------

    def list_pending(self) -> list[PendingCauseReview]:
        """Items still awaiting a human verdict (AWAITING_REVIEW / UNDER_REVIEW)."""
        return [it for it in self._all() if it.status != ReviewStatus.VERDICT_RECORDED]

    def get(self, cause_id: str) -> PendingCauseReview | None:
        return self._load(cause_id)

    def get_verdict(self, cause_id: str) -> ReviewVerdict | None:
        item = self._load(cause_id)
        return item.verdict if item else None

    # --- persistence helpers -------------------------------------------------

    def _require(self, cause_id: str) -> PendingCauseReview:
        item = self._load(cause_id)
        if item is None:
            raise VettingError(f"cause {cause_id} is not in the cause-vet queue")
        return item

    def _all(self) -> list[PendingCauseReview]:
        return [self._read(p) for p in sorted(self._index_dir.iterdir()) if p.is_file()]

    def _load(self, cause_id: str) -> PendingCauseReview | None:
        ref = self._index_dir / cause_id
        if not ref.exists():
            return None
        return self._read(ref)

    def _read(self, ref: Path) -> PendingCauseReview:
        blob_key = ref.read_text().strip()
        return PendingCauseReview.from_dict(self._ledger.blobs.get_json(blob_key))

    def _persist(self, item: PendingCauseReview) -> None:
        blob_key = self._ledger.blobs.put_json(item.to_dict())
        (self._index_dir / item.cause_id).write_text(blob_key)
