"""Contributor opt-in registry (explicit, gated, revocable consent).

The DEMAND-SIDE of the gate: a contributor may opt a node into a cause ONLY
when that cause is publicly listable (approved/live). Opt-in to a non-listable
cause (requested / rejected / paused) is REFUSED — the same gate that keeps a
non-vetted cause out of the public list keeps it from accepting compute.

Composes on the engine: consent records persist over ``ledger.blobs`` and every
opt-in / revoke is appended to the SAME append-only transparency log
(``CONSENT_RECORDED`` / ``CONSENT_REVOKED``), so consent is auditable on the same
chain as cause decisions and detection results
extended to consent). It forks nothing.
"""

from __future__ import annotations

from ..cause.registry import CauseRegistry
from ..ledger.ledger import Ledger
from ..ledger.translog import KIND_CONSENT_RECORDED, KIND_CONSENT_REVOKED
from .model import ConsentRecord


class OptInError(Exception):
    """Base error for an invalid opt-in operation."""


class OptInRefused(OptInError):
    """Raised when opt-in is refused — the cause is not publicly listable."""


class OptInRegistry:
    """Persist + gate + record contributor consent over the real ledger."""

    def __init__(self, ledger: Ledger, cause_registry: CauseRegistry) -> None:
        self._ledger = ledger
        self._causes = cause_registry
        self._clock = ledger.clock
        self._index_dir = ledger.root / "consents"
        self._index_dir.mkdir(parents=True, exist_ok=True)

    # --- opt in --------------------------------------------------------------

    def opt_in(self, node_id: str, cause_id: str, agreed_summary: str) -> ConsentRecord:
        """Record consent for ``node_id`` to work ``cause_id``.

        REFUSES (``OptInRefused``) if the cause is not publicly listable — a
        requested / rejected / paused cause cannot accept contributor compute (the
         gate). Otherwise records an ACTIVE ``ConsentRecord`` and appends a
        ``CONSENT_RECORDED`` entry to the transparency log.
        """
        # get_cause raises CauseError on an unknown id (surfaced to the caller).
        cause = self._causes.get_cause(cause_id)
        if not cause.is_publicly_listable:
            raise OptInRefused(
                f"cannot opt into cause {cause_id!r}: it is not publicly listable "
                f"(status={cause.status.value}). Opt-in is only valid for an "
                "approved/live cause."
            )

        record = ConsentRecord(
            node_id=node_id,
            cause_id=cause_id,
            agreed_summary=agreed_summary,
            consented_at=self._clock.now(),
            active=True,
        )
        self._persist(record)
        self._ledger.translog.append(
            KIND_CONSENT_RECORDED,
            {
                "node_id": node_id,
                "cause_id": cause_id,
                "agreed_summary": agreed_summary,
            },
        )
        return record

    # --- revoke --------------------------------------------------------------

    def revoke(self, node_id: str, cause_id: str) -> ConsentRecord:
        """Revoke an existing consent (flips ``active`` False); logs the revoke.

        Raises ``OptInError`` if there is no consent to revoke.
        """
        existing = self.get_consent(node_id, cause_id)
        if existing is None:
            raise OptInError(f"no consent to revoke for node {node_id!r} on cause {cause_id!r}")
        revoked = ConsentRecord(
            node_id=existing.node_id,
            cause_id=existing.cause_id,
            agreed_summary=existing.agreed_summary,
            consented_at=existing.consented_at,
            active=False,
        )
        self._persist(revoked)
        self._ledger.translog.append(
            KIND_CONSENT_REVOKED,
            {"node_id": node_id, "cause_id": cause_id},
        )
        return revoked

    # --- query ---------------------------------------------------------------

    def is_opted_in(self, node_id: str, cause_id: str) -> bool:
        """True iff an ACTIVE consent exists for this node + cause."""
        record = self.get_consent(node_id, cause_id)
        return record is not None and record.active

    def get_consent(self, node_id: str, cause_id: str) -> ConsentRecord | None:
        ref = self._index_dir / self._key(node_id, cause_id)
        if not ref.exists():
            return None
        blob_key = ref.read_text().strip()
        return ConsentRecord.from_dict(self._ledger.blobs.get_json(blob_key))

    # --- persistence helpers -------------------------------------------------

    @staticmethod
    def _key(node_id: str, cause_id: str) -> str:
        # Filesystem-safe composite index key (node + cause).
        safe = lambda s: s.replace("/", "_").replace(":", "_")  # noqa: E731
        return f"{safe(node_id)}__{safe(cause_id)}"

    def _persist(self, record: ConsentRecord) -> None:
        blob_key = self._ledger.blobs.put_json(record.to_dict())
        (self._index_dir / self._key(record.node_id, record.cause_id)).write_text(blob_key)
