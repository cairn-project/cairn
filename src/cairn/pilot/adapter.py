"""PilotNodeAdapter — a deterministic, offline node for the pilot cause (§32).

A concrete ``Adapter`` (the wave-2 seam) that produces the CORRECT pilot answer
by applying the same deterministic rule the gold standard uses
(``cause.classify_license``). Because the answer is computed from the unit inputs
rather than echoed from the schema, it is MEANINGFUL: honest nodes of DISTINCT
``model_family`` agree on the right answer (diversity quorum satisfiable) and a
``wrong`` node DIVERGES from the gold standard (the honeypot catches it).

This is a NEW adapter subclass — it composes the real ``Adapter`` /
``CandidateResult`` and does NOT fork or modify ``MockAdapter`` (which remains the
schema-echo reference). It makes NO network call and uses NO model: the
"inference" is the offline rule table, the sanctioned deterministic model
stand-in for an offline pilot.
"""

from __future__ import annotations

from typing import Any

from ..execute.adapter import Adapter
from ..execute.capability import Capabilities
from ..execute.result import CandidateResult
from ..types import WorkUnit
from .cause import classify_license

# Deterministic provenance placeholder so output is reproducible (no wall clock).
_PRODUCED_AT = "1970-01-01T00:00:00Z"
_ADAPTER_VERSION = "pilot-node-0.1.0"


class PilotNodeAdapter(Adapter):
    """A simulated pilot node producing the deterministic license classification.

    ``model_family`` distinguishes nodes so the model-diversity quorum is
    satisfiable. ``wrong=True`` makes a deliberately-bad node: it inverts
    ``is_open_license`` and garbles ``license_id`` so the output is still
    schema-VALID but DIVERGES from the gold standard — caught by the honeypot
    regardless of peer agreement (PLAN §3.5 L4).
    """

    version = _ADAPTER_VERSION

    def __init__(
        self,
        model_family: str,
        *,
        wrong: bool = False,
        capabilities: Capabilities | None = None,
    ) -> None:
        self.model_family = model_family
        # Per-node identity (honeypot node_id / reputation subject) = the family
        # label by default; the runner may re-stamp adapter_name with a node id.
        self.name = model_family
        self._wrong = wrong
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
        license_text = unit.inputs.get("inline", {}).get("license_text", "")
        answer = classify_license(license_text)
        if self._wrong:
            answer = self._corrupt(answer)
        return CandidateResult(
            task_id=unit.task_id,
            output=answer,
            adapter_name=self.name,
            model_family=self.model_family,
            adapter_version=self.version,
            produced_at=_PRODUCED_AT,
        )

    @staticmethod
    def _corrupt(answer: dict[str, Any]) -> dict[str, Any]:
        """Produce a schema-valid but gold-divergent (wrong) answer.

        Inverts the boolean and blanks the id to a clearly-wrong sentinel. Still a
        ``{is_open_license: bool, license_id: str}`` object (validates), but it
        does not match the gold standard — the honeypot flags it.
        """
        return {
            "is_open_license": not bool(answer["is_open_license"]),
            "license_id": "WRONG",
        }
