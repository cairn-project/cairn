"""Ledger-backed reputation persistence — persistence belongs to the ledger layer.

The verify layer ships ``InMemoryReputation`` and defers persistence to this
layer. ``LedgerReputation`` keeps the ``Reputation`` interface unchanged
(``score`` / ``apply`` / ``apply_all``) and reuses the bounding math
(neutral prior, [0,1] bounds, per-event weights) by subclassing
``InMemoryReputation`` — it does NOT fork the scoring logic. It adds durability:
every applied ``ReputationDelta`` is appended to an on-disk JSONL log, and a fresh
instance ``replay()``s that log to rebuild identical scores.

This replaces the in-memory-only store with a ledger-backed one while preserving
the earned-not-asserted semantics of.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from ..verify.reputation import (
    NEUTRAL_PRIOR,
    InMemoryReputation,
    ReputationDelta,
)


class LedgerReputation(InMemoryReputation):
    """Durable reputation: math, persisted as an append-only delta log."""

    def __init__(
        self,
        path: str | os.PathLike[str],
        prior: float = NEUTRAL_PRIOR,
    ) -> None:
        super().__init__(prior=prior)
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self.replay()

    def replay(self) -> None:
        """Rebuild in-memory scores from the persisted delta log."""
        # Reset, then fold every persisted delta through the math.
        self._scores = {}
        if not self._path.exists():
            return
        with open(self._path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                delta = ReputationDelta(
                    subject=d["subject"],
                    event=d["event"],
                    weight=d.get("weight", 0.0),
                )
                # Fold WITHOUT re-persisting (super().apply, not self.apply).
                super().apply(delta)

    def apply(self, delta: ReputationDelta) -> float:
        """Apply one delta: fold in-memory (math) AND append durably."""
        new_score = super().apply(delta)
        with open(self._path, "a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {
                        "subject": delta.subject,
                        "event": delta.event,
                        "weight": delta.weight,
                    },
                    sort_keys=True,
                )
                + "\n"
            )
        return new_score
