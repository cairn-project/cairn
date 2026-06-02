"""Atomic exclusive claim + leases (the one mutual-exclusion point).

A claim is EXCLUSIVE via an atomic ref compare-and-swap — the one place real
mutual exclusion is bought cheaply, with no consensus protocol. On a plain
filesystem the analog of
a git-ref compare-and-swap is an atomic ``O_EXCL`` file create: exactly one
creator wins the race for ``claims/<task_id>``; everyone else gets ``FileExistsError``.
That single OS-level atomic primitive makes double-claim STRUCTURALLY impossible —
no lock server, no consensus round.

Churn handling: claims carry a lease with an expiry. A node that
vanishes lets its claim expire, and an expired claim reopens the unit for re-claim.
Expiry is evaluated against an INJECTED ``Clock`` (no wall-clock hardcoding) so the
lease behaviour is deterministically testable.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from .clock import Clock


class ClaimError(Exception):
    """Raised when a task is already actively (unexpired) claimed."""


@dataclass(frozen=True)
class Claim:
    """An exclusive lease on one task by one node."""

    task_id: str
    node_id: str
    claimed_at: float
    lease_seconds: float
    claim_id: str

    @property
    def expires_at(self) -> float:
        return self.claimed_at + self.lease_seconds

    def is_expired(self, now: float) -> bool:
        return now >= self.expires_at

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "node_id": self.node_id,
            "claimed_at": self.claimed_at,
            "lease_seconds": self.lease_seconds,
            "claim_id": self.claim_id,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Claim":
        return cls(
            task_id=d["task_id"],
            node_id=d["node_id"],
            claimed_at=d["claimed_at"],
            lease_seconds=d["lease_seconds"],
            claim_id=d["claim_id"],
        )


class ClaimRegistry:
    """Filesystem-backed exclusive-claim registry with lease expiry."""

    def __init__(self, root: str | os.PathLike[str], clock: Clock) -> None:
        self._claims = Path(root) / "claims"
        self._claims.mkdir(parents=True, exist_ok=True)
        self._clock = clock

    def _path_for(self, task_id: str) -> Path:
        # Flatten the task id so it is a safe single filename.
        safe = task_id.replace("/", "_")
        return self._claims / safe

    def _write_atomic(self, path: Path, claim: Claim) -> None:
        """Atomic create-exclusive. Raises FileExistsError if the file exists.

        ``O_EXCL`` is the mutual-exclusion primitive: the kernel guarantees at
        most one creator wins. This is the filesystem analog of a git-ref CAS.
        """
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        try:
            os.write(fd, json.dumps(claim.to_dict()).encode("utf-8"))
        finally:
            os.close(fd)

    def _read(self, path: Path) -> Claim | None:
        if not path.exists():
            return None
        try:
            return Claim.from_dict(json.loads(path.read_text()))
        except (json.JSONDecodeError, KeyError):
            return None

    def claim(self, task_id: str, node_id: str, lease_seconds: float) -> Claim:
        """Atomically claim ``task_id`` for ``node_id`` with a lease.

        Succeeds if the task is unclaimed OR its existing claim has EXPIRED.
        Raises ``ClaimError`` if an unexpired claim already exists.
        """
        path = self._path_for(task_id)
        now = self._clock.now()
        new = Claim(
            task_id=task_id,
            node_id=node_id,
            claimed_at=now,
            lease_seconds=float(lease_seconds),
            claim_id=uuid.uuid4().hex,
        )
        try:
            self._write_atomic(path, new)
            return new
        except FileExistsError:
            # Someone holds the ref. Reclaim ONLY if their lease has expired.
            existing = self._read(path)
            if existing is not None and not existing.is_expired(now):
                raise ClaimError(
                    f"task {task_id!r} is actively claimed by "
                    f"{existing.node_id!r} until {existing.expires_at}"
                )
            # Expired (or unreadable) → atomically replace via temp + os.replace.
            tmp = path.parent / (path.name + f".{new.claim_id}.tmp")
            tmp.write_text(json.dumps(new.to_dict()))
            os.replace(tmp, path)
            # Re-read to confirm we are the holder (last-writer-wins on replace).
            confirmed = self._read(path)
            if confirmed is None or confirmed.claim_id != new.claim_id:
                raise ClaimError(
                    f"lost the race to reclaim expired task {task_id!r}"
                )
            return confirmed

    def active_claim(self, task_id: str) -> Claim | None:
        """Return the current UNEXPIRED claim, or None (an expired claim reads
        as None — i.e. the unit is reopened)."""
        existing = self._read(self._path_for(task_id))
        if existing is None:
            return None
        if existing.is_expired(self._clock.now()):
            return None
        return existing

    def release(self, task_id: str, claim_id: str) -> bool:
        """Release a claim early (only the holder, identified by claim_id)."""
        path = self._path_for(task_id)
        existing = self._read(path)
        if existing is not None and existing.claim_id == claim_id:
            path.unlink(missing_ok=True)
            return True
        return False
