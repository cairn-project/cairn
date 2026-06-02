"""OUTCOME-ALTITUDE e2e — the full detect→vet→ACT loop, fresh ledger.

Drives the REAL production entry points end to end on a fresh ledger with NO
pre-arranged state, proving the routing/action spine operationally:

  (a) capture a benign packet (REAL capture_packet) → flag a synthetic finding (REAL
      FindingVetQueue.flag) → record a human ROUTABLE verdict → dispatch_routable_finding
      selects the MATCHING recipient, delivers over the deterministic offline channel,
      and records the action (FINDING_ROUTED + ROUTE_ACK_RECORDED); the RoutingRecord
      names the recipient + the ack.
  (b) a SECOND routable finding whose locality/domain match nothing routes via
      ESCALATED_TO_FALLBACK to the explicit fallback (no silent drop), recorded.
  (c) a NON-ROUTABLE finding (rejected verdict) is REFUSED (RoutingRefused) — not
      routed, not delivered, not recorded.
  (d) verify_log over the produced transparency log is ok.

The load-bearing guarantee shown operationally: only a human-verified ROUTABLE
finding reaches a recorded action, and every routable finding routes somewhere
(matched OR explicit escalation) — there is no bypass and no silent drop.
"""

from __future__ import annotations

import pytest

from cairn.capture import CaptureGate, StaticDocumentCapturePort, capture_packet
from cairn.ledger import FixedClock, Ledger, verify_log
from cairn.ledger.translog import KIND_FINDING_ROUTED, KIND_ROUTE_ACK_RECORDED
from cairn.routing import (
    FindingRoutingAttributes,
    InMemoryRecipientChannel,
    Recipient,
    RecipientRegistry,
    RoutingRefused,
    dispatch_routable_finding,
)
from cairn.vetting import AutomatedVerdict, FindingVetQueue

_KEY = b"routing-e2e-key-not-secret"


def _routable_finding(queue, packet_hash, *, confidence):
    finding = queue.flag(
        packet_hash=packet_hash,
        automated_verdict=AutomatedVerdict(flag_label="flagged", confidence=confidence),
        flagged_by="node-1",
        cause_id="cause-x",
    )
    queue.record_verdict(
        finding.finding_hash, routable=True, reason="human finding-vetter confirms",
        reviewer_id="finding-vetter",
    )
    return finding


def test_routing_spine_full_loop_end_to_end(tmp_path):
    # Fresh ledger, no pre-arranged state.
    ledger = Ledger(tmp_path / "ledger", FixedClock(start=0.0), signing_key=_KEY)

    # A real benign capture produces the packet_hash the findings reference.
    cgate = CaptureGate(ledger)
    cgate.grant("operator-1", granted_by="anchor", scope_summary="benign fixtures")
    packet = capture_packet(
        StaticDocumentCapturePort(), gate=cgate, ledger=ledger,
        node_id="operator-1", cause_id="cause-x",
    )

    queue = FindingVetQueue(ledger)
    channel = InMemoryRecipientChannel()
    registry = RecipientRegistry()
    registry.add(
        Recipient.create(
            "recipient-region-a", locality={"region-a"}, domain={"kind-x"},
            channel=channel,
        )
    )
    registry.set_fallback(
        Recipient.create(
            "escalation-default", locality=set(), domain=set(), channel=channel,
        )
    )

    # === (a) MATCHED route — the recorded action ============================
    f1 = _routable_finding(queue, packet.packet_hash, confidence=0.91)
    rec1 = dispatch_routable_finding(
        f1.finding_hash, ledger=ledger, finding_queue=queue, registry=registry,
        attributes=FindingRoutingAttributes.of(locality={"region-a"}, domain={"kind-x"}),
    )
    assert rec1.recipient_id == "recipient-region-a"
    assert rec1.route_reason == "matched"
    assert rec1.ack.accepted is True
    assert channel.dispatched[-1].finding_hash == f1.finding_hash

    # === (b) NO-MATCH route — explicit escalation, no silent drop ==========
    f2 = _routable_finding(queue, packet.packet_hash, confidence=0.77)
    rec2 = dispatch_routable_finding(
        f2.finding_hash, ledger=ledger, finding_queue=queue, registry=registry,
        attributes=FindingRoutingAttributes.of(locality={"region-z"}, domain={"kind-z"}),
    )
    assert rec2.recipient_id == "escalation-default"
    assert rec2.route_reason == "escalated_to_fallback"

    # === (c) NON-ROUTABLE finding is REFUSED ===============================
    f3 = queue.flag(
        packet_hash=packet.packet_hash,
        automated_verdict=AutomatedVerdict(flag_label="flagged", confidence=0.5),
        flagged_by="node-1", cause_id="cause-x",
    )
    queue.record_verdict(
        f3.finding_hash, routable=False, reason="human rejects", reviewer_id="v2"
    )
    before = len(ledger.translog.entries())
    with pytest.raises(RoutingRefused):
        dispatch_routable_finding(
            f3.finding_hash, ledger=ledger, finding_queue=queue, registry=registry,
            attributes=FindingRoutingAttributes.of(locality={"region-a"}, domain={"kind-x"}),
        )
    # Refused => no routing entries were appended for it.
    assert len(ledger.translog.entries()) == before

    # Exactly two routed findings reached a recorded action (f1, f2 — not f3).
    routed = [e for e in ledger.translog.entries() if e.kind == KIND_FINDING_ROUTED]
    acks = [e for e in ledger.translog.entries() if e.kind == KIND_ROUTE_ACK_RECORDED]
    assert len(routed) == 2
    assert len(acks) == 2
    assert {e.payload["finding_hash"] for e in routed} == {
        f1.finding_hash, f2.finding_hash
    }

    # === (d) TRANSPARENCY ==================================================
    assert verify_log(ledger.translog._path).ok  # noqa: SLF001
