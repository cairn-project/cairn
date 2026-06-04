"""The CAUSE first-class object.

A cause is a first-class object — it owns its id, name, status, its
own 5-frame gate compliance record, partner-of-record posture, and an
output_schema reference its work-units bind to. The general engine runs N causes;
this module models ONE cause as a typed, content-addressable record.

MISSION-NEUTRAL: a "cause" is generic. The `target_conduct` / `protected_boundary`
fields are free-text the requester fills; this module hard-codes NO
domain-specific specifics (those are deferred to a later phase).

Listability is GATED (sequencing): a cause is publicly listable /
accepting-compute ONLY after a decision approves it. `is_publicly_listable` is the
single source of that rule (status ∈ {APPROVED, LIVE}).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from ..ledger.blobstore import canonical_json, content_key

# The five frame keys — mirror / "ACCEPTANCE GATE — five
# non-negotiable frames". Order is fixed and load-bearing for completeness checks.
FRAME_KEYS: tuple[str, ...] = (
    "works",
    "doesnt_target_good_people",
    "legal",
    "court_grade_auditable",
    "human_verified",
)


class CauseStatus(StrEnum):
    """Lifecycle status of a cause."""

    REQUESTED = "requested"
    APPROVED = "approved"
    REJECTED = "rejected"
    LIVE = "live"
    PAUSED = "paused"


# A cause is publicly listable / accepting-compute ONLY in these states
# (listing is gated; only an approval flips it listable). REQUESTED /
# REJECTED / PAUSED are visible only through the request/decision history.
_LISTABLE_STATES = frozenset({CauseStatus.APPROVED, CauseStatus.LIVE})


@dataclass(frozen=True)
class FrameVerdict:
    """One frame of the requester's 5-frame self-assessment.

    The requester asserts, per named frame, a `claim` (how the cause meets the
    frame) and whether it `passes`. This is the requester's SELF-assessment —
    the decider's independent gate-check lives in ``gate.py``.
    """

    frame: str
    claim: str
    passes: bool

    def to_dict(self) -> dict[str, Any]:
        return {"frame": self.frame, "claim": self.claim, "passes": self.passes}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> FrameVerdict:
        return cls(frame=d["frame"], claim=d["claim"], passes=bool(d["passes"]))


@dataclass(frozen=True)
class FiveFrameAssessment:
    """The requester's self-assessment across all five frames.

    Stored as a frame-keyed mapping so completeness ("all five present") is a
    set check, not a positional one.
    """

    verdicts: dict[str, FrameVerdict] = field(default_factory=dict)

    def frame_keys(self) -> set[str]:
        return set(self.verdicts.keys())

    def is_complete(self) -> bool:
        """All five named frames self-assessed (no frame skipped)."""
        return self.frame_keys() == set(FRAME_KEYS)

    def to_dict(self) -> dict[str, Any]:
        return {k: v.to_dict() for k, v in sorted(self.verdicts.items())}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> FiveFrameAssessment:
        return cls(
            verdicts={
                k: FrameVerdict.from_dict(
                    {"frame": k, **{kk: vv for kk, vv in v.items() if kk != "frame"}}
                )
                for k, v in d.items()
            }
        )


@dataclass(frozen=True)
class Cause:
    """A first-class cause object.

    ``cause_id`` is content-addressed from the canonical draft (name +
    description + conduct/boundary + output_schema_ref + partner posture +
    self-assessment), so the same draft always yields the same id (dedup +
    tamper-evidence, mirroring the engine's content-addressing).
    """

    cause_id: str
    name: str
    description: str
    status: CauseStatus
    five_frame: FiveFrameAssessment
    target_conduct: str
    protected_boundary: str
    output_schema_ref: str
    partner_of_record_posture: str
    created_at: float
    created_by: str
    decided_at: float | None = None
    decided_by: str | None = None
    decision_reason: str | None = None

    @property
    def is_publicly_listable(self) -> bool:
        """Gated-listing rule: listable iff APPROVED or LIVE."""
        return self.status in _LISTABLE_STATES

    @staticmethod
    def derive_id(draft: dict[str, Any]) -> str:
        """Content-address the immutable draft fields → the stable cause_id.

        Decision/status fields are EXCLUDED so the id is stable across the
        request→decision lifecycle (the id identifies the cause, not its state).
        """
        material = {
            "name": draft["name"],
            "description": draft["description"],
            "target_conduct": draft["target_conduct"],
            "protected_boundary": draft["protected_boundary"],
            "output_schema_ref": draft["output_schema_ref"],
            "partner_of_record_posture": draft["partner_of_record_posture"],
            "five_frame": draft["five_frame"],
            "created_by": draft["created_by"],
        }
        return content_key(canonical_json(material))

    def to_dict(self) -> dict[str, Any]:
        return {
            "cause_id": self.cause_id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "five_frame": self.five_frame.to_dict(),
            "target_conduct": self.target_conduct,
            "protected_boundary": self.protected_boundary,
            "output_schema_ref": self.output_schema_ref,
            "partner_of_record_posture": self.partner_of_record_posture,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "decided_at": self.decided_at,
            "decided_by": self.decided_by,
            "decision_reason": self.decision_reason,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Cause:
        return cls(
            cause_id=d["cause_id"],
            name=d["name"],
            description=d["description"],
            status=CauseStatus(d["status"]),
            five_frame=FiveFrameAssessment.from_dict(d["five_frame"]),
            target_conduct=d["target_conduct"],
            protected_boundary=d["protected_boundary"],
            output_schema_ref=d["output_schema_ref"],
            partner_of_record_posture=d["partner_of_record_posture"],
            created_at=d["created_at"],
            created_by=d["created_by"],
            decided_at=d.get("decided_at"),
            decided_by=d.get("decided_by"),
            decision_reason=d.get("decision_reason"),
        )
