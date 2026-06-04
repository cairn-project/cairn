"""Flagging policy — the generic, mission-neutral seam.

A ``FlagPolicy`` maps a verify-layer ``VerifyVerdict`` to a ``FlagDecision``: an
optional ``AutomatedVerdict`` (an OPAQUE ``flag_label`` + a ``confidence`` in
[0,1]) plus a human-readable reason it did or did not flag. The policy is the
injectable point that keeps the analysis→finding bridge mission-neutral: it
hard-codes NO domain vocabulary. ``flag_label`` is a caller-supplied opaque
string; the threshold is a generic numeric bound.

Why a policy seam, not an inline threshold: a "units of interest"
decision is RUNTIME / per-cause behaviour, not engine identity. The general
engine runs many causes, each able to supply its own flagging bar
without touching the bridge. The only policy shipped here is the generic
``ThresholdFlagPolicy`` — a confidence threshold over an accepted verdict's
output. No scam/sensitive/detection logic exists in this module by construction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ..verify import VerifyVerdict
from ..vetting import AutomatedVerdict


@dataclass(frozen=True)
class FlagDecision:
    """A policy's decision about whether a verdict flags an item of interest.

    ``flagged`` True iff the analyzed item should become a ``Finding``. When True,
    ``automated_verdict`` carries the opaque label + confidence the finding will
    record; when False it is ``None``. ``reason`` always names WHY (for the audit
    trail), so a non-flag is never silent.
    """

    flagged: bool
    automated_verdict: AutomatedVerdict | None
    reason: str

    @staticmethod
    def flag(automated_verdict: AutomatedVerdict, reason: str) -> FlagDecision:
        return FlagDecision(flagged=True, automated_verdict=automated_verdict, reason=reason)

    @staticmethod
    def no_flag(reason: str) -> FlagDecision:
        return FlagDecision(flagged=False, automated_verdict=None, reason=reason)


@runtime_checkable
class FlagPolicy(Protocol):
    """Decide whether a verify verdict flags an item of interest (the seam)."""

    def decide(self, verdict: VerifyVerdict) -> FlagDecision:
        """Return a ``FlagDecision`` for this verdict."""
        ...


def _clamp_unit(x: float) -> float:
    """Clamp a numeric score into the [0, 1] confidence range."""
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


class ThresholdFlagPolicy:
    """Flag an ACCEPTED verdict whose output score meets a threshold (generic).

    The single mission-neutral policy shipped. It flags iff:
      1. the verdict is ACCEPTED (an unaccepted verdict never flags), AND
      2. the accepted output carries a numeric ``score_field`` value, AND
      3. that value is >= ``min_confidence``.

    ``flag_label`` is the OPAQUE label the resulting ``AutomatedVerdict`` records
    (caller-supplied; no domain vocabulary baked in). ``score_field`` defaults to
    ``"confidence"`` but is configurable so a cause can name its own generic score
    field. The recorded confidence is the score clamped to [0, 1].
    """

    def __init__(
        self,
        flag_label: str,
        min_confidence: float,
        *,
        score_field: str = "confidence",
    ) -> None:
        if not flag_label:
            raise ValueError("flag_label must be a non-empty opaque string")
        self.flag_label = flag_label
        self.min_confidence = float(min_confidence)
        self.score_field = score_field

    def decide(self, verdict: VerifyVerdict) -> FlagDecision:
        if not verdict.accepted:
            return FlagDecision.no_flag("verdict not accepted")

        output = verdict.accepted_output
        if not isinstance(output, dict) or self.score_field not in output:
            return FlagDecision.no_flag(f"no {self.score_field!r} in accepted output")

        raw = output[self.score_field]
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            return FlagDecision.no_flag(f"{self.score_field!r} is not numeric")

        score = _clamp_unit(float(raw))
        if score < self.min_confidence:
            return FlagDecision.no_flag(f"score {score} below threshold {self.min_confidence}")

        return FlagDecision.flag(
            AutomatedVerdict(flag_label=self.flag_label, confidence=score),
            reason=f"score {score} >= threshold {self.min_confidence}",
        )
