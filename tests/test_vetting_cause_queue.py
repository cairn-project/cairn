"""Cause-vetting gate tests.

Exercises the human cause-vetting queue + its fail-closed bridge into the EXISTING
``CauseRegistry.decide_cause``. Offline, deterministic (FixedClock). NO pre-arranged
state beyond a freshly requested cause.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cairn.cause import CauseRegistry, CauseStatus, five_frame_gate_check
from cairn.cause.model import FRAME_KEYS
from cairn.ledger import FixedClock, Ledger, verify_log
from cairn.ledger.translog import (
    KIND_CAUSE_VET_ASSIGNED,
    KIND_CAUSE_VET_ENQUEUED,
    KIND_CAUSE_VET_VERDICT,
)
from cairn.vetting import CauseVetQueue, ReviewStatus, VettingError

_KEY = b"vetting-cause-test-key-not-secret"
_DRAFT = (
    Path(__file__).resolve().parents[1]
    / "src/cairn/fixtures/cause_draft_benign.json"
)


def _all_pass_gate():
    return five_frame_gate_check({k: True for k in FRAME_KEYS})


def _fresh(tmp_path):
    ledger = Ledger(tmp_path / "ledger", FixedClock(start=0.0), signing_key=_KEY)
    registry = CauseRegistry(ledger)
    draft = json.loads(_DRAFT.read_text())
    cause = registry.submit_cause_request(draft)
    return ledger, registry, cause


# --- enqueue --------------------------------------------------------


def test_enqueue_requested_cause_lands_pending_and_logged(tmp_path):
    ledger, _registry, cause = _fresh(tmp_path)
    queue = CauseVetQueue(ledger)
    item = queue.enqueue(cause)
    assert item.status == ReviewStatus.AWAITING_REVIEW
    assert [i.cause_id for i in queue.list_pending()] == [cause.cause_id]
    kinds = [e.kind for e in ledger.translog.entries()]
    assert kinds.count(KIND_CAUSE_VET_ENQUEUED) == 1


def test_enqueue_already_decided_cause_refused(tmp_path):
    ledger, registry, cause = _fresh(tmp_path)
    registry.decide_cause(
        cause.cause_id, approve=True, reason="approved directly",
        decider="anchor", gate_result=_all_pass_gate(),
    )
    decided = registry.get_cause(cause.cause_id)
    assert decided.status == CauseStatus.APPROVED
    queue = CauseVetQueue(ledger)
    with pytest.raises(VettingError):
        queue.enqueue(decided)


def test_enqueue_twice_refused(tmp_path):
    ledger, _registry, cause = _fresh(tmp_path)
    queue = CauseVetQueue(ledger)
    queue.enqueue(cause)
    with pytest.raises(VettingError):
        queue.enqueue(cause)


# --- assign ---------------------------------------------------------


def test_assign_moves_to_under_review_and_logs(tmp_path):
    ledger, _registry, cause = _fresh(tmp_path)
    queue = CauseVetQueue(ledger)
    queue.enqueue(cause)
    item = queue.assign(cause.cause_id, reviewer_id="vetter-1")
    assert item.status == ReviewStatus.UNDER_REVIEW
    assert item.assigned_to == "vetter-1"
    kinds = [e.kind for e in ledger.translog.entries()]
    assert kinds.count(KIND_CAUSE_VET_ASSIGNED) == 1


# --- recorded human verdict + no-silent-rejection -------------------


def test_record_approve_verdict_logged(tmp_path):
    ledger, _registry, cause = _fresh(tmp_path)
    queue = CauseVetQueue(ledger)
    queue.enqueue(cause)
    item = queue.record_verdict(
        cause.cause_id, approve=True, reason="benign; all frames pass",
        reviewer_id="vetter-1",
    )
    assert item.status == ReviewStatus.VERDICT_RECORDED
    assert item.verdict.decision == "approve"
    assert item.verdict.reviewer_id == "vetter-1"
    assert item.verdict.recorded_at == 0.0  # FixedClock
    kinds = [e.kind for e in ledger.translog.entries()]
    assert kinds.count(KIND_CAUSE_VET_VERDICT) == 1


def test_reject_without_reason_refused_no_silent_rejection(tmp_path):
    ledger, _registry, cause = _fresh(tmp_path)
    queue = CauseVetQueue(ledger)
    queue.enqueue(cause)
    with pytest.raises(VettingError):
        queue.record_verdict(cause.cause_id, approve=False, reason="   ",
                             reviewer_id="vetter-1")
    # nothing recorded → still pending
    assert queue.get_verdict(cause.cause_id) is None


def test_double_verdict_refused(tmp_path):
    ledger, _registry, cause = _fresh(tmp_path)
    queue = CauseVetQueue(ledger)
    queue.enqueue(cause)
    queue.record_verdict(cause.cause_id, approve=True, reason="ok",
                         reviewer_id="vetter-1")
    with pytest.raises(VettingError):
        queue.record_verdict(cause.cause_id, approve=False, reason="changed mind",
                             reviewer_id="vetter-1")


# --- fail-closed bridge into the existing cause decision ------------


def test_apply_without_recorded_verdict_refused_and_not_listable(tmp_path):
    ledger, registry, cause = _fresh(tmp_path)
    queue = CauseVetQueue(ledger)
    queue.enqueue(cause)
    # NO human verdict recorded yet → the bridge refuses, the cause stays
    # non-listable (fail-closed: no other path to decide_cause).
    with pytest.raises(VettingError):
        queue.apply_cause_verdict(cause.cause_id, registry, _all_pass_gate())
    assert registry.get_cause(cause.cause_id).status == CauseStatus.REQUESTED
    assert registry.list_causes() == []


def test_apply_approve_verdict_feeds_decision_and_lists(tmp_path):
    ledger, registry, cause = _fresh(tmp_path)
    queue = CauseVetQueue(ledger)
    queue.enqueue(cause)
    queue.record_verdict(cause.cause_id, approve=True,
                         reason="human vetter approves", reviewer_id="vetter-1")
    decided = queue.apply_cause_verdict(cause.cause_id, registry, _all_pass_gate())
    assert decided.status == CauseStatus.APPROVED
    # The human verdict's reason + reviewer are the decision-of-record.
    assert decided.decision_reason == "human vetter approves"
    assert decided.decided_by == "vetter-1"
    assert [c.cause_id for c in registry.list_causes()] == [cause.cause_id]


def test_apply_reject_verdict_keeps_cause_unlistable(tmp_path):
    ledger, registry, cause = _fresh(tmp_path)
    queue = CauseVetQueue(ledger)
    queue.enqueue(cause)
    queue.record_verdict(cause.cause_id, approve=False,
                         reason="fails human review", reviewer_id="vetter-1")
    decided = queue.apply_cause_verdict(cause.cause_id, registry, _all_pass_gate())
    assert decided.status == CauseStatus.REJECTED
    assert registry.list_causes() == []


# --- transparency ---------------------------------------------------


def test_full_cause_gate_log_verifies(tmp_path):
    ledger, registry, cause = _fresh(tmp_path)
    queue = CauseVetQueue(ledger)
    queue.enqueue(cause)
    queue.assign(cause.cause_id, reviewer_id="vetter-1")
    queue.record_verdict(cause.cause_id, approve=True, reason="ok",
                         reviewer_id="vetter-1")
    queue.apply_cause_verdict(cause.cause_id, registry, _all_pass_gate())
    assert verify_log(ledger.translog._path).ok  # noqa: SLF001
