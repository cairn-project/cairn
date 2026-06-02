"""Recipient registry + explicit fallback.

The registry holds mission-neutral recipients (id + locality/domain tags + channel)
and a designated EXPLICIT fallback recipient — the locality-aware escalation target,
distinct from "no recipient".
"""

from __future__ import annotations

import pytest

from cairn.routing import (
    InMemoryRecipientChannel,
    Recipient,
    RecipientRegistry,
    RoutingError,
)


def _recipient(rid, locality, domain) -> Recipient:
    return Recipient.create(
        rid, locality=locality, domain=domain, channel=InMemoryRecipientChannel()
    )


# --- registry + explicit fallback -------------------------------


def test_registry_holds_recipients_and_returns_them():
    reg = RecipientRegistry()
    r1 = _recipient("r1", {"region-a"}, {"kind-x"})
    r2 = _recipient("r2", {"region-b"}, {"kind-y"})
    reg.add(r1).add(r2)
    ids = {r.recipient_id for r in reg.recipients()}
    assert ids == {"r1", "r2"}
    assert reg.get("r1") is r1


def test_fallback_is_explicit_and_distinct_from_no_recipient():
    reg = RecipientRegistry()
    assert reg.fallback is None  # no implicit fallback
    fb = _recipient("fallback", set(), set())
    reg.set_fallback(fb)
    assert reg.fallback is fb


def test_recipient_tags_are_normalized_to_frozensets():
    r = _recipient("r1", ["region-a", "region-a"], ["kind-x"])
    assert r.locality == frozenset({"region-a"})
    assert r.domain == frozenset({"kind-x"})


def test_duplicate_recipient_id_is_refused():
    reg = RecipientRegistry()
    reg.add(_recipient("r1", {"region-a"}, {"kind-x"}))
    with pytest.raises(RoutingError):
        reg.add(_recipient("r1", {"region-b"}, {"kind-y"}))


def test_get_unknown_recipient_raises():
    reg = RecipientRegistry()
    with pytest.raises(RoutingError):
        reg.get("nope")
