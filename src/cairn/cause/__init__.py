"""cairn.cause — the CAUSE layer.

The cause data model + registry + public list + request intake + the gated-listing
gate, composed ON the engine's ledger + transparency log (it reuses
``TransparencyLog`` / ``BlobStore`` / ``verify_log`` — it forks nothing). A cause is
a generic first-class object (MISSION-NEUTRAL); the scam/SN-specific detection
logic, vetting UI, distribution ramps, and action engine are LATER waves.

  model.py     the Cause first-class object + CauseStatus + 5-frame assessment
  gate.py      the five-frame gate-check STRUCTURE enforcer
  registry.py  CauseRegistry — intake (CAUSE_REQUEST) + gated decision
               (CAUSE_DECISION, approval OR rejection WITH reason) + public list
  binding.py   cause ⇄ work-units binding (WorkUnitProvider + WorkUnitRegistry),
               the seam that gives a *listable* cause a source of work units
"""

from __future__ import annotations

from .binding import (
    PilotWorkUnitProvider,
    WorkUnitProvider,
    WorkUnitRegistry,
)
from .gate import GateCheckResult, five_frame_gate_check
from .model import (
    FRAME_KEYS,
    Cause,
    CauseStatus,
    FiveFrameAssessment,
    FrameVerdict,
)
from .registry import CauseError, CauseRegistry

__all__ = [
    # model
    "Cause",
    "CauseStatus",
    "FiveFrameAssessment",
    "FrameVerdict",
    "FRAME_KEYS",
    # gate
    "five_frame_gate_check",
    "GateCheckResult",
    # registry
    "CauseRegistry",
    "CauseError",
    # binding
    "WorkUnitProvider",
    "WorkUnitRegistry",
    "PilotWorkUnitProvider",
]
