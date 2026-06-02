"""The routing policy — best-fit recipient selection + locality-aware escalation.

``RoutingPolicy.route(finding_attrs, registry) -> RoutingDecision`` selects the
recipient best fit to act on a finding, given the finding's mission-neutral routing
attributes (``locality`` + ``domain`` tags). The escalation rule in one line:

    match on (locality ∩ domain); on no match, escalate to the registry's explicit
    fallback recipient and record ESCALATED_TO_FALLBACK; never return nothing.

No silent drops: every call yields a recipient — a MATCHED one or the
explicit fallback. The ONLY non-return is a RAISE on a misconfigured registry (no
recipients AND no fallback) — a named, loud error, never a drop. The attributes are
mission-neutral generic tags, NOT detection logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .recipient import Recipient, RecipientRegistry, RoutingError


class RouteReason(str, Enum):
    """Why a recipient was chosen — recorded on the transparency log (auditable).

    MATCHED: a recipient's locality AND domain tags both intersect the finding's.
    ESCALATED_TO_FALLBACK: no recipient matched; the explicit fallback was chosen.
    """

    MATCHED = "matched"
    ESCALATED_TO_FALLBACK = "escalated_to_fallback"


@dataclass(frozen=True)
class FindingRoutingAttributes:
    """The mission-neutral attributes a finding is routed on — generic tags only.

    ``locality`` / ``domain`` are sets of opaque generic tags (NOT detection logic);
    supplied at dispatch time. A finding with empty attribute sets matches nothing
    and therefore escalates to the fallback (which is correct — no silent drop).
    """

    locality: frozenset[str]
    domain: frozenset[str]

    @staticmethod
    def of(
        *,
        locality: set[str] | frozenset[str] | list[str],
        domain: set[str] | frozenset[str] | list[str],
    ) -> "FindingRoutingAttributes":
        return FindingRoutingAttributes(
            locality=frozenset(locality), domain=frozenset(domain)
        )


@dataclass(frozen=True)
class RoutingDecision:
    """The selected recipient + WHY (matched vs escalated) + the overlap score.

    ``recipient`` is always present (no silent drop). ``reason`` records whether it
    was a best-fit MATCHED selection or an ESCALATED_TO_FALLBACK escalation.
    ``overlap`` is the count of overlapping locality+domain tags for a match (0 for
    an escalation) — recorded for auditability / tie-break transparency.
    """

    recipient: Recipient
    reason: RouteReason
    overlap: int


class RoutingPolicy:
    """Best-fit recipient selection with explicit locality-aware escalation."""

    def route(
        self,
        attributes: FindingRoutingAttributes,
        registry: RecipientRegistry,
    ) -> RoutingDecision:
        """Select the best-fit recipient, else escalate to the explicit fallback.

        A recipient MATCHES iff its locality tags AND its domain tags BOTH intersect
        the finding's requested locality+domain. Among matches, the best fit has the
        most overlapping locality+domain tags; ties are broken deterministically by
        recipient id (lexicographic) so routing is reproducible. On NO match, escalate
        to the registry's explicit fallback (ESCALATED_TO_FALLBACK). If the registry
        has no recipients AND no fallback, RAISE (a named misconfiguration, never a
        silent drop).
        """
        best: tuple[int, str] | None = None
        best_recipient: Recipient | None = None
        for recipient in registry.recipients():
            loc_overlap = recipient.locality & attributes.locality
            dom_overlap = recipient.domain & attributes.domain
            if not loc_overlap or not dom_overlap:
                continue  # a match requires BOTH locality and domain to intersect
            overlap = len(loc_overlap) + len(dom_overlap)
            # Most-specific match wins; ties broken by lexicographically-smallest id.
            candidate = (overlap, recipient.recipient_id)
            if (
                best is None
                or overlap > best[0]
                or (overlap == best[0] and recipient.recipient_id < best[1])
            ):
                best = candidate
                best_recipient = recipient

        if best_recipient is not None:
            return RoutingDecision(
                recipient=best_recipient,
                reason=RouteReason.MATCHED,
                overlap=best[0],  # type: ignore[index]
            )

        # No match — locality-aware escalation to the EXPLICIT fallback (no drop).
        if registry.fallback is None:
            raise RoutingError(
                "routing registry is misconfigured: no recipient matched the "
                "finding's locality/domain AND no fallback recipient is configured. "
                "Refusing to silently drop a routable finding — configure a fallback."
            )
        return RoutingDecision(
            recipient=registry.fallback,
            reason=RouteReason.ESCALATED_TO_FALLBACK,
            overlap=0,
        )
