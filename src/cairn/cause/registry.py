"""Cause registry + request intake + gated decision + public list.

Composes on the REAL engine — it does NOT fork the ledger:
  * ``ledger.blobs`` content-addressed cause storage
  * ``ledger.translog``  the SAME append-only CT-style log the engine already
                         writes detection auditability to ("ONE log,
                         TWO uses"); cause requests + decisions are its second
                         use (CAUSE_REQUEST / CAUSE_DECISION kinds already exist).
  * ``verify_log`` the no-silent-rejection guarantee.

The gate: a cause CANNOT be listed-as-live / accept compute until a
decision approves it. ``submit_cause_request`` only records the request (status
REQUESTED, NOT listable). ``decide_cause`` records a reasoned CAUSE_DECISION —
approval OR rejection, WITH the reason — and ONLY approval flips the cause
listable. No decision is recordable without a non-empty reason AND a COMPLETE
five-frame gate-check (structure enforced — ``gate.py``).
"""

from __future__ import annotations

from ..ledger.indexed_store import IndexedBlobStore
from ..ledger.ledger import Ledger
from ..ledger.translog import (
    KIND_CAUSE_DECISION,
    KIND_CAUSE_REQUEST,
    verify_log,
)
from .gate import GateCheckResult
from .model import Cause, CauseStatus


class CauseError(Exception):
    """Raised on an invalid cause operation (unknown id, ungated decision)."""


class CauseRegistry:
    """Persist + intake + decide + list causes over the real ledger."""

    def __init__(self, ledger: Ledger) -> None:
        self._ledger = ledger
        self._store: IndexedBlobStore[Cause] = IndexedBlobStore(ledger, "causes", Cause.from_dict)
        self._clock = ledger.clock

    # --- intake --------------------------------------------------------------

    def submit_cause_request(self, draft: dict) -> Cause:
        """Record a cause REQUEST. NOT publicly listable yet.

        ``draft`` carries the cause's immutable fields + the requester's
        ``five_frame`` self-assessment + ``created_by``. The id is content-
        addressed from the draft (stable across the lifecycle). A CAUSE_REQUEST
        entry is appended to the public append-only transparency log.
        """
        d = dict(draft)
        d.setdefault("created_by", "anonymous")
        cause_id = Cause.derive_id(d)

        cause = Cause.from_dict(
            {
                "cause_id": cause_id,
                "status": CauseStatus.REQUESTED.value,
                "created_at": self._clock.now(),
                "decided_at": None,
                "decided_by": None,
                "decision_reason": None,
                **{
                    k: d[k]
                    for k in (
                        "name",
                        "description",
                        "target_conduct",
                        "protected_boundary",
                        "output_schema_ref",
                        "partner_of_record_posture",
                        "five_frame",
                        "created_by",
                    )
                },
            }
        )

        self._persist(cause)
        self._ledger.translog.append(
            KIND_CAUSE_REQUEST,
            {
                "cause_id": cause.cause_id,
                "name": cause.name,
                "blob_key": self._blob_key(cause),
                "created_by": cause.created_by,
            },
        )
        return cause

    # --- gated decision ------------------------------------------------------

    def decide_cause(
        self,
        cause_id: str,
        approve: bool,
        reason: str,
        decider: str,
        gate_result: GateCheckResult,
    ) -> Cause:
        """Record a reasoned approve/reject decision.

        Enforces: a non-empty ``reason`` (no silent decision) AND a COMPLETE
        five-frame gate-check (every frame addressed — structure enforced). Both
        approvals and rejections are recorded WITH the reason on the public log.
        Only approval flips the cause publicly listable (the gate).
        """
        if not reason or not reason.strip():
            raise CauseError("a cause decision requires a non-empty reason (no silent decision)")
        if not gate_result.complete:
            raise CauseError(
                "the five-frame gate-check is incomplete "
                f"(missing frames: {gate_result.missing_frames}); "
                "the decider must address all five frames"
            )

        cause = self.get_cause(cause_id)
        new_status = CauseStatus.APPROVED if approve else CauseStatus.REJECTED
        decided = Cause.from_dict(
            {
                **cause.to_dict(),
                "status": new_status.value,
                "decided_at": self._clock.now(),
                "decided_by": decider,
                "decision_reason": reason,
            }
        )
        self._persist(decided)
        self._ledger.translog.append(
            KIND_CAUSE_DECISION,
            {
                "cause_id": decided.cause_id,
                "approved": bool(approve),
                "reason": reason,
                "decider": decider,
                "frames_passed": gate_result.frames_passed,
                "frames_failed": gate_result.frames_failed,
            },
        )
        return decided

    # --- public list ---------------------------------------------------------

    def list_causes(self, status_filter: CauseStatus | None = None) -> list[Cause]:
        """List causes.

        Default (no filter): ONLY publicly-listable causes (APPROVED / LIVE) —
        the public cause list. An explicit ``status_filter`` returns the
        request/decision history view for that status (visible, but a REQUESTED
        or REJECTED cause is NOT "accepting compute").
        """
        causes = self._store.all()
        if status_filter is None:
            return [c for c in causes if c.is_publicly_listable]
        return [c for c in causes if c.status == status_filter]

    def get_cause(self, cause_id: str) -> Cause:
        cause = self._store.load(cause_id)
        if cause is None:
            raise CauseError(f"unknown cause_id: {cause_id}")
        return cause

    # --- transparency --------------------------------------------------------

    def verify_transparency(self):
        """Independently re-verify the transparency log.

        Reuses the engine's ``verify_log`` — the no-silent-rejection guarantee
        holds over cause requests + decisions exactly as it does over detection
        entries (the SAME chain).
        """
        return verify_log(self._ledger.translog.path)

    # --- persistence helpers -------------------------------------------------

    def _blob_key(self, cause: Cause) -> str:
        return self._ledger.blobs.put_json(cause.to_dict())

    def _persist(self, cause: Cause) -> None:
        self._store.persist(cause.cause_id, cause.to_dict())
