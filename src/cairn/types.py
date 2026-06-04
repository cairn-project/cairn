"""Pydantic-free dataclasses for the work-unit + acceptance-contract spec.

These mirror the canonical JSON Schema (``spec/work_unit.schema.json``) and the
human SPEC (``spec/SPEC.md``). They are convenience containers for typed access;
the JSON Schema remains authoritative for validation (see ``validate.py``).

 scope: the work-unit shape and the
acceptance-predicate shapes. No adapter, no verify-quorum, no ledger logic —
those are later phases and are not modeled here beyond the fields the spec
already carries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CapabilityFloor:
    """Minimum capability a unit needs."""

    context_window: int | None = None
    tools: list[str] = field(default_factory=list)
    modalities: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CapabilityFloor:
        return cls(
            context_window=d.get("context_window"),
            tools=list(d.get("tools", [])),
            modalities=list(d.get("modalities", [])),
        )


@dataclass(frozen=True)
class RedundancyPolicy:
    """Redundancy + quorum config consumed by the deferred verify layer."""

    target_nresults: int
    min_quorum: int
    model_diversity: int = 0

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> RedundancyPolicy:
        return cls(
            target_nresults=d["target_nresults"],
            min_quorum=d["min_quorum"],
            model_diversity=d.get("model_diversity", 0),
        )


@dataclass(frozen=True)
class ProvenanceRequirements:
    """Per-result attestation flags feeding the deferred audit ledger."""

    model_family: bool = False
    signed_result: bool = False
    trace: bool = False

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ProvenanceRequirements:
        return cls(
            model_family=d.get("model_family", False),
            signed_result=d.get("signed_result", False),
            trace=d.get("trace", False),
        )


@dataclass(frozen=True)
class AcceptancePredicate:
    """A single machine-checkable acceptance predicate.

    ``kind`` selects the checker; ``params`` carries the kind-specific
    parameters (see SPEC.md predicate table). Kept as a generic container so new
    predicate kinds do not require a new dataclass.
    """

    kind: str
    params: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AcceptancePredicate:
        params = {k: v for k, v in d.items() if k != "kind"}
        return cls(kind=d["kind"], params=params)


@dataclass(frozen=True)
class AcceptanceContract:
    """The conjunctive set of predicates a valid result must satisfy."""

    predicates: list[AcceptancePredicate] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AcceptanceContract:
        return cls(predicates=[AcceptancePredicate.from_dict(p) for p in d.get("predicates", [])])


@dataclass(frozen=True)
class Lease:
    duration_seconds: int

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Lease:
        return cls(duration_seconds=d["duration_seconds"])


@dataclass(frozen=True)
class WorkUnit:
    """A model-agnostic work unit.

    The portable payload is ``objective + inputs + output_schema +
    acceptance_contract``; everything model-specific is synthesized by an
    adapter (later phase).
    """

    schema_version: str
    task_id: str
    cause_id: str
    objective: str
    inputs: dict[str, Any]
    output_schema: dict[str, Any]
    acceptance_contract: AcceptanceContract
    capability_floor: CapabilityFloor
    redundancy_policy: RedundancyPolicy
    provenance_requirements: ProvenanceRequirements
    deadline: str | None = None
    lease: Lease | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> WorkUnit:
        """Build a WorkUnit from a raw dict.

        This does NOT validate against the schema — call
        ``validate.validate_work_unit`` first. ``from_dict`` assumes a
        schema-valid dict and provides typed access.
        """
        return cls(
            schema_version=d["schema_version"],
            task_id=d["task_id"],
            cause_id=d["cause_id"],
            objective=d["objective"],
            inputs=d["inputs"],
            output_schema=d["output_schema"],
            acceptance_contract=AcceptanceContract.from_dict(d["acceptance_contract"]),
            capability_floor=CapabilityFloor.from_dict(d["capability_floor"]),
            redundancy_policy=RedundancyPolicy.from_dict(d["redundancy_policy"]),
            provenance_requirements=ProvenanceRequirements.from_dict(d["provenance_requirements"]),
            deadline=d.get("deadline"),
            lease=Lease.from_dict(d["lease"]) if "lease" in d else None,
        )
