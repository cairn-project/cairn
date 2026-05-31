"""Append-only CT-style transparency log (PLAN §3.6 + REQUIREMENTS Frame 4 +
cause-vetting governance).

A Merkle/hash-CHAINED append-only log. Each entry commits to the prior entry's
hash, so the head hash transitively commits to the ENTIRE history — the
Certificate-Transparency pattern (Merkle log + independent monitor). Stored as
JSONL, one entry per line, so the log is a plain text file that any monitor can
re-derive from raw bytes.

ONE log, TWO uses (made explicit — PLAN §3.6, REQUIREMENTS cause-vetting):
  * DETECTION AUDITABILITY (Frame 4): RESULT_RECORDED / VERDICT_RECORDED entries
    give an immutable record of who/what/when/which-model/what-decision.
  * CAUSE-GOVERNANCE TRANSPARENCY (§3.9): CAUSE_REQUEST / CAUSE_DECISION entries
    record every cause request + decision (approval AND rejection with reason),
    so silent rejection or quiet removal is provably detectable.
Same chain, same ``verify_log``.

The load-bearing guarantee: ``verify_log`` re-derives every hash + chain link
from the on-disk bytes with NO trust in the stored hashes. A flipped byte, an
edited payload, a removed entry, or a reordered entry all break the chain and are
detected. The transparency property is only real because the monitor catches
tampering.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from .blobstore import canonical_json
from .clock import Clock

# Genesis predecessor — 64 hex zeros (no prior entry).
GENESIS_PREV = "0" * 64

# Entry kinds — the dual-use vocabulary (PLAN §3.6).
# Detection auditability (Frame 4):
KIND_RESULT_RECORDED = "RESULT_RECORDED"
KIND_VERDICT_RECORDED = "VERDICT_RECORDED"
# Cause-governance transparency (§3.9 — no silent rejection):
KIND_CAUSE_REQUEST = "CAUSE_REQUEST"
KIND_CAUSE_DECISION = "CAUSE_DECISION"
# Contributor consent (§3.9b — explicit opt-in, never silent enlistment):
KIND_CONSENT_RECORDED = "CONSENT_RECORDED"
KIND_CONSENT_REVOKED = "CONSENT_REVOKED"


def _entry_hash(
    index: int, kind: str, payload: dict, prev_hash: str, recorded_at: float
) -> str:
    """Deterministic hash of an entry's committed fields (incl. the prev link)."""
    material = canonical_json(
        {
            "index": index,
            "kind": kind,
            "payload": payload,
            "prev_hash": prev_hash,
            "recorded_at": recorded_at,
        }
    )
    return hashlib.sha256(material).hexdigest()


@dataclass(frozen=True)
class LogEntry:
    """One append-only log entry, chained to its predecessor."""

    index: int
    kind: str
    payload: dict
    prev_hash: str
    recorded_at: float
    entry_hash: str

    def to_json_line(self) -> str:
        return json.dumps(
            {
                "index": self.index,
                "kind": self.kind,
                "payload": self.payload,
                "prev_hash": self.prev_hash,
                "recorded_at": self.recorded_at,
                "entry_hash": self.entry_hash,
            },
            sort_keys=True,
        )

    @classmethod
    def from_json_line(cls, line: str) -> "LogEntry":
        d = json.loads(line)
        return cls(
            index=d["index"],
            kind=d["kind"],
            payload=d["payload"],
            prev_hash=d["prev_hash"],
            recorded_at=d["recorded_at"],
            entry_hash=d["entry_hash"],
        )


@dataclass(frozen=True)
class LogVerification:
    """Result of an independent monitor verifying the whole chain."""

    ok: bool
    length: int
    head_hash: str
    failed_index: int | None = None
    reason: str = ""


class TransparencyLog:
    """Append-only, hash-chained transparency log over a JSONL file."""

    def __init__(self, path: str | os.PathLike[str], clock: Clock) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._clock = clock

    def entries(self) -> list[LogEntry]:
        if not self._path.exists():
            return []
        out: list[LogEntry] = []
        with open(self._path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    out.append(LogEntry.from_json_line(line))
        return out

    def head_hash(self) -> str:
        entries = self.entries()
        return entries[-1].entry_hash if entries else GENESIS_PREV

    def append(self, kind: str, payload: dict) -> LogEntry:
        """Append a new entry chained to the current head. Append-only."""
        existing = self.entries()
        index = len(existing)
        prev_hash = existing[-1].entry_hash if existing else GENESIS_PREV
        recorded_at = self._clock.now()
        entry_hash = _entry_hash(index, kind, payload, prev_hash, recorded_at)
        entry = LogEntry(
            index=index,
            kind=kind,
            payload=payload,
            prev_hash=prev_hash,
            recorded_at=recorded_at,
            entry_hash=entry_hash,
        )
        with open(self._path, "a", encoding="utf-8") as fh:
            fh.write(entry.to_json_line() + "\n")
        return entry


def verify_log(path: str | os.PathLike[str]) -> LogVerification:
    """Independently verify the chain from raw on-disk bytes.

    Re-derives every entry hash and every chain link WITHOUT trusting the stored
    hashes. Detects: a flipped/edited byte (recomputed hash diverges), a removed
    entry (index gap + broken prev link), and a reordered entry (prev link
    mismatch). Returns ``ok=False`` with the first failing index.
    """
    p = Path(path)
    if not p.exists():
        return LogVerification(ok=True, length=0, head_hash=GENESIS_PREV)

    expected_prev = GENESIS_PREV
    length = 0
    head = GENESIS_PREV
    with open(p, "r", encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh):
            raw = raw.strip()
            if not raw:
                continue
            try:
                entry = LogEntry.from_json_line(raw)
            except (json.JSONDecodeError, KeyError):
                return LogVerification(
                    ok=False,
                    length=length,
                    head_hash=head,
                    failed_index=lineno,
                    reason="unparseable entry line",
                )

            # 1. positional integrity — index must be sequential (catches removal/reorder).
            if entry.index != lineno:
                return LogVerification(
                    ok=False,
                    length=length,
                    head_hash=head,
                    failed_index=lineno,
                    reason=f"index {entry.index} != position {lineno} "
                    "(removed or reordered entry)",
                )

            # 2. chain integrity — prev_hash must match the prior entry's hash.
            if entry.prev_hash != expected_prev:
                return LogVerification(
                    ok=False,
                    length=length,
                    head_hash=head,
                    failed_index=entry.index,
                    reason="prev_hash does not match prior entry "
                    "(broken chain / removed / reordered)",
                )

            # 3. self integrity — recompute the entry hash from its committed fields.
            recomputed = _entry_hash(
                entry.index,
                entry.kind,
                entry.payload,
                entry.prev_hash,
                entry.recorded_at,
            )
            if recomputed != entry.entry_hash:
                return LogVerification(
                    ok=False,
                    length=length,
                    head_hash=head,
                    failed_index=entry.index,
                    reason="recomputed entry hash differs (tampered payload)",
                )

            expected_prev = entry.entry_hash
            head = entry.entry_hash
            length += 1

    return LogVerification(ok=True, length=length, head_hash=head)
