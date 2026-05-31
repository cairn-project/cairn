"""cairn.routing — the routing / action spine (the prime-directive keystone).

The prime directive is "practical help = action taken" — not problems-seen, not
reports-filed, but a RECORDED ACTION routed to an entity that can act, with
locality-aware escalation. This layer is that keystone: it turns a human-verified
ROUTABLE ``Finding`` (the ``cairn.vetting`` finding-vetting gate's output) into a
recorded action dispatched to the recipient best fit to act on it, closing
detect → verify → human-vet → ACT.

Three composed pieces (BUILD-PLAN-routing-spine.md §1):

  * ``RecipientChannel`` seam (``channel.py``) — the delivery interface a routed
    finding reaches a recipient through. The EXTENSION POINT where real network
    channels plug in later. This wave ships ONLY the deterministic, OFFLINE
    ``InMemoryRecipientChannel`` (no network, no real recipient, no randomness).
  * Routing policy (``policy.py``) — ``RoutingPolicy.route`` selects the best-fit
    recipient by mission-neutral locality+domain tags, with LOCALITY-AWARE
    ESCALATION: on no match it escalates to the registry's EXPLICIT fallback and
    records ESCALATED_TO_FALLBACK — never a silent drop.
  * Dispatch driver (``dispatch.py``) — ``dispatch_routable_finding`` FAIL-CLOSED
    gates on ``FindingVetQueue.is_routable`` (a PENDING/REJECTED finding is REFUSED,
    never routed), selects + delivers, and records the action (``FINDING_ROUTED`` +
    ``ROUTE_ACK_RECORDED``) on the SAME append-only transparency log.

Composes on the engine (ledger blobstore + the one transparency log), the vetting
finding state, the cause layer (a finding/route belongs to a cause via its
``cause_id``), and the capture packet (the finding's ``packet_hash`` reference);
forks nothing. Mission-NEUTRAL — recipients + findings are generic; no
scam/phishing/sensitive recipients or content.

DEFERRED (later, separately-security-reviewed waves): real external-recipient
integration + network egress (Safe Browsing / abuse.ch / registrars / partner
endpoints — the ``RecipientChannel`` seam is where they plug in), a real
partner-of-record directory + identity verification, retry / delivery-failure /
dead-letter handling, multi-recipient fan-out / quorum routing, and a ``cairn route``
CLI (library-only this wave).
"""

from __future__ import annotations

from .channel import (
    DispatchAck,
    InMemoryRecipientChannel,
    RecipientChannel,
    RoutingDispatch,
)
from .dispatch import RoutingRecord, RoutingRefused, dispatch_routable_finding
from .policy import (
    FindingRoutingAttributes,
    RouteReason,
    RoutingDecision,
    RoutingPolicy,
)
from .recipient import Recipient, RecipientRegistry, RoutingError

__all__ = [
    # the delivery seam + the only (deterministic offline) channel
    "RecipientChannel",
    "RoutingDispatch",
    "DispatchAck",
    "InMemoryRecipientChannel",
    # recipients + registry (with explicit fallback)
    "Recipient",
    "RecipientRegistry",
    "RoutingError",
    # the routing policy (best-fit + locality-aware escalation)
    "RoutingPolicy",
    "RoutingDecision",
    "RouteReason",
    "FindingRoutingAttributes",
    # the fail-closed dispatch driver (the recorded action)
    "dispatch_routable_finding",
    "RoutingRecord",
    "RoutingRefused",
]
