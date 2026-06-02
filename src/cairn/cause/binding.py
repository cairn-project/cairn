"""Cause ⇄ work-units binding.

A cause owns its work-units. This module gives a *listable* cause a
SOURCE of work units without baking that source into the cause's identity.

Design note — why a registry, not a method on ``Cause``: ``Cause`` is a frozen,
content-addressed record (its id derives from immutable fields). A
units-provider is RUNTIME behaviour, not part of the cause's identity, so it stays
OUT of the content hash. ``WorkUnitProvider`` is the seam; ``WorkUnitRegistry``
maps ``cause_id -> provider`` at runtime. The general engine runs N causes,
each with its own provider.

MISSION-NEUTRAL: the only provider shipped here is ``PilotWorkUnitProvider`` —
the existing benign OSS-license-classification pilot units (``pilot.cause``),
re-stamped onto a bound cause id. No scam/SN/sensitive units exist here.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..pilot.cause import (
    HONEYPOT_SNIPPET_ID,
    build_pilot_units,
    gold_answer,
    honeypot_snippet,
    load_snippets,
)


@runtime_checkable
class WorkUnitProvider(Protocol):
    """A source of work-unit dicts for a single bound cause.

    A provider yields RAW work-unit dicts (the same shape the engine's
    ``validate_work_unit`` / ``run_work_unit`` consume). Every yielded unit's
    ``cause_id`` is the provider's bound ``cause_id`` (the units belong to THIS
    cause). The provider also exposes the cause's honeypot seed (the gold unit +
    gold answer) so the verify layer's L4 honeypot stays wired per cause.
    """

    cause_id: str

    def work_units(self) -> list[dict]:
        """Return this cause's work-unit dicts (already stamped to ``cause_id``)."""
        ...

    def honeypot_task_id(self) -> str:
        """The task_id of this cause's gold-standard honeypot unit."""
        ...

    def honeypot_gold(self) -> dict:
        """The known-correct output for the honeypot unit (L4 seed)."""
        ...


def _restamp(unit: dict, cause_id: str) -> dict:
    """Copy a pilot unit, stamping it onto ``cause_id`` (id namespace + field).

    The pilot's ``task_id`` is ``"<PILOT_CAUSE_ID>::<snippet_id>"``; we rewrite the
    namespace prefix to the bound cause so results/verdicts record against the
    APPROVED cause, not the hard-coded pilot literal. A dict copy — no new spec,
    the unit still validates against the schema.
    """
    out = dict(unit)
    snippet_part = unit["task_id"].split("::", 1)[-1]
    out["cause_id"] = cause_id
    out["task_id"] = f"{cause_id}::{snippet_part}"
    return out


class PilotWorkUnitProvider:
    """Bind the benign pilot's OSS-license units to an arbitrary cause id.

    This is the worked, mission-neutral example: any approved benign cause can be
    backed by the deterministic, offline, honeypot-seeded pilot units. The units
    are re-stamped to the bound cause so the run is recorded against it.
    """

    def __init__(self, cause_id: str) -> None:
        self.cause_id = cause_id
        self._snippets = load_snippets()

    def work_units(self) -> list[dict]:
        return [_restamp(u, self.cause_id) for u in build_pilot_units(self._snippets)]

    def honeypot_task_id(self) -> str:
        return f"{self.cause_id}::{HONEYPOT_SNIPPET_ID}"

    def honeypot_gold(self) -> dict:
        return gold_answer(honeypot_snippet(self._snippets))


class WorkUnitRegistry:
    """Runtime map of ``cause_id -> WorkUnitProvider``."""

    def __init__(self) -> None:
        self._providers: dict[str, WorkUnitProvider] = {}

    def bind(self, provider: WorkUnitProvider) -> None:
        """Register a provider for its ``cause_id``."""
        self._providers[provider.cause_id] = provider

    def bind_pilot(self, cause_id: str) -> PilotWorkUnitProvider:
        """Convenience: bind the benign pilot provider to ``cause_id``."""
        provider = PilotWorkUnitProvider(cause_id)
        self.bind(provider)
        return provider

    def provider_for(self, cause_id: str) -> WorkUnitProvider:
        if cause_id not in self._providers:
            raise KeyError(f"no work-unit provider bound for cause_id: {cause_id}")
        return self._providers[cause_id]

    def is_bound(self, cause_id: str) -> bool:
        return cause_id in self._providers
