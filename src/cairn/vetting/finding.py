"""The mission-neutral FINDING — a flagged item awaiting human review (Gate 2).

A ``Finding`` represents, GENERICALLY, an analyzed/flagged item: a reference to an
existing examination packet (``packet_hash`` — compose on the capture store), the
AUTOMATED verdict that flagged it (a generic ``{flag_label, confidence}`` shape —
NO domain detection logic; ``flag_label`` is an opaque generic string), plus
provenance. It carries NO scam/phishing/sensitive content — the language is
clinical and abstract by construction.

Content-addressing mirrors the engine: ``finding_hash`` is the sha256
of the canonical JSON of the immutable material, so an identical flagged item
always yields an identical hash (dedup + tamper-evidence), and the hash equals the
blob content key the finding is stored under (``finding_queue.py``).

The finding's *advanced* (routable) state is NOT a field here — it is derived
solely from a recorded human verdict in ``finding_queue.py`` (fail-closed). A
``Finding`` is only the inert flagged record under review.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from ..ledger.blobstore import canonical_json, content_key


class FindingState(str, Enum):
    """The human-verified routing-eligibility state of a finding (Gate 2 output).

    Fail-closed default is PENDING. ROUTABLE / REJECTED are reached ONLY via a
    recorded human finding-vetter verdict (``finding_queue.finding_state``). There
    is no producer of ROUTABLE other than a human verdict.
    """

    PENDING = "pending"
    ROUTABLE = "routable"
    REJECTED = "rejected"


@dataclass(frozen=True)
class AutomatedVerdict:
    """The automated (non-human) verdict that flagged an item — mission-neutral.

    ``flag_label`` is an OPAQUE generic label (e.g. "flagged") — this layer hard-codes
    no domain vocabulary. ``confidence`` is a float in [0, 1]. This is the upstream
    machine signal; the HUMAN verdict in the finding-vet gate is what makes a finding
    routable, never this.
    """

    flag_label: str
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return {"flag_label": self.flag_label, "confidence": self.confidence}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AutomatedVerdict":
        return cls(flag_label=d["flag_label"], confidence=float(d["confidence"]))


def _finding_material(
    *,
    packet_hash: str,
    automated_verdict: AutomatedVerdict,
    flagged_at: float,
    flagged_by: str,
    cause_id: Optional[str],
) -> dict[str, Any]:
    """The immutable fields the ``finding_hash`` commits to (deterministic order)."""
    return {
        "packet_hash": packet_hash,
        "automated_verdict": automated_verdict.to_dict(),
        "flagged_at": flagged_at,
        "flagged_by": flagged_by,
        "cause_id": cause_id,
    }


@dataclass(frozen=True)
class Finding:
    """A flagged item under human review — content-addressed, mission-neutral.

    ``packet_hash`` references an existing examination packet (the evidence the
    automated verdict was derived from); this finding does NOT inline the packet
    content. ``finding_hash`` is the content address (sha256 of the immutable
    material) and equals the blob key the finding is stored under.
    """

    packet_hash: str
    automated_verdict: AutomatedVerdict
    flagged_at: float
    flagged_by: str
    cause_id: Optional[str]
    finding_hash: str

    @staticmethod
    def create(
        *,
        packet_hash: str,
        automated_verdict: AutomatedVerdict,
        flagged_at: float,
        flagged_by: str,
        cause_id: Optional[str] = None,
    ) -> "Finding":
        material = _finding_material(
            packet_hash=packet_hash,
            automated_verdict=automated_verdict,
            flagged_at=flagged_at,
            flagged_by=flagged_by,
            cause_id=cause_id,
        )
        return Finding(
            packet_hash=packet_hash,
            automated_verdict=automated_verdict,
            flagged_at=flagged_at,
            flagged_by=flagged_by,
            cause_id=cause_id,
            finding_hash=content_key(canonical_json(material)),
        )

    def material_dict(self) -> dict[str, Any]:
        """The immutable material the ``finding_hash`` commits to (no finding_hash).

        Stored in the content-addressed blob store, so the blob's content key equals
        ``finding_hash`` by construction.
        """
        return _finding_material(
            packet_hash=self.packet_hash,
            automated_verdict=self.automated_verdict,
            flagged_at=self.flagged_at,
            flagged_by=self.flagged_by,
            cause_id=self.cause_id,
        )

    def to_dict(self) -> dict[str, Any]:
        d = self.material_dict()
        d["finding_hash"] = self.finding_hash
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Finding":
        """Reconstruct, RE-DERIVING ``finding_hash`` from the material.

        Accepts either the stored MATERIAL form (no ``finding_hash`` key) or the full
        ``to_dict`` form; a provided ``finding_hash`` that does not match is rejected
        (tamper-evidence).
        """
        av = AutomatedVerdict.from_dict(d["automated_verdict"])
        material = _finding_material(
            packet_hash=d["packet_hash"],
            automated_verdict=av,
            flagged_at=d["flagged_at"],
            flagged_by=d["flagged_by"],
            cause_id=d.get("cause_id"),
        )
        finding_hash = content_key(canonical_json(material))
        if "finding_hash" in d and d["finding_hash"] != finding_hash:
            raise ValueError("finding_hash mismatch (tampered finding)")
        return cls(
            packet_hash=d["packet_hash"],
            automated_verdict=av,
            flagged_at=d["flagged_at"],
            flagged_by=d["flagged_by"],
            cause_id=d.get("cause_id"),
            finding_hash=finding_hash,
        )
