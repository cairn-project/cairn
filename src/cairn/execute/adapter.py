"""The model-agnostic adapter seam ("the leverage point").

An ``Adapter`` is the AI-system analog of the BOINC client: it
takes an already-validated ``WorkUnit``, renders the portable payload into a
runtime-native call, runs it, and returns a ``CandidateResult`` stamped with its
provenance. The seam makes **no vendor assumption** — a Claude Code / OpenAI /
ollama / generic-OpenAI-compatible adapter is just a subclass overriding
``produce`` and declaring its real ``capabilities``. Adding a runtime = writing
one adapter, never changing the work-unit format.

This module provides the abstract base plus the offline ``MockAdapter``
(``mock_adapter.py``). Live network adapters are a follow-on increment — none
are implemented here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..types import WorkUnit
from .capability import Capabilities
from .result import CandidateResult


class Adapter(ABC):
    """Abstract model-agnostic adapter.

    Concrete adapters set ``name`` / ``model_family`` / ``version`` and a real
    ``capabilities`` (what their runtime offers — used by the execute flow's
    capability-floor gate), and implement ``produce``. ``produce`` receives a
    unit the caller has ALREADY validated; it must not assume any vendor.
    """

    #: stable adapter identifier (e.g. "mock", "claude-code", "openai-compatible")
    name: str = "abstract"
    #: model family this adapter runs (provenance; "mock" for the reference)
    model_family: str = "unknown"
    #: adapter implementation version (provenance)
    version: str = "0.0.0"

    @property
    @abstractmethod
    def capabilities(self) -> Capabilities:
        """The runtime capabilities this adapter offers (self-declared)."""

    @abstractmethod
    def produce(self, unit: WorkUnit) -> CandidateResult:
        """Render + run the unit on this runtime, returning a CandidateResult.

        Contract:
          * ``unit`` is already schema-valid (the execute flow validates first).
          * The implementation renders the portable payload (``render_payload``)
            into its native call, runs it, and shapes the result to
            ``unit.output_schema``.
          * The returned ``CandidateResult`` is stamped with this adapter's
            provenance (name / model_family / version / produced_at / signature
            placeholder).
        """
