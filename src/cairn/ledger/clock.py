"""Clock seam — injected time, never a hardwired wall clock.

Claim leases need a notion of "now" to decide whether
a claim has expired. Hardwiring ``time.time()`` would make lease tests
non-deterministic, so every component that needs time takes a ``Clock``. The only
module that touches the real wall clock is ``SystemClock``; everything else asks
the injected clock. ``FixedClock`` is the deterministic test double.
"""

from __future__ import annotations

import time
from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    """Time source: epoch seconds as a float."""

    def now(self) -> float: ...


class SystemClock:
    """Real wall clock — the ONLY place ``time.time()`` is called."""

    def now(self) -> float:
        return time.time()


class FixedClock:
    """Deterministic, advanceable clock for tests (no wall-clock dependence)."""

    def __init__(self, start: float = 0.0) -> None:
        self._t = float(start)

    def now(self) -> float:
        return self._t

    def advance(self, dt: float) -> float:
        """Advance time by ``dt`` seconds; return the new now."""
        self._t += float(dt)
        return self._t

    def set(self, t: float) -> None:
        self._t = float(t)
