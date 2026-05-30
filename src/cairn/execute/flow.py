"""Execute flow — validate -> probe -> capability-gate -> produce -> accept.

``run_work_unit`` is the wave-2 entry point. It composes the wave-1 functions
(``validate_work_unit``, ``evaluate_acceptance``) with the wave-2 adapter seam +
capability model. This is one node's local execution of a single work unit; the
cross-node verify/quorum layer (PLAN §3.5) that aggregates N CandidateResults is
the NEXT wave and sits ABOVE this.

Pipeline (research 02 A.2 steps 2/4 + PLAN §3.3 self-selection):
  1. validate the raw unit dict against the spec (wave-1)            [fail-closed]
  2. (optional) calibration probe of the adapter's self-declared caps [fail-closed]
  3. capability-floor self-selection gate                            [fail-closed]
  4. adapter.produce -> CandidateResult
  5. evaluate_acceptance — the cheap client-side filter (wave-1)
  6. return an ExecuteOutcome

No network, no signing, no quorum here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from ..acceptance import AcceptanceResult, evaluate_acceptance
from ..types import WorkUnit
from ..validate import ValidationResult, validate_work_unit
from .adapter import Adapter
from .calibration import CalibrationProbe, CalibrationResult
from .capability import CapabilityCheck, meets_floor
from .result import CandidateResult

# Outcome status values.
STATUS_ACCEPTED = "accepted"
STATUS_ACCEPTED_ACCEPTANCE_FAILED = "accepted_acceptance_failed"
STATUS_REJECTED_VALIDATION = "rejected_validation"
STATUS_REJECTED_CALIBRATION = "rejected_calibration"
STATUS_REJECTED_CAPABILITY = "rejected_capability"


@dataclass(frozen=True)
class ExecuteOutcome:
    """Result of running one work unit on one adapter (one node, one attempt).

    ``status`` (one of the STATUS_* constants):
      * ``accepted`` — produced + passed the client-side acceptance filter.
      * ``accepted_acceptance_failed`` — produced, but the output failed the
        acceptance contract (the candidate exists; the cheap filter rejected it).
      * ``rejected_validation`` — the unit dict did not validate (nothing run).
      * ``rejected_calibration`` — the adapter's declared capabilities failed the
        calibration probe (nothing run).
      * ``rejected_capability`` — the adapter does not meet the unit's floor.
    """

    status: str
    validation: ValidationResult
    candidate: Optional[CandidateResult] = None
    acceptance: Optional[AcceptanceResult] = None
    capability_check: Optional[CapabilityCheck] = None
    calibration: Optional[CalibrationResult] = None
    detail: str = ""


def run_work_unit(
    unit_dict: dict[str, Any],
    adapter: Adapter,
    probe: Optional[CalibrationProbe] = None,
) -> ExecuteOutcome:
    """Run one work unit on one adapter, returning an ExecuteOutcome.

    ``unit_dict`` is a RAW work-unit dict (not yet validated). ``adapter`` is any
    concrete ``Adapter`` (the ``MockAdapter`` for offline tests). ``probe`` is an
    optional calibration probe of the adapter's self-declared capabilities; when
    omitted, calibration is skipped (the seam is in place for the real probe).

    Composes wave-1 ``validate_work_unit`` + ``evaluate_acceptance`` — does not
    re-implement either. Fails closed at every gate.
    """
    # 1. validate (wave-1)
    validation = validate_work_unit(unit_dict)
    if not validation.valid:
        return ExecuteOutcome(
            status=STATUS_REJECTED_VALIDATION,
            validation=validation,
            detail="work unit failed schema validation",
        )

    unit = WorkUnit.from_dict(unit_dict)

    # 2. optional calibration probe of self-declared capabilities (research 01 §5.4)
    calibration: Optional[CalibrationResult] = None
    if probe is not None:
        calibration = probe.verify(adapter.capabilities)
        if not calibration.passed:
            return ExecuteOutcome(
                status=STATUS_REJECTED_CALIBRATION,
                validation=validation,
                calibration=calibration,
                detail="adapter capabilities failed calibration: "
                + "; ".join(calibration.reasons),
            )

    # 3. capability-floor self-selection gate (PLAN §3.3)
    capability_check = meets_floor(adapter.capabilities, unit.capability_floor)
    if not capability_check.qualifies:
        return ExecuteOutcome(
            status=STATUS_REJECTED_CAPABILITY,
            validation=validation,
            calibration=calibration,
            capability_check=capability_check,
            detail="adapter does not meet capability floor: "
            + "; ".join(capability_check.reasons),
        )

    # 4. produce the candidate result
    candidate = adapter.produce(unit)

    # 5. client-side acceptance filter (wave-1)
    acceptance = evaluate_acceptance(candidate.output, unit.acceptance_contract)

    status = STATUS_ACCEPTED if acceptance.passed else STATUS_ACCEPTED_ACCEPTANCE_FAILED
    detail = (
        "produced + passed acceptance"
        if acceptance.passed
        else "produced but failed client-side acceptance filter"
    )
    return ExecuteOutcome(
        status=status,
        validation=validation,
        candidate=candidate,
        acceptance=acceptance,
        capability_check=capability_check,
        calibration=calibration,
        detail=detail,
    )
