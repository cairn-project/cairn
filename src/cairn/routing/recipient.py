"""Mission-neutral recipients + the registry the routing policy selects from.

A ``Recipient`` is the entity best fit to ACT on a routed finding — generic by
construction: an ``id``, a set of mission-neutral ``locality`` tags and ``domain``
tags, and the ``RecipientChannel`` it is reachable on. NO scam/phishing/sensitive
recipients; the tags are opaque generic strings (e.g. ``"region-a"`` / ``"kind-x"``),
this layer hard-codes no domain vocabulary.

A ``RecipientRegistry`` holds a set of recipients PLUS a designated **fallback
recipient** — the explicit locality-aware escalation target. The fallback is a
first-class, named recipient (NOT "no recipient"): when nothing matches a finding's
locality/domain, the policy escalates to it and records the escalation, so a
routable finding is NEVER silently dropped.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .channel import RecipientChannel


class RoutingError(Exception):
    """Raised on an invalid routing/registry operation (e.g. a misconfigured registry).

    A misconfigured registry — no recipients AND no fallback — is a NAMED, loud
    error, never a silent drop.
    """


@dataclass(frozen=True)
class Recipient:
    """A mission-neutral entity that can act on a routed finding.

    ``locality`` / ``domain`` are sets of opaque generic tags used for best-fit
    matching; ``channel`` is the (deterministic offline, this release) seam the
    finding is delivered over.
    """

    recipient_id: str
    locality: frozenset[str]
    domain: frozenset[str]
    channel: RecipientChannel

    @staticmethod
    def create(
        recipient_id: str,
        *,
        locality: set[str] | frozenset[str] | list[str],
        domain: set[str] | frozenset[str] | list[str],
        channel: RecipientChannel,
    ) -> "Recipient":
        return Recipient(
            recipient_id=recipient_id,
            locality=frozenset(locality),
            domain=frozenset(domain),
            channel=channel,
        )


@dataclass
class RecipientRegistry:
    """A set of mission-neutral recipients + a designated explicit fallback.

    The ``fallback`` is the locality-aware escalation target. A registry
    with neither recipients nor a fallback is a misconfiguration the routing policy
    refuses loudly — it is never permitted to become a silent drop.
    """

    _recipients: dict[str, Recipient] = field(default_factory=dict)
    fallback: Optional[Recipient] = None

    def add(self, recipient: Recipient) -> "RecipientRegistry":
        """Register a recipient (by id). Returns self for chaining."""
        if recipient.recipient_id in self._recipients:
            raise RoutingError(
                f"recipient {recipient.recipient_id!r} is already registered"
            )
        self._recipients[recipient.recipient_id] = recipient
        return self

    def set_fallback(self, recipient: Recipient) -> "RecipientRegistry":
        """Designate the explicit fallback (escalation) recipient. Returns self."""
        self.fallback = recipient
        return self

    def recipients(self) -> list[Recipient]:
        """All registered recipients (excludes a fallback that was not also added)."""
        return list(self._recipients.values())

    def get(self, recipient_id: str) -> Recipient:
        if recipient_id not in self._recipients:
            raise RoutingError(f"no recipient registered with id {recipient_id!r}")
        return self._recipients[recipient_id]
