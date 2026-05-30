"""Provenance attestation / signing-seam tests (BUILD-PLAN §25.5, PLAN §3.6).

attest_candidate upgrades a wave-2 CandidateResult's placeholder signature into a
real keyed attestation; verify_attestation passes for an untampered record and
fails when the output hash is altered.
"""

from __future__ import annotations

from dataclasses import replace

from cairn.execute.result import CandidateResult
from cairn.ledger import attest_candidate, output_hash, verify_attestation

_KEY = b"test-signing-key-not-a-secret"


def _candidate(output):
    return CandidateResult(
        task_id="task-1",
        output=output,
        adapter_name="mock",
        model_family="mock",
        adapter_version="mock-0.1.0",
        produced_at="1970-01-01T00:00:00Z",
        signature="mock-sig:placeholder",  # wave-2 placeholder
    )


def test_attest_candidate_produces_verifiable_attestation(tmp_path):
    cand = _candidate({"answer": "https://example.invalid/x", "score": 3})
    att = attest_candidate(cand, key=_KEY)

    assert att.task_id == "task-1"
    assert att.model_family == "mock"
    assert att.output_hash == output_hash(cand.output)
    assert att.signature  # a real (non-empty) signature replaced the placeholder
    assert verify_attestation(att, key=_KEY) is True


def test_altered_output_hash_fails_verification():
    cand = _candidate({"answer": "https://example.invalid/x"})
    att = attest_candidate(cand, key=_KEY)

    # Tamper: claim a different output hash but keep the old signature.
    tampered = replace(att, output_hash="0" * 64)
    assert verify_attestation(tampered, key=_KEY) is False


def test_wrong_key_fails_verification():
    cand = _candidate({"answer": "https://example.invalid/x"})
    att = attest_candidate(cand, key=_KEY)
    assert verify_attestation(att, key=b"different-key") is False
