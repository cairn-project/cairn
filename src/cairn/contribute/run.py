"""Cause-scoped run loop.

``run_cause`` is the contributor-facing end-to-end driver for ONE approved cause:

  gate (listable + opted-in)  ->  pull the cause's bound work units
   ->  per unit: define_task -> N nodes atomic-claim/run_work_unit/store_result
       -> verify_unit (with the cause's honeypot seed) -> record_verdict
   ->  results + verdicts recorded against the cause on the ledger + translog.

It COMPOSES on the engine (``run_work_unit`` / ``verify_unit`` / ``Ledger``) and
the cause layer (``CauseRegistry`` / ``WorkUnitRegistry`` / ``OptInRegistry``) —
it reimplements none of them. The per-unit body mirrors the pilot runner's REAL
exclusive-claim path (``run_pilot``) but is its own loop, so the pilot's public
behaviour is untouched.

Fail-closed gate: a non-listable cause or a node that has NOT opted in
is REFUSED — never waved through. This is the demand-side of the listing gate.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from ..cause.binding import WorkUnitRegistry
from ..cause.registry import CauseRegistry
from ..execute.flow import run_work_unit
from ..execute.result import CandidateResult
from ..ledger.ledger import Ledger
from ..pilot.adapter import PilotNodeAdapter
from ..pilot.runner import UnitRunResult
from ..types import RedundancyPolicy
from ..verify.aggregate import VerifyVerdict, verify_unit
from ..verify.honeypot import Honeypot
from .optin import OptInRegistry

_LEASE_SECONDS = 60.0


class CauseRunError(Exception):
    """Base error for an invalid cause run."""


class CauseRunRefused(CauseRunError):
    """Raised when the run is refused by the gate (not listable / not opted in)."""


@dataclass(frozen=True)
class CauseRunSummary:
    """Structured summary of a contributor's run of one approved cause."""

    cause_id: str
    node_id: str
    units: list[UnitRunResult]
    reputation: dict[str, float]
    total_honeypot_catches: int
    log_head: str
    result_recorded: int
    verdict_recorded: int

    @property
    def all_accepted(self) -> bool:
        return bool(self.units) and all(u.accepted for u in self.units)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cause_id": self.cause_id,
            "node_id": self.node_id,
            "units": [u.to_dict() for u in self.units],
            "reputation": self.reputation,
            "total_honeypot_catches": self.total_honeypot_catches,
            "log_head": self.log_head,
            "result_recorded": self.result_recorded,
            "verdict_recorded": self.verdict_recorded,
            "all_accepted": self.all_accepted,
        }

    def pretty(self) -> str:
        lines = [
            f"cause: {self.cause_id}",
            f"contributor node: {self.node_id} (opted in)",
            "",
        ]
        for u in self.units:
            verdict = "ACCEPTED" if u.accepted else f"NOT-ACCEPTED ({u.status})"
            fam = ", ".join(u.model_families_in_quorum) or "-"
            lines.append(f"  {u.task_id}")
            lines.append(f"      verdict: {verdict}  | quorum families: {fam}")
            if u.honeypot_catches:
                lines.append(f"      honeypot caught: {', '.join(u.honeypot_catches)}")
        lines.append("")
        lines.append(
            f"units accepted: {sum(u.accepted for u in self.units)}/"
            f"{len(self.units)}  | honeypot catches: "
            f"{self.total_honeypot_catches}"
        )
        lines.append(
            f"transparency log: {self.result_recorded} results recorded, "
            f"{self.verdict_recorded} verdicts recorded"
        )
        lines.append(f"log head: {self.log_head}")
        return "\n".join(lines)


def run_cause(
    cause_id: str,
    *,
    cause_registry: CauseRegistry,
    optin_registry: OptInRegistry,
    work_unit_registry: WorkUnitRegistry,
    ledger: Ledger,
    node_id: str = "contributor",
    node_families: list[str] | None = None,
    bad_family: str | None = None,
) -> CauseRunSummary:
    """Run an approved cause end-to-end for an opted-in contributor node.

    Args:
      cause_id: the cause to work (must be publicly listable).
      cause_registry / optin_registry / work_unit_registry: the cause layer.
      ledger: the real ``Ledger`` (carries its injected clock).
      node_id: the contributor's node id (must have opted in).
      node_families: distinct model-family labels (>=2 so the diversity quorum is
        satisfiable). Defaults to two.
      bad_family: if set, that family runs wrong on the honeypot unit (models a
        faulty/malicious node the honeypot catches).

    Raises ``CauseRunRefused`` if the cause is not listable or the node has not
    opted in. Returns a ``CauseRunSummary``.
    """
    node_families = node_families or ["claude", "gpt"]

    # --- fail-closed gate ---------------------------
    cause = cause_registry.get_cause(cause_id)  # raises on unknown id
    if not cause.is_publicly_listable:
        raise CauseRunRefused(
            f"cannot run cause {cause_id!r}: it is not publicly listable "
            f"(status={cause.status.value})."
        )
    if not optin_registry.is_opted_in(node_id, cause_id):
        raise CauseRunRefused(
            f"node {node_id!r} has not opted into cause {cause_id!r}; "
            "explicit opt-in is required (no silent enlistment)."
        )

    provider = work_unit_registry.provider_for(cause_id)
    units = provider.work_units()
    hp_task_id = provider.honeypot_task_id()
    hp_gold = provider.honeypot_gold()

    unit_results: list[UnitRunResult] = []

    for unit_dict in units:
        task_id = ledger.define_task(unit_dict)

        candidates: list[CandidateResult] = []
        for family in node_families:
            family_node = f"{node_id}-{family}"
            wrong = bad_family is not None and family == bad_family and task_id == hp_task_id
            adapter = PilotNodeAdapter(model_family=family, wrong=wrong)

            # Real atomic exclusive claim, held while this node executes.
            claim = ledger.claim_task(task_id, node_id=family_node, lease_seconds=_LEASE_SECONDS)
            outcome = run_work_unit(unit_dict, adapter)
            assert outcome.candidate is not None
            cand = replace(outcome.candidate, adapter_name=family_node)
            candidates.append(cand)
            ledger.store_result(cand)
            ledger.claims.release(task_id, claim.claim_id)

        policy = RedundancyPolicy.from_dict(unit_dict["redundancy_policy"])
        honeypot = Honeypot(expected_output=hp_gold) if task_id == hp_task_id else None
        verdict: VerifyVerdict = verify_unit(
            candidates,
            policy,
            honeypot=honeypot,
            reputation=ledger.reputation,
            unit_task_id=task_id,
        )
        ledger.record_verdict(task_id, verdict)

        families_in_quorum: list[str] = []
        if verdict.quorum.winning_cluster is not None:
            families_in_quorum = sorted(verdict.quorum.winning_cluster.model_families)
        catches = [s.node_id for s in verdict.honeypot_scores if not s.passed]

        unit_results.append(
            UnitRunResult(
                task_id=task_id,
                status=verdict.status,
                accepted=verdict.accepted,
                model_families_in_quorum=families_in_quorum,
                honeypot_catches=catches,
            )
        )

    reputation = {
        subject: ledger.reputation.score(subject) for subject in ledger.reputation.known_subjects()
    }
    kinds = [e.kind for e in ledger.translog.entries()]

    return CauseRunSummary(
        cause_id=cause_id,
        node_id=node_id,
        units=unit_results,
        reputation=reputation,
        total_honeypot_catches=sum(len(u.honeypot_catches) for u in unit_results),
        log_head=ledger.translog.head_hash(),
        result_recorded=kinds.count("RESULT_RECORDED"),
        verdict_recorded=kinds.count("VERDICT_RECORDED"),
    )
