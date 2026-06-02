"""RecipientChannel seam + the deterministic offline channel.

The only channel shipped this release is deterministic + offline: it records every
dispatch and returns a DispatchAck whose ack_ref is derived from the dispatch
material (reproducible, no network, no randomness).
"""

from __future__ import annotations

from cairn.routing import (
    DispatchAck,
    InMemoryRecipientChannel,
    RecipientChannel,
    RoutingDispatch,
)


def _dispatch(recipient_id="r1", reason="matched") -> RoutingDispatch:
    return RoutingDispatch(
        finding_hash="f" * 64,
        packet_hash="p" * 64,
        flag_label="flagged",
        cause_id="cause-x",
        recipient_id=recipient_id,
        route_reason=reason,
    )


# --- the seam + the deterministic offline channel ---------------


def test_in_memory_channel_satisfies_the_recipient_channel_protocol():
    ch = InMemoryRecipientChannel()
    assert isinstance(ch, RecipientChannel)  # runtime_checkable Protocol
    assert ch.name == "in-memory"


def test_deliver_records_the_dispatch_and_returns_an_accepting_ack():
    ch = InMemoryRecipientChannel()
    assert ch.dispatched == ()
    ack = ch.deliver(_dispatch(), acknowledged_at=12.0)
    assert isinstance(ack, DispatchAck)
    assert ack.accepted is True
    assert ack.channel == "in-memory"
    assert ack.acknowledged_at == 12.0
    assert len(ch.dispatched) == 1
    assert ch.dispatched[0].recipient_id == "r1"


def test_ack_ref_is_deterministic_from_dispatch_material_not_random():
    # Same dispatch material => same ack_ref (offline reproducibility, no nonce).
    ch_a = InMemoryRecipientChannel()
    ch_b = InMemoryRecipientChannel()
    ack_a = ch_a.deliver(_dispatch(), acknowledged_at=1.0)
    ack_b = ch_b.deliver(_dispatch(), acknowledged_at=999.0)  # time differs
    assert ack_a.ack_ref == ack_b.ack_ref  # ack_ref is independent of time
    assert len(ack_a.ack_ref) == 64  # sha256 hex


def test_different_dispatch_material_yields_different_ack_ref():
    ch = InMemoryRecipientChannel()
    a = ch.deliver(_dispatch(recipient_id="r1"), acknowledged_at=1.0)
    b = ch.deliver(_dispatch(recipient_id="r2"), acknowledged_at=1.0)
    assert a.ack_ref != b.ack_ref


def test_channel_name_is_carried_onto_the_ack():
    ch = InMemoryRecipientChannel(name="offline-sink")
    ack = ch.deliver(_dispatch(), acknowledged_at=0.0)
    assert ack.channel == "offline-sink"
