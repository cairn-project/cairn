"""ReportingOrgFinder — resolve the REAL public reporting org for a flagged record.

The genuinely-"find the right partner" step of the demo. Given a flagged
open-data-feed record, it resolves the **actual** public reporting organization
for that dataset's steward — a public, non-person org inbox — and returns it as a
mission-neutral ``Recipient``.

PUBLIC-INFO-ONLY + FAIL-CLOSED (load-bearing safety guarantees):
  * It resolves ONLY public org/agency reporting surfaces (documented complaint
    inboxes, listed points-of-contact). It performs NO people-search, NO
    private-data lookup, NO scraping of individuals. The subject is always a
    DATASET RECORD; the recipient is always an ORG INBOX, never a person.
  * It is READ-ONLY: it resolves a contact; it never submits a form, posts, or
    contacts anyone.
  * It FAILS CLOSED: a record whose steward has no resolvable public contact
    yields ``None`` (no recipient) — the finder NEVER guesses a recipient or
    reaches for a private contact. The downstream dump records "no public contact
    resolved; do not proceed" and the human still reviews.

This release ships the DETERMINISTIC path: a hand-verified seed registry of real,
public, non-person reporting inboxes (the design's claim-or-cite feasibility
list). The live public web lookup is the deferred default-on real path (same
contract, gated behind the live ride-along tier); it would write into this same
``ResolvedOrg`` shape. Either path is public-info-only, read-only, org-not-person.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..routing.channel import InMemoryRecipientChannel
from ..routing.recipient import Recipient

#: the documented public Data.gov fallback steward inbox (Data.gov User Guide).
#: A public, non-person org address — NOT an individual.
DATA_GOV_FALLBACK_CONTACT = "DataGovHelp@gsa.gov"
DATA_GOV_FALLBACK_ORG = "Data.gov / GSA open-data help desk"


@dataclass(frozen=True)
class ResolvedOrg:
    """A resolved PUBLIC reporting organization — never a person.

    ``contact`` is a public org inbox. ``source`` records HOW it was resolved (the
    lookup provenance), so the dump can show "find the right authority" honestly.
    ``is_public_org`` is always True by construction here (the registry holds only
    public org inboxes); it is carried explicitly so the dump can assert it.
    """

    org_name: str
    contact: str
    source: str
    is_public_org: bool = True


#: The hand-verified PUBLIC org-contact seed registry — keyed by steward. Every
#: entry is a public ORG inbox (documented complaint/help channel), NEVER a
#: person. Records whose steward is not present here (or is the "unknown"
#: sentinel) FAIL CLOSED (no recipient resolved).
_PUBLIC_ORG_REGISTRY: dict[str, ResolvedOrg] = {
    "data.gov": ResolvedOrg(
        org_name=DATA_GOV_FALLBACK_ORG,
        contact=DATA_GOV_FALLBACK_CONTACT,
        source=(
            "Data.gov User Guide — the documented public channel for reporting a "
            "broken link or bad metadata is the dataset's listed point-of-contact, "
            f"with the fallback {DATA_GOV_FALLBACK_CONTACT} (a public org inbox)."
        ),
    ),
}


class ReportingOrgFinder:
    """Resolve the public reporting org for a flagged record (fail-closed)."""

    def __init__(self, registry: dict[str, ResolvedOrg] | None = None) -> None:
        self._registry = registry if registry is not None else dict(_PUBLIC_ORG_REGISTRY)

    def resolve(self, record: dict[str, Any]) -> ResolvedOrg | None:
        """Resolve the public reporting org for a seed record, or ``None``.

        Public-info-only + fail-closed: returns a public ORG inbox when the
        record's steward is in the verified registry, else ``None`` (never a
        guessed or private contact). The subject is the DATASET; the recipient is
        an ORG, never a person.
        """
        steward = str(record.get("steward", "")).strip().lower()
        if not steward or steward == "unknown":
            return None
        return self._registry.get(steward)

    def as_recipient(self, resolved: ResolvedOrg) -> Recipient:
        """Build a mission-neutral ``Recipient`` from a resolved public org.

        The recipient is reachable on the deterministic offline
        ``InMemoryRecipientChannel`` (NO network) — the scenario never delivers,
        but a recipient is the engine's shape for "the resolved reporting target".
        The recipient id is derived from the public org contact (not a person).
        """
        return Recipient.create(
            recipient_id=f"org:{resolved.contact}",
            locality={"public-open-data"},
            domain={"open-data-feed-quality"},
            channel=InMemoryRecipientChannel(name="scenario-dump-no-egress"),
        )
