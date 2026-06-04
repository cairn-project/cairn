"""ScenarioReferenceNode — the deterministic offline node for the scenario.

A concrete ``Adapter`` (the seam) that produces the CORRECT defect-analysis
answer by applying the same deterministic rule the gold standard uses
(``seed.classify_defect``). Because the answer is computed from the unit inputs
(the public dataset-record metadata) rather than echoed, it is MEANINGFUL: an
honest reference node of a DISTINCT ``model_family`` agrees with the live
``claude`` node on the right answer (diversity quorum satisfiable), and the
honeypot scores both against the gold standard.

This composes the real ``Adapter`` / ``CandidateResult``; it forks nothing. It
makes NO network call and uses NO model — the "inference" is the offline rule.
The ``--offline`` scenario path uses TWO of these (distinct families) so the demo
runs with zero credentials and zero network.
"""

from __future__ import annotations

from ..execute.adapter import Adapter
from ..execute.capability import Capabilities
from ..execute.result import CandidateResult
from ..types import WorkUnit
from .seed import classify_defect

# Deterministic provenance placeholder so output is reproducible (no wall clock).
_PRODUCED_AT = "1970-01-01T00:00:00Z"
_ADAPTER_VERSION = "scenario-reference-0.1.0"


class ScenarioReferenceNode(Adapter):
    """A deterministic node producing the canonical defect classification.

    ``model_family`` distinguishes nodes so the model-diversity quorum is
    satisfiable. The answer is the offline ``classify_defect`` rule applied to the
    unit's ``inline.registration_metadata`` — no model, no network.
    """

    version = _ADAPTER_VERSION

    def __init__(
        self,
        model_family: str = "reference",
        *,
        capabilities: Capabilities | None = None,
    ) -> None:
        self.model_family = model_family
        self.name = model_family
        self._capabilities = capabilities or Capabilities(
            context_window=4096,
            tools=[],
            modalities=["text"],
            model_family_tier=2,
        )

    @property
    def capabilities(self) -> Capabilities:
        return self._capabilities

    def produce(self, unit: WorkUnit) -> CandidateResult:
        inline = unit.inputs.get("inline", {})
        meta = inline.get("registration_metadata", {}) if isinstance(inline, dict) else {}
        answer = classify_defect({"registration_metadata": meta})
        return CandidateResult(
            task_id=unit.task_id,
            output=answer,
            adapter_name=self.name,
            model_family=self.model_family,
            adapter_version=self.version,
            produced_at=_PRODUCED_AT,
        )
