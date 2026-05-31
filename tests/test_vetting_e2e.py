"""OUTCOME-ALTITUDE e2e (AC.VET.9) — both gates, real entry points, fresh ledger.

Drives the REAL production entry points end to end on a fresh ledger with NO
pre-arranged state, proving BOTH fail-closed human gates operationally:

  (a) Cause gate: submit a cause request (REAL CauseRegistry) → enqueue into the
      cause-vet queue → assert it CANNOT list and apply_cause_verdict is REFUSED
      with no human verdict → record a human approve verdict → apply_cause_verdict
      → assert the cause now lists.
  (b) Finding gate: capture a benign packet (REAL capture_packet) → flag a
      synthetic finding referencing its packet_hash → assert NOT routable with no
      human verdict → record a human ROUTABLE verdict → assert is_routable is True.
  (c) verify_log over the produced transparency log is ok.

The load-bearing guarantee shown operationally: neither item can reach its advanced
state without a recorded human verdict — there is no advance-path that bypasses the
human.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cairn.capture import CaptureGate, StaticDocumentCapturePort, capture_packet
from cairn.cause import CauseRegistry, CauseStatus, five_frame_gate_check
from cairn.cause.model import FRAME_KEYS
from cairn.ledger import FixedClock, Ledger, verify_log
from cairn.vetting import (
    AutomatedVerdict,
    CauseVetQueue,
    FindingVetQueue,
    VettingError,
)

_KEY = b"vetting-e2e-key-not-secret"
_DRAFT = (
    Path(__file__).resolve().parents[1]
    / "src/cairn/fixtures/cause_draft_benign.json"
)


def test_two_gate_vetting_end_to_end(tmp_path):
    # Fresh ledger, no pre-arranged state.
    ledger = Ledger(tmp_path / "ledger", FixedClock(start=0.0), signing_key=_KEY)
    gate_pass = five_frame_gate_check({k: True for k in FRAME_KEYS})

    # === (a) CAUSE GATE =====================================================
    registry = CauseRegistry(ledger)
    cause = registry.submit_cause_request(json.loads(_DRAFT.read_text()))
    cause_queue = CauseVetQueue(ledger)
    cause_queue.enqueue(cause)
    cause_queue.assign(cause.cause_id, reviewer_id="cause-vetter")

    # Fail-closed: with NO recorded human verdict the cause cannot list and the
    # bridge into the existing decision is refused.
    assert registry.list_causes() == []
    with pytest.raises(VettingError):
        cause_queue.apply_cause_verdict(cause.cause_id, registry, gate_pass)
    assert registry.get_cause(cause.cause_id).status == CauseStatus.REQUESTED

    # Human verdict recorded → the bridge feeds the EXISTING decision → it lists.
    cause_queue.record_verdict(cause.cause_id, approve=True,
                               reason="human cause-vetter approves",
                               reviewer_id="cause-vetter")
    decided = cause_queue.apply_cause_verdict(cause.cause_id, registry, gate_pass)
    assert decided.status == CauseStatus.APPROVED
    assert decided.decided_by == "cause-vetter"
    assert [c.cause_id for c in registry.list_causes()] == [cause.cause_id]

    # === (b) FINDING GATE ===================================================
    # A real benign capture produces a real packet_hash the finding references.
    cgate = CaptureGate(ledger)
    cgate.grant("operator-1", granted_by="anchor", scope_summary="benign fixtures")
    packet = capture_packet(
        StaticDocumentCapturePort(), gate=cgate, ledger=ledger,
        node_id="operator-1", cause_id=cause.cause_id,
    )

    finding_queue = FindingVetQueue(ledger)
    finding = finding_queue.flag(
        packet_hash=packet.packet_hash,
        automated_verdict=AutomatedVerdict(flag_label="flagged", confidence=0.88),
        flagged_by="node-1",
        cause_id=cause.cause_id,
    )
    finding_queue.assign(finding.finding_hash, reviewer_id="finding-vetter")

    # Fail-closed: with NO recorded human verdict the finding is NOT routable.
    assert finding_queue.is_routable(finding.finding_hash) is False

    # Human verdict recorded → it becomes ROUTABLE (the human-verified state).
    finding_queue.record_verdict(finding.finding_hash, routable=True,
                                 reason="human finding-vetter confirms",
                                 reviewer_id="finding-vetter")
    assert finding_queue.is_routable(finding.finding_hash) is True

    # === (c) TRANSPARENCY ===================================================
    assert verify_log(ledger.translog._path).ok  # noqa: SLF001
