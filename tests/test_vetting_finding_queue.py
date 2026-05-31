"""Finding-vetting gate tests (AC.VET.5–8).

Exercises the human finding-vetting queue producing the ROUTABLE/REJECTED state.
Mission-neutral: a synthetic finding references a packet hash + a generic automated
verdict. Offline, deterministic (FixedClock).
"""

from __future__ import annotations

import pytest

from cairn.ledger import FixedClock, Ledger, verify_log
from cairn.ledger.translog import (
    KIND_FINDING_FLAGGED,
    KIND_FINDING_VET_ASSIGNED,
    KIND_FINDING_VET_VERDICT,
)
from cairn.vetting import (
    AutomatedVerdict,
    FindingState,
    FindingVetQueue,
    ReviewStatus,
    VettingError,
)

_KEY = b"vetting-finding-test-key-not-secret"
_PACKET = "deadbeef" * 8  # a synthetic opaque packet-hash reference
_VERDICT = AutomatedVerdict(flag_label="flagged", confidence=0.91)


def _fresh(tmp_path):
    return Ledger(tmp_path / "ledger", FixedClock(start=0.0), signing_key=_KEY)


# --- AC.VET.5 flag/enqueue ---------------------------------------------------


def test_flag_finding_lands_pending_content_addressed_and_logged(tmp_path):
    ledger = _fresh(tmp_path)
    queue = FindingVetQueue(ledger)
    finding = queue.flag(packet_hash=_PACKET, automated_verdict=_VERDICT,
                         flagged_by="node-1")
    # content-addressed + stored under its own hash
    assert ledger.blobs.has(finding.finding_hash)
    assert [i.finding_hash for i in queue.list_pending()] == [finding.finding_hash]
    item = queue.get(finding.finding_hash)
    assert item.status == ReviewStatus.AWAITING_REVIEW
    kinds = [e.kind for e in ledger.translog.entries()]
    assert kinds.count(KIND_FINDING_FLAGGED) == 1


def test_flag_same_finding_twice_refused(tmp_path):
    ledger = _fresh(tmp_path)
    queue = FindingVetQueue(ledger)
    queue.flag(packet_hash=_PACKET, automated_verdict=_VERDICT, flagged_by="node-1")
    with pytest.raises(VettingError):
        queue.flag(packet_hash=_PACKET, automated_verdict=_VERDICT,
                   flagged_by="node-1")


# --- AC.VET.6 assign ---------------------------------------------------------


def test_assign_moves_to_under_review_and_logs(tmp_path):
    ledger = _fresh(tmp_path)
    queue = FindingVetQueue(ledger)
    finding = queue.flag(packet_hash=_PACKET, automated_verdict=_VERDICT,
                         flagged_by="node-1")
    item = queue.assign(finding.finding_hash, reviewer_id="vetter-2")
    assert item.status == ReviewStatus.UNDER_REVIEW
    assert item.assigned_to == "vetter-2"
    kinds = [e.kind for e in ledger.translog.entries()]
    assert kinds.count(KIND_FINDING_VET_ASSIGNED) == 1


# --- AC.VET.7 verdict + ROUTABLE gate (fail-closed) --------------------------


def test_not_routable_without_verdict_fail_closed(tmp_path):
    ledger = _fresh(tmp_path)
    queue = FindingVetQueue(ledger)
    finding = queue.flag(packet_hash=_PACKET, automated_verdict=_VERDICT,
                         flagged_by="node-1")
    # No human verdict → PENDING, NOT routable. There is no setter that advances it.
    assert queue.finding_state(finding.finding_hash) == FindingState.PENDING
    assert queue.is_routable(finding.finding_hash) is False


def test_routable_only_after_recorded_routable_verdict(tmp_path):
    ledger = _fresh(tmp_path)
    queue = FindingVetQueue(ledger)
    finding = queue.flag(packet_hash=_PACKET, automated_verdict=_VERDICT,
                         flagged_by="node-1")
    item = queue.record_verdict(finding.finding_hash, routable=True,
                                reason="human confirms", reviewer_id="vetter-2")
    assert item.status == ReviewStatus.VERDICT_RECORDED
    assert queue.finding_state(finding.finding_hash) == FindingState.ROUTABLE
    assert queue.is_routable(finding.finding_hash) is True
    kinds = [e.kind for e in ledger.translog.entries()]
    assert kinds.count(KIND_FINDING_VET_VERDICT) == 1


def test_reject_verdict_marks_rejected_not_routable(tmp_path):
    ledger = _fresh(tmp_path)
    queue = FindingVetQueue(ledger)
    finding = queue.flag(packet_hash=_PACKET, automated_verdict=_VERDICT,
                         flagged_by="node-1")
    queue.record_verdict(finding.finding_hash, routable=False,
                         reason="false positive on human review",
                         reviewer_id="vetter-2")
    assert queue.finding_state(finding.finding_hash) == FindingState.REJECTED
    assert queue.is_routable(finding.finding_hash) is False


def test_reject_without_reason_refused_no_silent_rejection(tmp_path):
    ledger = _fresh(tmp_path)
    queue = FindingVetQueue(ledger)
    finding = queue.flag(packet_hash=_PACKET, automated_verdict=_VERDICT,
                         flagged_by="node-1")
    with pytest.raises(VettingError):
        queue.record_verdict(finding.finding_hash, routable=False, reason="",
                             reviewer_id="vetter-2")
    # still pending; not advanced
    assert queue.is_routable(finding.finding_hash) is False


def test_double_verdict_refused(tmp_path):
    ledger = _fresh(tmp_path)
    queue = FindingVetQueue(ledger)
    finding = queue.flag(packet_hash=_PACKET, automated_verdict=_VERDICT,
                         flagged_by="node-1")
    queue.record_verdict(finding.finding_hash, routable=True, reason="ok",
                         reviewer_id="vetter-2")
    with pytest.raises(VettingError):
        queue.record_verdict(finding.finding_hash, routable=False,
                             reason="changed mind", reviewer_id="vetter-2")


def test_finding_tamper_detected_on_load(tmp_path):
    ledger = _fresh(tmp_path)
    queue = FindingVetQueue(ledger)
    finding = queue.flag(packet_hash=_PACKET, automated_verdict=_VERDICT,
                         flagged_by="node-1")
    loaded = queue.load_finding(finding.finding_hash)
    assert loaded.packet_hash == _PACKET
    assert loaded.automated_verdict.flag_label == "flagged"


# --- AC.VET.8 transparency ---------------------------------------------------


def test_full_finding_gate_log_verifies(tmp_path):
    ledger = _fresh(tmp_path)
    queue = FindingVetQueue(ledger)
    finding = queue.flag(packet_hash=_PACKET, automated_verdict=_VERDICT,
                         flagged_by="node-1")
    queue.assign(finding.finding_hash, reviewer_id="vetter-2")
    queue.record_verdict(finding.finding_hash, routable=True, reason="ok",
                         reviewer_id="vetter-2")
    assert verify_log(ledger.translog._path).ok  # noqa: SLF001
