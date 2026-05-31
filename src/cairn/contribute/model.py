"""The contributor consent record (PLAN §3.9b).

PLAN §3.9b: "explicit contributor OPT-IN. Informed consent to exactly what their
AI will do + which cause — never silent enlistment." A ``ConsentRecord`` is that
informed consent made durable: WHO (node_id), WHICH cause (cause_id), WHEN
(consented_at), WHAT they agreed to (agreed_summary, human-readable), and whether
the consent is still ACTIVE (revocable).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ConsentRecord:
    """One contributor's recorded, revocable consent to work ONE cause.

    ``agreed_summary`` is the informed-consent text — a human-readable description
    of exactly what the node's AI will do for this cause. ``active`` is True for a
    live consent and False once revoked (the record is kept for the audit trail,
    not deleted).
    """

    node_id: str
    cause_id: str
    agreed_summary: str
    consented_at: float
    active: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "cause_id": self.cause_id,
            "agreed_summary": self.agreed_summary,
            "consented_at": self.consented_at,
            "active": self.active,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ConsentRecord":
        return cls(
            node_id=d["node_id"],
            cause_id=d["cause_id"],
            agreed_summary=d["agreed_summary"],
            consented_at=d["consented_at"],
            active=bool(d["active"]),
        )
