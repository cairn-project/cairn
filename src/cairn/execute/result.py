"""CandidateResult — a single node's produced output + provenance.

research 02 A.2 step 5 ("attest + sign"): an adapter stamps each result with its
model family, adapter version, and a signature over ``task_id`` + result. Wave 2
carries the provenance FIELDS as PLACEHOLDERS — ``produced_at`` is a plain ISO
string and ``signature`` is an optional opaque placeholder. Real cryptographic
signing belongs to the ledger wave (PLAN §3.6); the verify-layer quorum (PLAN
§3.5) consumes these fields in a later wave.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ..types import ProvenanceRequirements


@dataclass(frozen=True)
class CandidateResult:
    """One produced result from one adapter, with provenance placeholders.

    ``output`` is the runtime's structured result (shaped to the unit's
    ``output_schema``). The remaining fields are provenance; ``signature`` is a
    placeholder this wave (no real signing).
    """

    task_id: str
    output: dict[str, Any]
    adapter_name: str
    model_family: str
    adapter_version: str
    produced_at: str  # ISO-8601 placeholder (real clock/attestation: ledger wave)
    signature: Optional[str] = None  # placeholder (real signing: ledger wave)

    def provenance_satisfies(
        self, requirements: ProvenanceRequirements
    ) -> dict[str, bool]:
        """Report which provenance requirements this candidate currently meets.

        Reporting only — NO enforcement here (the verify layer enforces, later
        wave). ``model_family`` is satisfied when a non-empty family is stamped;
        ``signed_result`` when a signature placeholder is present; ``trace`` is
        not yet produced this wave, so it reports its requirement state as unmet
        when required.
        """
        return {
            "model_family": (not requirements.model_family)
            or bool(self.model_family),
            "signed_result": (not requirements.signed_result)
            or (self.signature is not None),
            "trace": not requirements.trace,  # no trace produced this wave
        }
