"""cairn — distributed cause-coordination engine (Layer A).

The full Layer-A engine is built:
the work-unit + acceptance-contract spec + validation (the A<->B stable
interface); the model-agnostic execute / adapter seam; the verify / trust layer
that aggregates N candidate results into a trust verdict; the ledger /
transparency log; the cause layer + contributor opt-in; the inert capture
abstraction; the human-in-the-loop two-gate vetting; the public-transparency
surfaces; and the routing / action spine. Real-world capture (headless browser /
network egress) and real external-recipient delivery are deliberately deferred to
separate, independently security-reviewed phases.
"""

from __future__ import annotations

from .acceptance import (
    AcceptanceResult,
    PredicateResult,
    UnknownPredicateError,
    evaluate_acceptance,
)
from .execute import (
    Adapter,
    CandidateResult,
    Capabilities,
    CapabilityCheck,
    ExecuteOutcome,
    MockAdapter,
    RenderedPayload,
    TrivialCalibrationProbe,
    meets_floor,
    render_payload,
    run_work_unit,
)
from .fixtures import list_fixtures, load_fixture
from .public import (
    PublicCauseView,
    PublicLogEntryView,
    PublicTransparency,
    PublicVettedOutcomeView,
    list_public_log,
    list_published_causes,
    list_vetted_outcomes,
    public_verify_log,
)
from .types import (
    AcceptanceContract,
    AcceptancePredicate,
    CapabilityFloor,
    Lease,
    ProvenanceRequirements,
    RedundancyPolicy,
    WorkUnit,
)
from .validate import SPEC_MAJOR, ValidationResult, validate_work_unit
from .verify import (
    AgreementFunction,
    Cluster,
    Honeypot,
    HoneypotScore,
    InMemoryReputation,
    Judge,
    MockJudge,
    ObjectiveAgreement,
    QuorumResult,
    Reputation,
    ReputationDelta,
    SubjectiveAgreement,
    TiebreakDecision,
    VerifyVerdict,
    decide_quorum,
    decide_tiebreak,
    verify_unit,
)

__version__ = "0.3.2"
# Spec version of the work-unit + acceptance-contract interface (SPEC.md).
SPEC_VERSION = "1.0.0"

__all__ = [
    "__version__",
    "SPEC_VERSION",
    "SPEC_MAJOR",
    # spec / validation
    "validate_work_unit",
    "ValidationResult",
    "evaluate_acceptance",
    "AcceptanceResult",
    "PredicateResult",
    "UnknownPredicateError",
    # types
    "WorkUnit",
    "AcceptanceContract",
    "AcceptancePredicate",
    "CapabilityFloor",
    "RedundancyPolicy",
    "ProvenanceRequirements",
    "Lease",
    # fixtures
    "load_fixture",
    "list_fixtures",
    # execute / adapter layer
    "Adapter",
    "MockAdapter",
    "render_payload",
    "RenderedPayload",
    "CandidateResult",
    "Capabilities",
    "CapabilityCheck",
    "meets_floor",
    "TrivialCalibrationProbe",
    "run_work_unit",
    "ExecuteOutcome",
    # verify / trust layer
    "verify_unit",
    "VerifyVerdict",
    "AgreementFunction",
    "ObjectiveAgreement",
    "SubjectiveAgreement",
    "Cluster",
    "Judge",
    "MockJudge",
    "decide_quorum",
    "QuorumResult",
    "Honeypot",
    "HoneypotScore",
    "Reputation",
    "InMemoryReputation",
    "ReputationDelta",
    "decide_tiebreak",
    "TiebreakDecision",
    # public transparency read-surfaces (read-only projection)
    "PublicTransparency",
    "PublicCauseView",
    "PublicVettedOutcomeView",
    "PublicLogEntryView",
    "list_published_causes",
    "list_vetted_outcomes",
    "public_verify_log",
    "list_public_log",
]
