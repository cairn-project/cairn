"""Routing policy — best-fit match, tie-break, locality-aware escalation (AC.ROUTE.2/3).

Best-fit selection requires BOTH locality and domain to intersect; the most-specific
match wins; ties break deterministically by recipient id. On NO match, escalation to
the EXPLICIT fallback (ESCALATED_TO_FALLBACK) — never a silent drop. A registry with
no recipients AND no fallback is a named, refused misconfiguration.
"""

from __future__ import annotations

import pytest

from cairn.routing import (
    FindingRoutingAttributes,
    InMemoryRecipientChannel,
    Recipient,
    RecipientRegistry,
    RouteReason,
    RoutingError,
    RoutingPolicy,
)


def _recipient(rid, locality, domain) -> Recipient:
    return Recipient.create(
        rid, locality=locality, domain=domain, channel=InMemoryRecipientChannel()
    )


def _attrs(locality, domain) -> FindingRoutingAttributes:
    return FindingRoutingAttributes.of(locality=locality, domain=domain)


# --- AC.ROUTE.2 — best-fit match ---------------------------------------------


def test_matches_recipient_when_both_locality_and_domain_intersect():
    reg = RecipientRegistry()
    reg.add(_recipient("r1", {"region-a"}, {"kind-x"}))
    reg.set_fallback(_recipient("fallback", set(), set()))
    d = RoutingPolicy().route(_attrs({"region-a"}, {"kind-x"}), reg)
    assert d.reason is RouteReason.MATCHED
    assert d.recipient.recipient_id == "r1"
    assert d.overlap == 2


def test_partial_match_locality_only_does_not_match_and_escalates():
    # locality intersects but domain does not => NOT a match => escalate.
    reg = RecipientRegistry()
    reg.add(_recipient("r1", {"region-a"}, {"kind-x"}))
    fb = _recipient("fallback", set(), set())
    reg.set_fallback(fb)
    d = RoutingPolicy().route(_attrs({"region-a"}, {"kind-z"}), reg)
    assert d.reason is RouteReason.ESCALATED_TO_FALLBACK
    assert d.recipient is fb


def test_most_specific_match_wins_over_less_specific():
    reg = RecipientRegistry()
    reg.add(_recipient("broad", {"region-a"}, {"kind-x"}))
    reg.add(_recipient("specific", {"region-a", "region-b"}, {"kind-x", "kind-y"}))
    reg.set_fallback(_recipient("fallback", set(), set()))
    d = RoutingPolicy().route(
        _attrs({"region-a", "region-b"}, {"kind-x", "kind-y"}), reg
    )
    assert d.reason is RouteReason.MATCHED
    assert d.recipient.recipient_id == "specific"
    assert d.overlap == 4


def test_tie_break_is_deterministic_by_lexicographic_recipient_id():
    reg = RecipientRegistry()
    # Both match with identical overlap; the lexicographically-smallest id wins.
    reg.add(_recipient("bbb", {"region-a"}, {"kind-x"}))
    reg.add(_recipient("aaa", {"region-a"}, {"kind-x"}))
    reg.set_fallback(_recipient("fallback", set(), set()))
    d1 = RoutingPolicy().route(_attrs({"region-a"}, {"kind-x"}), reg)
    d2 = RoutingPolicy().route(_attrs({"region-a"}, {"kind-x"}), reg)
    assert d1.recipient.recipient_id == "aaa"
    assert d2.recipient.recipient_id == "aaa"  # reproducible


# --- AC.ROUTE.3 — locality-aware escalation / no silent drop -----------------


def test_no_match_escalates_to_the_explicit_fallback():
    reg = RecipientRegistry()
    reg.add(_recipient("r1", {"region-a"}, {"kind-x"}))
    fb = _recipient("fallback", set(), set())
    reg.set_fallback(fb)
    d = RoutingPolicy().route(_attrs({"region-z"}, {"kind-z"}), reg)
    assert d.reason is RouteReason.ESCALATED_TO_FALLBACK
    assert d.recipient is fb
    assert d.overlap == 0


def test_empty_finding_attributes_escalate_rather_than_drop():
    reg = RecipientRegistry()
    reg.add(_recipient("r1", {"region-a"}, {"kind-x"}))
    fb = _recipient("fallback", set(), set())
    reg.set_fallback(fb)
    d = RoutingPolicy().route(_attrs(set(), set()), reg)
    assert d.reason is RouteReason.ESCALATED_TO_FALLBACK
    assert d.recipient is fb


def test_misconfigured_registry_no_recipients_no_fallback_raises_never_drops():
    reg = RecipientRegistry()  # no recipients, no fallback
    with pytest.raises(RoutingError):
        RoutingPolicy().route(_attrs({"region-a"}, {"kind-x"}), reg)


def test_no_match_with_no_fallback_raises_named_error():
    reg = RecipientRegistry()
    reg.add(_recipient("r1", {"region-a"}, {"kind-x"}))  # exists but won't match
    with pytest.raises(RoutingError):
        RoutingPolicy().route(_attrs({"region-z"}, {"kind-z"}), reg)
