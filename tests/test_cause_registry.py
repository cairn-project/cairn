"""Cause-layer tests: registry intake + gated decision + public list.

Drives the REAL CauseRegistry over a REAL Ledger + transparency log. Offline.
"""

from __future__ import annotations

import pytest

from cairn.cause import CauseError, CauseRegistry, CauseStatus, five_frame_gate_check
from cairn.cause.model import FRAME_KEYS
from cairn.ledger import FixedClock, Ledger
from cairn.ledger.translog import (
    KIND_CAUSE_DECISION,
    KIND_CAUSE_REQUEST,
)

_DEMO_KEY = b"cairn-cause-test-key-not-secret"


def _registry(tmp_path) -> CauseRegistry:
    ledger = Ledger(tmp_path / "ledger", FixedClock(start=0.0), signing_key=_DEMO_KEY)
    return CauseRegistry(ledger)


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


def _complete_gate(all_pass=True):
    return five_frame_gate_check(dict.fromkeys(FRAME_KEYS, all_pass))


def _kinds(registry):
    return [e.kind for e in registry._ledger.translog.entries()]  # noqa: SLF001


def test_request_is_not_publicly_listable_and_logs_cause_request(tmp_path):
    reg = _registry(tmp_path)
    cause = reg.submit_cause_request(_draft())
    assert cause.status == CauseStatus.REQUESTED
    assert cause.is_publicly_listable is False
    assert reg.list_causes() == []  # public list excludes it
    assert KIND_CAUSE_REQUEST in _kinds(reg)


def test_approval_makes_listable_and_logs_reasoned_decision(tmp_path):
    reg = _registry(tmp_path)
    cause = reg.submit_cause_request(_draft())
    decided = reg.decide_cause(
        cause.cause_id,
        approve=True,
        reason="passes all five frames; benign open-data cause",
        decider="anchor",
        gate_result=_complete_gate(),
    )
    assert decided.status == CauseStatus.APPROVED
    assert decided.is_publicly_listable is True
    assert decided.decision_reason
    # The cause is now on the public list.
    public = reg.list_causes()
    assert [c.cause_id for c in public] == [cause.cause_id]
    # A reasoned CAUSE_DECISION (approved=True) was logged.
    entries = reg._ledger.translog.entries()  # noqa: SLF001
    dec = [e for e in entries if e.kind == KIND_CAUSE_DECISION][-1]
    assert dec.payload["approved"] is True
    assert dec.payload["reason"]


def test_rejection_keeps_unlistable_and_logs_reason(tmp_path):
    reg = _registry(tmp_path)
    cause = reg.submit_cause_request(_draft())
    decided = reg.decide_cause(
        cause.cause_id,
        approve=False,
        reason="fails frame 2; could profile a protected group",
        decider="anchor",
        gate_result=_complete_gate(all_pass=False),
    )
    assert decided.status == CauseStatus.REJECTED
    assert decided.is_publicly_listable is False
    assert reg.list_causes() == []  # never on the public list
    entries = reg._ledger.translog.entries()  # noqa: SLF001
    dec = [e for e in entries if e.kind == KIND_CAUSE_DECISION][-1]
    assert dec.payload["approved"] is False
    assert dec.payload["reason"]  # NO silent rejection


def test_decision_requires_nonempty_reason(tmp_path):
    reg = _registry(tmp_path)
    cause = reg.submit_cause_request(_draft())
    with pytest.raises(CauseError, match="non-empty reason"):
        reg.decide_cause(
            cause.cause_id,
            approve=True,
            reason="   ",
            decider="anchor",
            gate_result=_complete_gate(),
        )


def test_decision_requires_complete_gate_check(tmp_path):
    reg = _registry(tmp_path)
    cause = reg.submit_cause_request(_draft())
    incomplete = five_frame_gate_check(dict.fromkeys(list(FRAME_KEYS)[:-1], True))
    with pytest.raises(CauseError, match="incomplete"):
        reg.decide_cause(
            cause.cause_id,
            approve=True,
            reason="looks fine",
            decider="anchor",
            gate_result=incomplete,
        )


def test_list_causes_default_vs_status_filter(tmp_path):
    reg = _registry(tmp_path)
    c = reg.submit_cause_request(_draft())
    # Default public list excludes a REQUESTED cause...
    assert reg.list_causes() == []
    # ...but the status history view shows it.
    requested = reg.list_causes(status_filter=CauseStatus.REQUESTED)
    assert [x.cause_id for x in requested] == [c.cause_id]


def test_transparency_log_over_cause_entries_verifies(tmp_path):
    reg = _registry(tmp_path)
    c1 = reg.submit_cause_request(_draft(name="A"))
    c2 = reg.submit_cause_request(_draft(name="B"))
    reg.decide_cause(
        c1.cause_id, approve=True, reason="ok", decider="anchor", gate_result=_complete_gate()
    )
    reg.decide_cause(
        c2.cause_id,
        approve=False,
        reason="no",
        decider="anchor",
        gate_result=_complete_gate(all_pass=False),
    )
    # No silent rejection: the whole chain (incl. cause entries) verifies.
    v = reg.verify_transparency()
    assert v.ok is True
    assert v.length == 4  # 2 requests + 2 decisions


def test_outcome_altitude_request_decide_list_e2e(tmp_path):
    # OUTCOME-ALTITUDE: real registry + real translog, no pre-arranged state.
    reg = _registry(tmp_path)
    cause = reg.submit_cause_request(_draft(name="link-rot audit"))
    assert reg.list_causes() == []  # not listable before decision (the gate)
    reg.decide_cause(
        cause.cause_id,
        approve=True,
        reason="benign; passes all five frames",
        decider="anchor",
        gate_result=_complete_gate(),
    )
    listed = reg.list_causes()
    assert len(listed) == 1
    assert listed[0].cause_id == cause.cause_id
    assert listed[0].is_publicly_listable is True
