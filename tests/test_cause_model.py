"""Cause-layer tests: the Cause first-class object.

Offline, no pre-arranged ledger state.
"""

from __future__ import annotations

from cairn.cause.model import (
    FRAME_KEYS,
    Cause,
    CauseStatus,
    FiveFrameAssessment,
    FrameVerdict,
)


def _draft(name="Benign cause", by="req"):
    return {
        "name": name,
        "description": "a generic, mission-neutral cause",
        "target_conduct": "some publicly-observable conduct",
        "protected_boundary": "no persons profiled/stored/reported",
        "output_schema_ref": "result_v0",
        "partner_of_record_posture": "maintainer is actor-of-record",
        "created_by": by,
        "five_frame": {k: {"frame": k, "claim": f"{k} ok", "passes": True} for k in FRAME_KEYS},
    }


def _cause(status=CauseStatus.REQUESTED):
    d = _draft()
    return Cause.from_dict(
        {
            "cause_id": Cause.derive_id(d),
            "status": status.value,
            "created_at": 0.0,
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


def test_fresh_cause_is_requested_and_not_listable():
    c = _cause()
    assert c.status == CauseStatus.REQUESTED
    assert c.is_publicly_listable is False


def test_listability_rule_per_status():
    # GATED LISTING: only APPROVED / LIVE are publicly listable.
    assert _cause(CauseStatus.APPROVED).is_publicly_listable is True
    assert _cause(CauseStatus.LIVE).is_publicly_listable is True
    assert _cause(CauseStatus.REQUESTED).is_publicly_listable is False
    assert _cause(CauseStatus.REJECTED).is_publicly_listable is False
    assert _cause(CauseStatus.PAUSED).is_publicly_listable is False


def test_to_from_dict_roundtrips():
    c = _cause(CauseStatus.APPROVED)
    assert Cause.from_dict(c.to_dict()) == c


def test_content_addressed_id_is_stable_for_same_draft():
    # Same immutable draft → same id; the id identifies the cause, not its state.
    d1 = _draft()
    d2 = _draft()
    assert Cause.derive_id(d1) == Cause.derive_id(d2)
    # A different name → a different id.
    assert Cause.derive_id(_draft(name="other")) != Cause.derive_id(d1)


def test_id_stable_across_lifecycle_status_change():
    d = _draft()
    cid = Cause.derive_id(d)
    # derive_id excludes status/decision fields, so it stays constant.
    assert Cause.derive_id({**d, "status": "approved"}) == cid


def test_five_frame_assessment_completeness():
    full = FiveFrameAssessment(verdicts={k: FrameVerdict(k, "ok", True) for k in FRAME_KEYS})
    assert full.is_complete() is True
    partial = FiveFrameAssessment(
        verdicts={k: FrameVerdict(k, "ok", True) for k in list(FRAME_KEYS)[:3]}
    )
    assert partial.is_complete() is False
