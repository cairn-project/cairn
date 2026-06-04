"""Trust-gated CAPTURE role (fail-closed) — the privileged-operator gate.

Producing an examination packet is a PRIVILEGED, opt-in operation; analyzing one
is OPEN. This module is the demand-side gate for the CAPTURE role, mirroring the
contribute layer's ``OptInRegistry`` posture: a ``CaptureGrant`` is persisted over
``ledger.blobs`` and every grant / revoke is appended to the SAME append-only
transparency log (``CAPTURE_ROLE_GRANTED`` / ``CAPTURE_ROLE_REVOKED``), so who may
capture is auditable on the same chain as detection + cause governance + consent.

Fail-closed: ``is_granted`` for an unknown node is False. A node with no ACTIVE
grant cannot produce a packet (enforced in ``store.capture_packet``). It forks
nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..ledger.ledger import Ledger
from ..ledger.translog import (
    KIND_CAPTURE_ROLE_GRANTED,
    KIND_CAPTURE_ROLE_REVOKED,
)


class CaptureGateError(Exception):
    """Base error for an invalid capture-role operation."""


@dataclass(frozen=True)
class CaptureGrant:
    """One operator's recorded, revocable grant of the CAPTURE role.

    ``scope_summary`` is the human-readable description of what this operator is
    permitted to capture (informed, mirroring the consent ``agreed_summary``).
    ``active`` is True for a live grant and False once revoked (kept for audit).
    """

    node_id: str
    granted_by: str
    scope_summary: str
    granted_at: float
    active: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "granted_by": self.granted_by,
            "scope_summary": self.scope_summary,
            "granted_at": self.granted_at,
            "active": self.active,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CaptureGrant:
        return cls(
            node_id=d["node_id"],
            granted_by=d["granted_by"],
            scope_summary=d["scope_summary"],
            granted_at=d["granted_at"],
            active=bool(d["active"]),
        )


class CaptureGate:
    """Persist + gate + record the trust-gated CAPTURE role over the real ledger."""

    def __init__(self, ledger: Ledger) -> None:
        self._ledger = ledger
        self._clock = ledger.clock
        self._index_dir = ledger.root / "capture_grants"
        self._index_dir.mkdir(parents=True, exist_ok=True)

    # --- grant ---------------------------------------------------------------

    def grant(self, node_id: str, granted_by: str, scope_summary: str) -> CaptureGrant:
        """Grant the CAPTURE role to ``node_id``; log ``CAPTURE_ROLE_GRANTED``."""
        grant = CaptureGrant(
            node_id=node_id,
            granted_by=granted_by,
            scope_summary=scope_summary,
            granted_at=self._clock.now(),
            active=True,
        )
        self._persist(grant)
        self._ledger.translog.append(
            KIND_CAPTURE_ROLE_GRANTED,
            {
                "node_id": node_id,
                "granted_by": granted_by,
                "scope_summary": scope_summary,
            },
        )
        return grant

    # --- revoke --------------------------------------------------------------

    def revoke(self, node_id: str) -> CaptureGrant:
        """Revoke an existing grant (flips ``active`` False); log the revoke.

        Raises ``CaptureGateError`` if there is no grant to revoke.
        """
        existing = self.get_grant(node_id)
        if existing is None:
            raise CaptureGateError(f"no capture-role grant to revoke for node {node_id!r}")
        revoked = CaptureGrant(
            node_id=existing.node_id,
            granted_by=existing.granted_by,
            scope_summary=existing.scope_summary,
            granted_at=existing.granted_at,
            active=False,
        )
        self._persist(revoked)
        self._ledger.translog.append(KIND_CAPTURE_ROLE_REVOKED, {"node_id": node_id})
        return revoked

    # --- query ---------------------------------------------------------------

    def is_granted(self, node_id: str) -> bool:
        """True iff an ACTIVE capture-role grant exists (FAIL CLOSED otherwise)."""
        grant = self.get_grant(node_id)
        return grant is not None and grant.active

    def get_grant(self, node_id: str) -> CaptureGrant | None:
        ref = self._index_dir / self._key(node_id)
        if not ref.exists():
            return None
        blob_key = ref.read_text().strip()
        return CaptureGrant.from_dict(self._ledger.blobs.get_json(blob_key))

    # --- persistence helpers -------------------------------------------------

    @staticmethod
    def _key(node_id: str) -> str:
        return node_id.replace("/", "_").replace(":", "_")

    def _persist(self, grant: CaptureGrant) -> None:
        blob_key = self._ledger.blobs.put_json(grant.to_dict())
        (self._index_dir / self._key(grant.node_id)).write_text(blob_key)
