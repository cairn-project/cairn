"""The ``RecipientChannel`` delivery seam + the deterministic offline channel.

A routed finding reaches a recipient through a ``RecipientChannel`` — a narrow
delivery interface (a ``Protocol``). This is the EXTENSION POINT where, in a later
separately-security-reviewed wave, real network channels (registrar / partner /
abuse endpoints, email / HTTP transport) will plug in. THIS wave ships ONLY a
deterministic, OFFLINE ``InMemoryRecipientChannel`` (AC.ROUTE.4): no network, no
real recipient, no randomness — it records every dispatch and returns a synthetic
``DispatchAck`` whose ``ack_ref`` is DERIVED from the dispatch material (so the
worked example is fully reproducible).

Mission-neutral by construction: a ``RoutingDispatch`` carries only the finding's
existing mission-neutral attributes — a ``packet_hash`` reference, an opaque
generic ``flag_label``, the owning ``cause_id``, and the chosen recipient id. No
captured content, observation bytes, analysis text, or PII is expressible here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from ..ledger.blobstore import canonical_json, content_key


@dataclass(frozen=True)
class RoutingDispatch:
    """The mission-neutral payload handed to a channel for delivery.

    Carries the finding's REFERENCE attributes only — ``finding_hash`` (content
    address), ``packet_hash`` (the evidence reference), the opaque generic
    ``flag_label``, the owning ``cause_id``, and the resolved ``recipient_id`` plus
    the ``route_reason`` (MATCHED / ESCALATED_TO_FALLBACK). There is no field for
    raw content — the dispatch cannot carry captured bytes/PII because no parameter
    accepts them.
    """

    finding_hash: str
    packet_hash: str
    flag_label: str
    cause_id: str | None
    recipient_id: str
    route_reason: str

    def material_dict(self) -> dict[str, Any]:
        """The deterministic fields the ``ack_ref`` derives from (sorted-key hash)."""
        return {
            "finding_hash": self.finding_hash,
            "packet_hash": self.packet_hash,
            "flag_label": self.flag_label,
            "cause_id": self.cause_id,
            "recipient_id": self.recipient_id,
            "route_reason": self.route_reason,
        }


@dataclass(frozen=True)
class DispatchAck:
    """A recipient's acknowledgement of a delivered dispatch — generic + deterministic.

    ``accepted`` is the recipient outcome; ``ack_ref`` is an opaque reference DERIVED
    from the dispatch material (NOT a random nonce — reproducible offline);
    ``channel`` is the delivering channel's name; ``acknowledged_at`` is a timestamp
    (supplied by the dispatch driver from the ledger's injected clock).
    """

    accepted: bool
    ack_ref: str
    channel: str
    acknowledged_at: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "ack_ref": self.ack_ref,
            "channel": self.channel,
            "acknowledged_at": self.acknowledged_at,
        }


@runtime_checkable
class RecipientChannel(Protocol):
    """The delivery seam: how a routed finding reaches a recipient.

    A channel exposes a ``name`` and a ``deliver(dispatch) -> DispatchAck``. Real
    network channels implement this Protocol in a later wave; this wave ships only
    the deterministic offline ``InMemoryRecipientChannel``.
    """

    name: str

    def deliver(self, dispatch: RoutingDispatch, *, acknowledged_at: float) -> DispatchAck:
        ...


class InMemoryRecipientChannel:
    """The ONLY channel shipped this wave — deterministic, offline, no egress.

    Records every dispatch it receives (inspectable via ``dispatched``) and returns
    a ``DispatchAck`` whose ``ack_ref`` is the sha256 of the dispatch material — so
    delivery is reproducible and verifiable offline with no network or randomness.
    Always ``accepted=True``: a deterministic in-memory sink unconditionally accepts;
    real transport failure semantics belong to the deferred real channels.
    """

    def __init__(self, name: str = "in-memory") -> None:
        self.name = name
        self._dispatched: list[RoutingDispatch] = []

    @property
    def dispatched(self) -> tuple[RoutingDispatch, ...]:
        """Every dispatch this channel has delivered, in order (inspection only)."""
        return tuple(self._dispatched)

    def deliver(
        self, dispatch: RoutingDispatch, *, acknowledged_at: float
    ) -> DispatchAck:
        """Record the dispatch + return a deterministic synthetic acknowledgement."""
        self._dispatched.append(dispatch)
        ack_ref = content_key(canonical_json(dispatch.material_dict()))
        return DispatchAck(
            accepted=True,
            ack_ref=ack_ref,
            channel=self.name,
            acknowledged_at=acknowledged_at,
        )
