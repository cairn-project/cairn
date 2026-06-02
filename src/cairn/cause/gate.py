"""The five-frame gate-check — STRUCTURE enforcer.

A structured 5-frame gate-check: a checklist the decider must pass. The human
judgment is the decider's, but the STRUCTURE is enforced.

This module does NOT make the human judgment. It enforces that the decider
addressed ALL FIVE named frames before a decision
is recordable. A gate-check that skips a frame is INCOMPLETE, and an incomplete
gate-check cannot back an approval (the registry enforces that at decision time).
The decider's per-frame pass/fail verdicts are recorded for the transparency log.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from .model import FRAME_KEYS


@dataclass(frozen=True)
class GateCheckResult:
    """Outcome of the structured five-frame gate-check.

    ``complete`` is the load-bearing flag: it is true ONLY when every one of the
    five named frames was addressed by the decider (no silent skip). The registry
    refuses to record a decision on an incomplete gate-check.
    """

    all_frames_present: bool
    frames_passed: list[str] = field(default_factory=list)
    frames_failed: list[str] = field(default_factory=list)
    missing_frames: list[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return self.all_frames_present

    @property
    def all_passed(self) -> bool:
        """Every addressed frame passed (and all frames were addressed)."""
        return self.all_frames_present and not self.frames_failed


def five_frame_gate_check(decider_verdicts: Mapping[str, bool]) -> GateCheckResult:
    """Enforce the five-frame checklist structure over the decider's verdicts.

    ``decider_verdicts`` maps each frame key → the decider's pass(True)/fail(False)
    verdict for that frame. The STRUCTURE (all five frames addressed) is enforced
    here; the human judgment encoded in each bool is the decider's own.
    """
    present = set(decider_verdicts.keys()) & set(FRAME_KEYS)
    missing = [k for k in FRAME_KEYS if k not in present]
    passed = sorted(k for k in present if decider_verdicts[k])
    failed = sorted(k for k in present if not decider_verdicts[k])
    return GateCheckResult(
        all_frames_present=not missing,
        frames_passed=passed,
        frames_failed=failed,
        missing_frames=missing,
    )
