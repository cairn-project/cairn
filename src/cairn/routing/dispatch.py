"""The dispatch driver — the fail-closed path from ROUTABLE finding to RECORDED ACTION.

``dispatch_routable_finding(...)`` is the keystone of the prime directive
("practical help = action taken"): it turns a human-verified ROUTABLE finding into a
recorded action delivered to the best-fit recipient. It:

1. **Fail-closed gates on the human-verified ROUTABLE state**: it reuses
   ``FindingVetQueue.is_routable`` / ``finding_state`` — it does NOT re-derive
   routability — and RAISES ``RoutingRefused`` for any finding that is not ROUTABLE
   (PENDING or REJECTED). A non-routable finding is REFUSED before any selection,
   delivery, or recording happens.
2. **Selects the recipient** via ``RoutingPolicy.route`` (best-fit, else explicit
   locality-aware escalation to the fallback — never a silent drop).
3. **Delivers** over the recipient's ``RecipientChannel`` (the deterministic offline
   ``InMemoryRecipientChannel`` this release).
4. **Records the action** on the SAME append-only transparency log: a
   ``KIND_FINDING_ROUTED`` entry (the routing event) AND a ``KIND_ROUTE_ACK_RECORDED``
   entry (the recipient acknowledgement/outcome). These two entries ARE the "action
   taken" the directive measures. The dispatch record is also content-addressed in
   ``ledger.blobs`` for an auditable artifact.

Composes, reimplementing nothing: the human gate is ``cairn.vetting``; the finding is
the existing mission-neutral ``Finding``; the log is the one ``TransparencyLog``;
timestamps come from the ledger's injected clock.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..ledger.ledger import Ledger
from ..ledger.translog import KIND_FINDING_ROUTED, KIND_ROUTE_ACK_RECORDED
from ..vetting.finding_queue import FindingVetQueue
from .channel import DispatchAck, RoutingDispatch
from .policy import FindingRoutingAttributes, RoutingPolicy
from .recipient import RecipientRegistry


class RoutingRefused(Exception):
    """Raised when dispatch is refused — the finding is not human-verified ROUTABLE.

    The fail-closed guarantee: only a finding whose recorded human verdict is
    ROUTABLE may be dispatched. A PENDING or REJECTED finding raises this and is
    never routed/delivered/recorded.
    """


@dataclass(frozen=True)
class RoutingRecord:
    """The recorded action — the prime directive's "action taken", as a return value.

    Summarizes both transparency entries: which recipient the finding was routed to,
    WHY (matched / escalated), over which channel, and the recipient acknowledgement.
    Content-addressed in ``ledger.blobs``; ``record_key`` is its blob content key.
    """

    finding_hash: str
    cause_id: str | None
    recipient_id: str
    route_reason: str
    channel: str
    ack: DispatchAck
    record_key: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_hash": self.finding_hash,
            "cause_id": self.cause_id,
            "recipient_id": self.recipient_id,
            "route_reason": self.route_reason,
            "channel": self.channel,
            "ack": self.ack.to_dict(),
        }


def dispatch_routable_finding(
    finding_hash: str,
    *,
    ledger: Ledger,
    finding_queue: FindingVetQueue,
    registry: RecipientRegistry,
    attributes: FindingRoutingAttributes,
    policy: RoutingPolicy | None = None,
) -> RoutingRecord:
    """Route + deliver + record the action for a human-verified ROUTABLE finding.

    FAIL-CLOSED FIRST: refuses unless ``finding_queue.is_routable(finding_hash)``.
    Then selects the recipient (best-fit or explicit fallback escalation), delivers
    over its channel, and records a ``FINDING_ROUTED`` + a ``ROUTE_ACK_RECORDED``
    entry on the SAME transparency log. Returns the ``RoutingRecord``.
    """
    # 1. Fail-closed human-verified gate — reuse the vetting state, do not re-derive.
    if not finding_queue.is_routable(finding_hash):
        state = finding_queue.finding_state(finding_hash)
        raise RoutingRefused(
            f"finding {finding_hash} is not human-verified ROUTABLE "
            f"(state={state.value}); refusing to route. Only a finding with a "
            "recorded human ROUTABLE verdict may be dispatched (fail-closed)."
        )

    finding = finding_queue.load_finding(finding_hash)

    # 2. Select the recipient — best-fit match or explicit locality-aware escalation.
    decision = (policy or RoutingPolicy()).route(attributes, registry)
    recipient = decision.recipient

    # 3. Deliver over the recipient's channel (deterministic offline this release).
    dispatch = RoutingDispatch(
        finding_hash=finding.finding_hash,
        packet_hash=finding.packet_hash,
        flag_label=finding.automated_verdict.flag_label,
        cause_id=finding.cause_id,
        recipient_id=recipient.recipient_id,
        route_reason=decision.reason.value,
    )
    ack = recipient.channel.deliver(
        dispatch,
        acknowledged_at=ledger.clock.now(),
    )

    # 4. Record the action on the SAME transparency log — the routing event...
    ledger.translog.append(
        KIND_FINDING_ROUTED,
        {
            "finding_hash": finding.finding_hash,
            "packet_hash": finding.packet_hash,
            "cause_id": finding.cause_id,
            "recipient_id": recipient.recipient_id,
            "route_reason": decision.reason.value,
            "match_overlap": decision.overlap,
            "channel": recipient.channel.name,
        },
    )
    # ...followed by the recipient acknowledgement/outcome.
    ledger.translog.append(
        KIND_ROUTE_ACK_RECORDED,
        {
            "finding_hash": finding.finding_hash,
            "recipient_id": recipient.recipient_id,
            "accepted": ack.accepted,
            "ack_ref": ack.ack_ref,
            "channel": ack.channel,
        },
    )

    # An auditable, content-addressed record of the recorded action.
    record_body = {
        "finding_hash": finding.finding_hash,
        "cause_id": finding.cause_id,
        "recipient_id": recipient.recipient_id,
        "route_reason": decision.reason.value,
        "channel": recipient.channel.name,
        "ack": ack.to_dict(),
    }
    record_key = ledger.blobs.put_json(record_body)

    return RoutingRecord(
        finding_hash=finding.finding_hash,
        cause_id=finding.cause_id,
        recipient_id=recipient.recipient_id,
        route_reason=decision.reason.value,
        channel=recipient.channel.name,
        ack=ack,
        record_key=record_key,
    )
