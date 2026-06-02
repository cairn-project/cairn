"""Node capability model + Contract-Net self-selection floor check.

Capability-tier non-uniformity: a model-agnostic unit can only
*require* capabilities the weakest enrolled runtime has; ``capability_floor``
makes the tiering explicit. A node declares its ``Capabilities`` and runs a unit
only if it ``meets_floor`` — Contract-Net self-selection. Self-declared
capability is an untrusted claim validated by a calibration probe on join
(``calibration.py``).

 scope: the declaration + the floor check. No probing execution here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..types import CapabilityFloor


@dataclass(frozen=True)
class Capabilities:
    """What a node's runtime offers (self-declared; untrusted until probed).

    ``model_family_tier`` is a coarse capability tier (0 = unknown / local-small);
    it is informational this release — the ``CapabilityFloor`` carries no tier
    field, so the floor check does not gate on it yet.
    """

    context_window: int = 0
    tools: list[str] = field(default_factory=list)
    modalities: list[str] = field(default_factory=list)
    model_family_tier: int = 0

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Capabilities":
        return cls(
            context_window=int(d.get("context_window", 0)),
            tools=list(d.get("tools", [])),
            modalities=list(d.get("modalities", [])),
            model_family_tier=int(d.get("model_family_tier", 0)),
        )


@dataclass(frozen=True)
class CapabilityCheck:
    """Outcome of a self-selection floor check.

    ``qualifies`` is True only when every floor dimension is met. ``reasons``
    names each failed dimension (empty when qualifies).
    """

    qualifies: bool
    reasons: list[str] = field(default_factory=list)


def meets_floor(
    capabilities: Capabilities, floor: CapabilityFloor
) -> CapabilityCheck:
    """Check a node's declared capabilities against a unit's capability floor.

    Floor dimensions (all conjunctive):
      * ``context_window`` — node's window must be >= the floor (if the floor
        sets one).
      * ``tools`` — node must expose every tool the floor requires (superset).
      * ``modalities`` — node must support every modality the floor requires.

    ``model_family_tier`` is not gated this release (floor has no tier field).
    Returns a ``CapabilityCheck`` naming each failed dimension; never raises.
    """
    reasons: list[str] = []

    if floor.context_window is not None:
        if capabilities.context_window < floor.context_window:
            reasons.append(
                "context_window "
                f"{capabilities.context_window} < floor {floor.context_window}"
            )

    missing_tools = [t for t in floor.tools if t not in capabilities.tools]
    if missing_tools:
        reasons.append(f"missing tools: {missing_tools}")

    missing_modalities = [
        m for m in floor.modalities if m not in capabilities.modalities
    ]
    if missing_modalities:
        reasons.append(f"missing modalities: {missing_modalities}")

    return CapabilityCheck(qualifies=not reasons, reasons=reasons)
