"""cairn.execute — the model-agnostic EXECUTE / ADAPTER layer (wave 2).

Sits directly on top of the wave-1 work-unit + acceptance-contract spec. Ships:
the abstract ``Adapter`` seam (PLAN §3.3 "the leverage point"), a deterministic
offline ``MockAdapter``, the portable-payload ``render_payload`` (research 02
A.2), the ``Capabilities`` + ``meets_floor`` self-selection model, a
calibration-probe stub (research 01 §5.4), and the ``run_work_unit`` execute flow
that wires the wave-1 ``validate_work_unit`` + ``evaluate_acceptance``.

Wave 6 adds the FIRST live adapter, ``ClaudeCliAdapter`` (a real Claude model via
the isolated subscription ``claude -p`` CLI), composing on this same seam.

DEFERRED (later waves): other live adapters (OpenAI / ollama / generic), the
verify/quorum layer (PLAN §3.5), real attestation/signing (PLAN §3.6), the real
adversarial calibration probe, and pull/submit transport.
"""

from __future__ import annotations

from .adapter import Adapter
from .calibration import (
    KNOWN_MODALITIES,
    CalibrationProbe,
    CalibrationResult,
    TrivialCalibrationProbe,
)
from .capability import Capabilities, CapabilityCheck, meets_floor
from .flow import (
    STATUS_ACCEPTED,
    STATUS_ACCEPTED_ACCEPTANCE_FAILED,
    STATUS_REJECTED_CALIBRATION,
    STATUS_REJECTED_CAPABILITY,
    STATUS_REJECTED_VALIDATION,
    ExecuteOutcome,
    run_work_unit,
)
from .claude_adapter import ClaudeCliAdapter, ClaudeCliError
from .mock_adapter import MockAdapter
from .render import RenderedPayload, render_payload
from .result import CandidateResult

__all__ = [
    # seam + reference adapter
    "Adapter",
    "ClaudeCliAdapter",  # wave 6 — first live adapter
    "ClaudeCliError",
    "MockAdapter",
    # render
    "render_payload",
    "RenderedPayload",
    # result
    "CandidateResult",
    # capability
    "Capabilities",
    "CapabilityCheck",
    "meets_floor",
    # calibration
    "CalibrationProbe",
    "CalibrationResult",
    "TrivialCalibrationProbe",
    "KNOWN_MODALITIES",
    # flow
    "run_work_unit",
    "ExecuteOutcome",
    "STATUS_ACCEPTED",
    "STATUS_ACCEPTED_ACCEPTANCE_FAILED",
    "STATUS_REJECTED_VALIDATION",
    "STATUS_REJECTED_CALIBRATION",
    "STATUS_REJECTED_CAPABILITY",
]
