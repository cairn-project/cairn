"""Finding-vetting gate — the human review queue producing the ROUTABLE state.

The second of the two fail-closed gates (Gate 2). A human
finding-vetter reviews a flagged ``Finding`` before it may be marked ROUTABLE
(eligible to be acted on / routed onward). No finding becomes routable without a
recorded human finding-vetter verdict. The actual onward routing to external
recipients is OUT of scope (deferred, network-touching, security-reviewed later
phase); this gate only produces the human-verified ROUTABLE/REJECTED state.

  * ``flag`` — content-address + store a mission-neutral ``Finding`` and enqueue it
    (``FINDING_FLAGGED``); the finding references an existing ``packet_hash``.
  * ``assign`` — assign a pending finding to a reviewer (``FINDING_VET_ASSIGNED``).
  * ``record_verdict`` — record the human verdict (routable/reject + REQUIRED reason;
    ``FINDING_VET_VERDICT``).
  * ``finding_state`` / ``is_routable`` — derive the routing-eligibility state SOLELY
    from the recorded human verdict. Fail-closed: PENDING by default; there is NO
    function that marks a finding routable without a recorded ROUTABLE verdict.

Every event is on the SAME append-only transparency log, covered by the unchanged
``verify_log``. Findings + verdicts are persisted over ``ledger.blobs``; timestamps
come from the ledger's injected clock. Forks nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..ledger.indexed_store import IndexedBlobStore
from ..ledger.ledger import Ledger
from ..ledger.translog import (
    KIND_FINDING_FLAGGED,
    KIND_FINDING_VET_ASSIGNED,
    KIND_FINDING_VET_VERDICT,
)
from .finding import AutomatedVerdict, Finding, FindingState
from .review import ReviewStatus, ReviewVerdict, VettingError, require_reason_on_reject

# Gate-specific decision strings for the finding gate.
FINDING_DECISION_ROUTABLE = "routable"
FINDING_DECISION_REJECT = "reject"


@dataclass(frozen=True)
class PendingFindingReview:
    """A flagged finding awaiting (or having completed) human review.

    ``status`` tracks the review lifecycle; ``verdict`` is the recorded human
    sign-off (``None`` until recorded). The finding's routing-eligibility state is
    derived from ``verdict`` (``finding_state`` / ``is_routable``), never from
    ``status`` alone.
    """

    finding_hash: str
    status: ReviewStatus
    flagged_at: float
    assigned_to: str | None = None
    verdict: ReviewVerdict | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_hash": self.finding_hash,
            "status": self.status.value,
            "flagged_at": self.flagged_at,
            "assigned_to": self.assigned_to,
            "verdict": self.verdict.to_dict() if self.verdict else None,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PendingFindingReview:
        v = d.get("verdict")
        return cls(
            finding_hash=d["finding_hash"],
            status=ReviewStatus(d["status"]),
            flagged_at=d["flagged_at"],
            assigned_to=d.get("assigned_to"),
            verdict=ReviewVerdict.from_dict(v) if v else None,
        )


class FindingVetQueue:
    """Persist + queue + assign + record the human finding-vetting gate."""

    def __init__(self, ledger: Ledger) -> None:
        self._ledger = ledger
        self._clock = ledger.clock
        self._store: IndexedBlobStore[PendingFindingReview] = IndexedBlobStore(
            ledger, "finding_vet_queue", PendingFindingReview.from_dict
        )

    # --- flag/enqueue ---------------------------------------------

    def flag(
        self,
        *,
        packet_hash: str,
        automated_verdict: AutomatedVerdict,
        flagged_by: str,
        cause_id: str | None = None,
    ) -> Finding:
        """Flag a mission-neutral finding into the queue; log ``FINDING_FLAGGED``.

        The finding references an existing ``packet_hash`` (the evidence it was
        derived from). It is content-addressed + stored over ``ledger.blobs``; the
        blob content key equals ``finding_hash`` by construction.
        """
        finding = Finding.create(
            packet_hash=packet_hash,
            automated_verdict=automated_verdict,
            flagged_at=self._clock.now(),
            flagged_by=flagged_by,
            cause_id=cause_id,
        )
        if self._load(finding.finding_hash) is not None:
            raise VettingError(
                f"finding {finding.finding_hash} is already in the finding-vet queue"
            )
        blob_key = self._ledger.blobs.put_json(finding.material_dict())
        assert blob_key == finding.finding_hash  # content-address invariant
        item = PendingFindingReview(
            finding_hash=finding.finding_hash,
            status=ReviewStatus.AWAITING_REVIEW,
            flagged_at=finding.flagged_at,
        )
        self._persist(item)
        self._ledger.translog.append(
            KIND_FINDING_FLAGGED,
            {
                "finding_hash": finding.finding_hash,
                "packet_hash": packet_hash,
                "flag_label": automated_verdict.flag_label,
                "confidence": automated_verdict.confidence,
                "flagged_by": flagged_by,
                "cause_id": cause_id,
            },
        )
        return finding

    # --- assign ---------------------------------------------------

    def assign(self, finding_hash: str, reviewer_id: str) -> PendingFindingReview:
        """Assign a pending finding to a reviewer (AWAITING_REVIEW → UNDER_REVIEW)."""
        item = self._require(finding_hash)
        if item.status == ReviewStatus.VERDICT_RECORDED:
            raise VettingError(
                f"finding {finding_hash} already has a recorded verdict; cannot reassign"
            )
        updated = PendingFindingReview(
            finding_hash=item.finding_hash,
            status=ReviewStatus.UNDER_REVIEW,
            flagged_at=item.flagged_at,
            assigned_to=reviewer_id,
            verdict=item.verdict,
        )
        self._persist(updated)
        self._ledger.translog.append(
            KIND_FINDING_VET_ASSIGNED,
            {"finding_hash": finding_hash, "reviewer_id": reviewer_id},
        )
        return updated

    # --- record human verdict -------------------------------------

    def record_verdict(
        self, finding_hash: str, routable: bool, reason: str, reviewer_id: str
    ) -> PendingFindingReview:
        """Record the human finding-vetter verdict; log ``FINDING_VET_VERDICT``.

        A REJECT with an empty/whitespace reason is refused (no silent rejection).
        A verdict can be recorded only once per finding.
        """
        item = self._require(finding_hash)
        if item.verdict is not None:
            raise VettingError(f"finding {finding_hash} already has a recorded human verdict")
        cleaned = require_reason_on_reject(is_reject=not routable, reason=reason)
        verdict = ReviewVerdict(
            reviewer_id=reviewer_id,
            decision=FINDING_DECISION_ROUTABLE if routable else FINDING_DECISION_REJECT,
            reason=cleaned,
            recorded_at=self._clock.now(),
        )
        updated = PendingFindingReview(
            finding_hash=item.finding_hash,
            status=ReviewStatus.VERDICT_RECORDED,
            flagged_at=item.flagged_at,
            assigned_to=item.assigned_to,
            verdict=verdict,
        )
        self._persist(updated)
        self._ledger.translog.append(
            KIND_FINDING_VET_VERDICT,
            {
                "finding_hash": finding_hash,
                "reviewer_id": reviewer_id,
                "decision": verdict.decision,
                "reason": verdict.reason,
            },
        )
        return updated

    # --- the fail-closed routing-eligibility state ----------------

    def finding_state(self, finding_hash: str) -> FindingState:
        """Derive the human-verified routing-eligibility state from the verdict.

        Fail-closed: ROUTABLE iff a recorded human ROUTABLE verdict exists; REJECTED
        iff a recorded reject verdict exists; otherwise PENDING. There is no producer
        of ROUTABLE other than a recorded human verdict.
        """
        item = self._require(finding_hash)
        if item.verdict is None:
            return FindingState.PENDING
        if item.verdict.decision == FINDING_DECISION_ROUTABLE:
            return FindingState.ROUTABLE
        return FindingState.REJECTED

    def is_routable(self, finding_hash: str) -> bool:
        """True ONLY after a recorded human ROUTABLE verdict (fail-closed)."""
        return self.finding_state(finding_hash) == FindingState.ROUTABLE

    # --- queries -------------------------------------------------------------

    def list_pending(self) -> list[PendingFindingReview]:
        """Findings still awaiting a human verdict (AWAITING_REVIEW / UNDER_REVIEW)."""
        return [it for it in self._all() if it.status != ReviewStatus.VERDICT_RECORDED]

    def list_reviewed(self) -> list[PendingFindingReview]:
        """Findings with a recorded human verdict (the inverse of ``list_pending``).

        A pure READ (no mutation) mirroring ``list_pending``: returns every queue
        item that has reached VERDICT_RECORDED — i.e. has a human-verified
        ROUTABLE/REJECTED outcome. Consumed by the public read-only vetted-outcomes
        projection (``cairn.public``); the queue itself records nothing here.
        """
        return [it for it in self._all() if it.status == ReviewStatus.VERDICT_RECORDED]

    def get(self, finding_hash: str) -> PendingFindingReview | None:
        return self._load(finding_hash)

    def get_verdict(self, finding_hash: str) -> ReviewVerdict | None:
        item = self._load(finding_hash)
        return item.verdict if item else None

    def load_finding(self, finding_hash: str) -> Finding:
        """Load the stored (inert) finding by its content address."""
        if not self._ledger.blobs.has(finding_hash):
            raise VettingError(f"no finding at content key: {finding_hash}")
        return Finding.from_dict(self._ledger.blobs.get_json(finding_hash))

    # --- persistence helpers -------------------------------------------------

    def _require(self, finding_hash: str) -> PendingFindingReview:
        item = self._load(finding_hash)
        if item is None:
            raise VettingError(f"finding {finding_hash} is not in the finding-vet queue")
        return item

    def _all(self) -> list[PendingFindingReview]:
        return self._store.all()

    def _load(self, finding_hash: str) -> PendingFindingReview | None:
        return self._store.load(finding_hash)

    def _persist(self, item: PendingFindingReview) -> None:
        self._store.persist(item.finding_hash, item.to_dict())
