"""Dispatch driver — fail-closed gate + recorded action + transparency.

dispatch_routable_finding fail-closed gates on FindingVetQueue.is_routable (REFUSES a
PENDING/REJECTED finding), selects the recipient, delivers, and records FINDING_ROUTED
+ ROUTE_ACK_RECORDED on the SAME transparency log (covered by the unchanged verify_log).
"""

from __future__ import annotations

import pytest

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

_KEY = b"routing-dispatch-test-key-not-secret"
_PACKET = "abcdef12" * 8  # synthetic opaque packet-hash reference


def _fresh(tmp_path):
    return Ledger(tmp_path / "ledger", FixedClock(start=0.0), signing_key=_KEY)


def _registry(channel):
    reg = RecipientRegistry()
    reg.add(
        Recipient.create(
            "r1", locality={"region-a"}, domain={"kind-x"}, channel=channel
        )
    )
    reg.set_fallback(
        Recipient.create(
            "fallback", locality=set(), domain=set(), channel=channel
        )
    )
    return reg


def _attrs():
    return FindingRoutingAttributes.of(locality={"region-a"}, domain={"kind-x"})


def _flag(queue, *, confidence=0.9):
    return queue.flag(
        packet_hash=_PACKET,
        automated_verdict=AutomatedVerdict(flag_label="flagged", confidence=confidence),
        flagged_by="node-1",
        cause_id="cause-x",
    )


# --- fail-closed on the human-verified gate ---------------------


def test_pending_finding_no_verdict_is_refused_not_routed(tmp_path):
    ledger = _fresh(tmp_path)
    queue = FindingVetQueue(ledger)
    finding = _flag(queue)  # no human verdict => PENDING
    channel = InMemoryRecipientChannel()
    with pytest.raises(RoutingRefused):
        dispatch_routable_finding(
            finding.finding_hash,
            ledger=ledger,
            finding_queue=queue,
            registry=_registry(channel),
            attributes=_attrs(),
        )
    # Nothing was delivered or recorded.
    assert channel.dispatched == ()
    kinds = [e.kind for e in ledger.translog.entries()]
    assert KIND_FINDING_ROUTED not in kinds


def test_rejected_finding_is_refused_not_routed(tmp_path):
    ledger = _fresh(tmp_path)
    queue = FindingVetQueue(ledger)
    finding = _flag(queue)
    queue.record_verdict(
        finding.finding_hash, routable=False, reason="human rejects", reviewer_id="v1"
    )
    channel = InMemoryRecipientChannel()
    with pytest.raises(RoutingRefused):
        dispatch_routable_finding(
            finding.finding_hash,
            ledger=ledger,
            finding_queue=queue,
            registry=_registry(channel),
            attributes=_attrs(),
        )
    assert channel.dispatched == ()


# --- recorded action (the prime-directive unit) -----------------


def test_routable_finding_is_delivered_and_recorded(tmp_path):
    ledger = _fresh(tmp_path)
    queue = FindingVetQueue(ledger)
    finding = _flag(queue)
    queue.record_verdict(
        finding.finding_hash, routable=True, reason="human confirms", reviewer_id="v1"
    )
    channel = InMemoryRecipientChannel()
    record = dispatch_routable_finding(
        finding.finding_hash,
        ledger=ledger,
        finding_queue=queue,
        registry=_registry(channel),
        attributes=_attrs(),
    )
    # Delivered to the matching recipient over the channel.
    assert record.recipient_id == "r1"
    assert record.route_reason == "matched"
    assert record.ack.accepted is True
    assert len(channel.dispatched) == 1

    # The two transparency entries ARE the action taken.
    kinds = [e.kind for e in ledger.translog.entries()]
    assert KIND_FINDING_ROUTED in kinds
    assert KIND_ROUTE_ACK_RECORDED in kinds

    routed = next(
        e for e in ledger.translog.entries() if e.kind == KIND_FINDING_ROUTED
    )
    assert routed.payload["recipient_id"] == "r1"
    assert routed.payload["route_reason"] == "matched"
    assert routed.payload["finding_hash"] == finding.finding_hash

    ack = next(
        e for e in ledger.translog.entries() if e.kind == KIND_ROUTE_ACK_RECORDED
    )
    assert ack.payload["accepted"] is True
    assert ack.payload["ack_ref"] == record.ack.ack_ref

    # The content-addressed record is retrievable.
    assert ledger.blobs.has(record.record_key)


def test_no_match_finding_escalates_to_fallback_recorded_no_drop(tmp_path):
    ledger = _fresh(tmp_path)
    queue = FindingVetQueue(ledger)
    finding = _flag(queue)
    queue.record_verdict(
        finding.finding_hash, routable=True, reason="human confirms", reviewer_id="v1"
    )
    channel = InMemoryRecipientChannel()
    record = dispatch_routable_finding(
        finding.finding_hash,
        ledger=ledger,
        finding_queue=queue,
        registry=_registry(channel),
        # Attributes that match nothing => escalate to the explicit fallback.
        attributes=FindingRoutingAttributes.of(locality={"region-z"}, domain={"kind-z"}),
    )
    assert record.recipient_id == "fallback"
    assert record.route_reason == "escalated_to_fallback"
    routed = next(
        e for e in ledger.translog.entries() if e.kind == KIND_FINDING_ROUTED
    )
    assert routed.payload["route_reason"] == "escalated_to_fallback"


# --- transparency / verify_log ----------------------------------


def test_verify_log_covers_the_new_routing_kinds(tmp_path):
    ledger = _fresh(tmp_path)
    queue = FindingVetQueue(ledger)
    finding = _flag(queue)
    queue.record_verdict(
        finding.finding_hash, routable=True, reason="human confirms", reviewer_id="v1"
    )
    dispatch_routable_finding(
        finding.finding_hash,
        ledger=ledger,
        finding_queue=queue,
        registry=_registry(InMemoryRecipientChannel()),
        attributes=_attrs(),
    )
    v = verify_log(ledger.translog._path)  # noqa: SLF001
    assert v.ok is True
    kinds = {e.kind for e in ledger.translog.entries()}
    assert {KIND_FINDING_ROUTED, KIND_ROUTE_ACK_RECORDED} <= kinds
