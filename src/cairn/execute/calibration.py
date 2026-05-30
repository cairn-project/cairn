"""Calibration-probe stub — validate a node's self-declared capabilities on join.

research 01 §5.4 / PLAN §3.3 F2: "self-declared capability is itself an untrusted
claim — does it get verified (a calibration probe task on join)?" The answer is
yes, but the full adversarial probe (a real probe work-unit a joining node must
execute and pass, so it cannot lie about a capability it does not actually have)
is DEFERRED.

Wave 2 ships only the SHAPE: an abstract ``CalibrationProbe`` interface and a
trivial implementation that checks the declared ``Capabilities`` are internally
well-formed (non-negative context window, recognized modalities). This is a
necessary-not-sufficient gate — it catches obviously-malformed declarations; it
does NOT yet catch an honest-looking lie. The execute flow accepts an optional
probe so the seam is in place for the real probe to slot in later.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from .capability import Capabilities

# Modalities the protocol recognizes this wave. A declared modality outside this
# set is treated as malformed by the trivial probe (open to extension later).
KNOWN_MODALITIES = frozenset({"text", "image", "audio", "video", "code"})


@dataclass(frozen=True)
class CalibrationResult:
    """Outcome of a calibration probe.

    ``passed`` False means the declaration is rejected (and the node should not
    be admitted / should not run the unit). ``reasons`` names each problem.
    """

    passed: bool
    reasons: list[str] = field(default_factory=list)


class CalibrationProbe(ABC):
    """Interface for a join-time capability-calibration probe.

    A real probe (deferred) issues an actual probe work-unit to the runtime and
    confirms the produced result is consistent with the self-declared
    ``Capabilities`` (e.g. a long-context probe only the claimed window can pass).
    Wave 2 defines the seam; ``TrivialCalibrationProbe`` is the placeholder.
    """

    @abstractmethod
    def verify(self, capabilities: Capabilities) -> CalibrationResult:
        """Validate self-declared capabilities; return a CalibrationResult."""


class TrivialCalibrationProbe(CalibrationProbe):
    """Well-formedness-only probe (necessary, not sufficient).

    Checks the declaration is internally sane:
      * ``context_window`` >= 0,
      * ``model_family_tier`` >= 0,
      * every declared modality is in ``KNOWN_MODALITIES``.

    It does NOT execute a probe task — it cannot catch an honest-looking lie. The
    real adversarial probe is deferred (research 01 §5.4).
    """

    def verify(self, capabilities: Capabilities) -> CalibrationResult:
        reasons: list[str] = []
        if capabilities.context_window < 0:
            reasons.append(
                f"context_window {capabilities.context_window} is negative"
            )
        if capabilities.model_family_tier < 0:
            reasons.append(
                f"model_family_tier {capabilities.model_family_tier} is negative"
            )
        unknown = [m for m in capabilities.modalities if m not in KNOWN_MODALITIES]
        if unknown:
            reasons.append(f"unknown modalities: {unknown}")
        return CalibrationResult(passed=not reasons, reasons=reasons)
