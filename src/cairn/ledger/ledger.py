"""Ledger facade — the THIN coordinator (PLAN §3.1, top-pick topology).

PLAN §3.1: a git-style ledger holding ``tasks/`` (open units, content-addressed),
``claims/``, ``results/``. It is "thin, commodity, mirrorable, and
non-truth-deciding — it orders claims and stores blobs; it does NOT decide truth
(the quorum does)". This facade wires the wave-4 components into that one
coordinator:

  objects/         content-addressed blob store (tasks + results live here)
  tasks/<id>       index ref -> the task unit's blob key
  claims/<id>      the atomic exclusive-claim ref (mutual exclusion)
  results/<id>/    index refs -> stored result blobs + attestations
  translog.jsonl   the CT-style transparency log (dual-use)
  reputation.jsonl the persisted reputation delta log

Truth-deciding stays OUT of the ledger: ``record_verdict`` only WRITES the
wave-3 ``verify_unit`` verdict into the transparency log; it never decides it.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from ..execute.result import CandidateResult
from .attestation import Attestation, attest_candidate
from .blobstore import BlobStore, content_key
from .claim import Claim, ClaimRegistry
from .clock import Clock
from .reputation_store import LedgerReputation
from .translog import (
    KIND_RESULT_RECORDED,
    KIND_VERDICT_RECORDED,
    TransparencyLog,
)


class Ledger:
    """The thin coordinator: stores blobs, orders claims, records the audit log."""

    def __init__(
        self,
        root: str | os.PathLike[str],
        clock: Clock,
        *,
        signing_key: bytes,
    ) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)
        self._clock = clock
        self._signing_key = signing_key

        self.blobs = BlobStore(self._root)
        self.claims = ClaimRegistry(self._root, clock)
        self.translog = TransparencyLog(self._root / "translog.jsonl", clock)
        self.reputation = LedgerReputation(self._root / "reputation.jsonl")

        self._tasks_dir = self._root / "tasks"
        self._tasks_dir.mkdir(parents=True, exist_ok=True)
        self._results_dir = self._root / "results"
        self._results_dir.mkdir(parents=True, exist_ok=True)

    # --- tasks ---------------------------------------------------------------

    def define_task(self, unit_dict: dict[str, Any]) -> str:
        """Content-address a work-unit dict and index it under ``tasks/``.

        Returns the unit's ``task_id`` (the unit carries its own id; the blob is
        content-addressed for tamper-evidence + dedup).
        """
        blob_key = self.blobs.put_json(unit_dict)
        task_id = unit_dict["task_id"]
        ref = self._tasks_dir / task_id.replace("/", "_")
        ref.write_text(blob_key)
        return task_id

    def get_task(self, task_id: str) -> dict[str, Any]:
        ref = self._tasks_dir / task_id.replace("/", "_")
        blob_key = ref.read_text().strip()
        return self.blobs.get_json(blob_key)

    # --- claims (delegates to the atomic registry) ---------------------------

    def claim_task(self, task_id: str, node_id: str, lease_seconds: float) -> Claim:
        return self.claims.claim(task_id, node_id, lease_seconds)

    # --- results -------------------------------------------------------------

    def store_result(
        self, candidate: CandidateResult, *, attest: bool = True
    ) -> str:
        """Store a result blob (+ real attestation) and log a RESULT_RECORDED entry.

        Returns the result blob key. The attestation upgrades the wave-2
        placeholder signature into a real keyed attestation (PLAN §3.6).
        """
        result_blob = {
            "task_id": candidate.task_id,
            "output": candidate.output,
            "adapter_name": candidate.adapter_name,
            "model_family": candidate.model_family,
            "adapter_version": candidate.adapter_version,
            "produced_at": candidate.produced_at,
        }
        result_key = self.blobs.put_json(result_blob)

        attestation: Attestation | None = None
        attestation_key: str | None = None
        if attest:
            attestation = attest_candidate(candidate, key=self._signing_key)
            attestation_key = self.blobs.put_json(
                {
                    "task_id": attestation.task_id,
                    "output_hash": attestation.output_hash,
                    "adapter_name": attestation.adapter_name,
                    "model_family": attestation.model_family,
                    "adapter_version": attestation.adapter_version,
                    "produced_at": attestation.produced_at,
                    "signature": attestation.signature,
                }
            )

        # Index the result under results/<task_id>/<result_key>.
        idx_dir = self._results_dir / candidate.task_id.replace("/", "_")
        idx_dir.mkdir(parents=True, exist_ok=True)
        (idx_dir / result_key).write_text(
            json.dumps(
                {"result_key": result_key, "attestation_key": attestation_key},
                sort_keys=True,
            )
        )

        # Audit-log the recording (Frame-4 detection auditability).
        self.translog.append(
            KIND_RESULT_RECORDED,
            {
                "task_id": candidate.task_id,
                "result_key": result_key,
                "attestation_key": attestation_key,
                "model_family": candidate.model_family,
                "adapter_name": candidate.adapter_name,
            },
        )
        return result_key

    def record_verdict(self, task_id: str, verdict: Any) -> None:
        """Log a wave-3 verify verdict (does NOT decide it — only records it).

        ``verdict`` is a wave-3 ``VerifyVerdict``; the ledger reads its public,
        already-decided fields and appends a VERDICT_RECORDED transparency entry.
        """
        self.translog.append(
            KIND_VERDICT_RECORDED,
            {
                "task_id": task_id,
                "status": verdict.status,
                "accepted": bool(verdict.accepted),
                "accepted_output_hash": (
                    content_key(
                        json.dumps(
                            verdict.accepted_output, sort_keys=True
                        ).encode("utf-8")
                    )
                    if verdict.accepted_output is not None
                    else None
                ),
            },
        )
