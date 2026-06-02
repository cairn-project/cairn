"""The analysis layer — the bridge from a verify verdict to a flagged finding.

This package is the missing seam between the engine's detect/analyze half
(execute → verify → verdict) and its vet/route half (Finding → human Gate-2 →
dispatch). It produces a ``Finding`` from a real ``VerifyVerdict`` over a captured
``ExaminationPacket``, via a generic, injectable ``FlagPolicy`` that hard-codes no
domain vocabulary (mission-neutral).

Public surface:
  * ``FlagPolicy`` — the decision protocol (the seam).
  * ``ThresholdFlagPolicy`` — the only shipped policy (generic confidence bar).
  * ``FlagDecision`` — a policy's flag/no-flag result + reason.
  * ``flag_from_verdict`` — the bridge driver: decide (policy) + record (queue).
"""

from __future__ import annotations

from .bridge import flag_from_verdict
from .policy import FlagDecision, FlagPolicy, ThresholdFlagPolicy

__all__ = [
    "FlagPolicy",
    "ThresholdFlagPolicy",
    "FlagDecision",
    "flag_from_verdict",
]
