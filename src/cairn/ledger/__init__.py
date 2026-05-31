"""cairn.ledger — the LEDGER + TRANSPARENCY layer (wave 4, PLAN §3.1 + §3.6).

The THIN coordinator (PLAN §3.1, top-pick topology) + the tamper-evident
transparency log (PLAN §3.6, REQUIREMENTS Frame 4 + cause-vetting governance),
fully OFFLINE on the local filesystem. It ORDERS claims + STORES blobs; it does
NOT decide truth — the wave-3 verify layer (``verify_unit``) does.

  blobstore.py   content-addressed sha256 blob store        (PLAN §3.6)
  claim.py       atomic O_EXCL exclusive claim + leases      (PLAN §3.1)
  clock.py       injected Clock seam (deterministic leases)  (PLAN §3.1)
  attestation.py provenance attestation + HMAC signing seam  (PLAN §3.6)
  translog.py    hash-chained append-only CT-style log       (PLAN §3.6, Frame 4)
  reputation_store.py  ledger-persisted wave-3 reputation    (PLAN §3.5 L3)
  ledger.py      the thin coordinator facade                 (PLAN §3.1)

DUAL-USE (one log, two uses — PLAN §3.6): the SAME transparency log serves both
detection auditability (RESULT_RECORDED / VERDICT_RECORDED) AND cause-governance
no-silent-rejection (CAUSE_REQUEST / CAUSE_DECISION). ``verify_log`` independently
detects any retroactive edit/removal/reorder for both.

DEFERRED (later waves): live-model adapters, distribution storefronts,
cause-discovery/vetting GOVERNANCE workflow (this wave ships the LOG it writes to,
not the approval engine), the escalation/action engine, real asymmetric keypair
mgmt (HMAC seam ships), network mirroring/transport (filesystem-local only).
"""

from __future__ import annotations

from .attestation import (
    Attestation,
    attest_candidate,
    output_hash,
    sign_attestation,
    verify_attestation,
)
from .blobstore import BlobStore, canonical_json, content_key
from .claim import Claim, ClaimError, ClaimRegistry
from .clock import Clock, FixedClock, SystemClock
from .ledger import Ledger
from .reputation_store import LedgerReputation
from .translog import (
    GENESIS_PREV,
    KIND_CAPTURE_ROLE_GRANTED,
    KIND_CAPTURE_ROLE_REVOKED,
    KIND_CAUSE_DECISION,
    KIND_CAUSE_REQUEST,
    KIND_CAUSE_VET_ASSIGNED,
    KIND_CAUSE_VET_ENQUEUED,
    KIND_CAUSE_VET_VERDICT,
    KIND_FINDING_FLAGGED,
    KIND_FINDING_VET_ASSIGNED,
    KIND_FINDING_VET_VERDICT,
    KIND_PACKET_CAPTURED,
    KIND_RESULT_RECORDED,
    KIND_VERDICT_RECORDED,
    LogEntry,
    LogVerification,
    TransparencyLog,
    verify_log,
)

__all__ = [
    # clock seam
    "Clock",
    "SystemClock",
    "FixedClock",
    # blob store
    "BlobStore",
    "content_key",
    "canonical_json",
    # claims
    "Claim",
    "ClaimError",
    "ClaimRegistry",
    # attestation / signing seam
    "Attestation",
    "sign_attestation",
    "verify_attestation",
    "attest_candidate",
    "output_hash",
    # transparency log (dual-use)
    "TransparencyLog",
    "verify_log",
    "LogEntry",
    "LogVerification",
    "GENESIS_PREV",
    "KIND_RESULT_RECORDED",
    "KIND_VERDICT_RECORDED",
    "KIND_CAUSE_REQUEST",
    "KIND_CAUSE_DECISION",
    "KIND_PACKET_CAPTURED",
    "KIND_CAPTURE_ROLE_GRANTED",
    "KIND_CAPTURE_ROLE_REVOKED",
    "KIND_CAUSE_VET_ENQUEUED",
    "KIND_CAUSE_VET_ASSIGNED",
    "KIND_CAUSE_VET_VERDICT",
    "KIND_FINDING_FLAGGED",
    "KIND_FINDING_VET_ASSIGNED",
    "KIND_FINDING_VET_VERDICT",
    # reputation persistence
    "LedgerReputation",
    # the thin coordinator
    "Ledger",
]
