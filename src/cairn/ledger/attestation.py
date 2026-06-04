"""Provenance attestation + signing seam.

An ``Attestation`` record binds a hash of an adapter's output to the producing
adapter/model_family and seals it with a keyed signature, turning provenance
from a bare hash into a verifiable, tamper-evident claim.

The signing is a SEAM. The local implementation is HMAC-SHA256 over the canonical
attestation bytes (stdlib ``hmac``, no heavy deps). HMAC is symmetric — it proves
integrity to a holder of the key, NOT third-party non-repudiation; real
asymmetric keypairs / A2A signed agent cards are a later phase. The function
signatures (``sign_attestation`` / ``verify_attestation``) are the stable seam
that survives that swap. The key is ALWAYS supplied by the caller — never a
checked-in secret.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, replace

from ..execute.result import CandidateResult
from .blobstore import canonical_json


@dataclass(frozen=True)
class Attestation:
    """A signed provenance record for one produced result.

    ``output_hash`` content-addresses the output; the adapter fields bind it to
    its producer; ``signature`` seals the whole record. ``signature`` is empty
    until ``sign_attestation`` is applied.
    """

    task_id: str
    output_hash: str
    adapter_name: str
    model_family: str
    adapter_version: str
    produced_at: str
    signature: str = ""

    def signing_payload(self) -> bytes:
        """Canonical bytes that the signature seals (everything but the sig)."""
        return canonical_json(
            {
                "task_id": self.task_id,
                "output_hash": self.output_hash,
                "adapter_name": self.adapter_name,
                "model_family": self.model_family,
                "adapter_version": self.adapter_version,
                "produced_at": self.produced_at,
            }
        )


def output_hash(output: dict) -> str:
    """Content address of a result output (canonical-JSON sha256)."""
    return hashlib.sha256(canonical_json(output)).hexdigest()


def sign_attestation(att: Attestation, *, key: bytes) -> Attestation:
    """Return a copy of ``att`` with an HMAC-SHA256 signature over its payload.

    SEAM: swap this body for asymmetric signing later without changing callers.
    """
    sig = hmac.new(key, att.signing_payload(), hashlib.sha256).hexdigest()
    return replace(att, signature=sig)


def verify_attestation(att: Attestation, *, key: bytes) -> bool:
    """Recompute the signature and constant-time compare it to the stored one."""
    expected = hmac.new(key, att.signing_payload(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, att.signature)


def attest_candidate(result: CandidateResult, *, key: bytes) -> Attestation:
    """Build a real, signed ``Attestation`` from a ``CandidateResult``.

    Composes on the type (reads its fields) — does NOT fork it. Upgrades
    the candidate's placeholder ``signature`` into a real keyed signature over a
    content-addressed output hash bound to the producing adapter.
    """
    att = Attestation(
        task_id=result.task_id,
        output_hash=output_hash(result.output),
        adapter_name=result.adapter_name,
        model_family=result.model_family,
        adapter_version=result.adapter_version,
        produced_at=result.produced_at,
    )
    return sign_attestation(att, key=key)
