"""run_pilot — the end-to-end runner driving the REAL backbone (§33).

Wires waves 1..4 over the benign pilot cause, fully offline:

  define_task (ledger) -> claim_task (atomic exclusive) -> run_work_unit
  (PilotNodeAdapter, distinct families) -> store_result (blob + attestation +
  RESULT_RECORDED) -> verify_unit (with a Honeypot on the seeded unit) ->
  record_verdict (VERDICT_RECORDED) -> everything on the real TransparencyLog.

Returns a structured ``PilotRunSummary`` (per-unit verdicts, model-diversity in
quorum, honeypot catches, reputation deltas, the transparency-log head hash).

The ledger / verify layers are the REAL ones — no mocks. The only stand-in is
``PilotNodeAdapter`` (the sanctioned offline model stand-in via the Adapter seam).

Claim modeling: N nodes redundantly EXECUTE one unit (redundancy is the verify
layer's point). The wave-4 claim is EXCLUSIVE per task_id, so each node claims,
executes, then releases before the next claims — exercising the REAL atomic-claim
+ release path rather than bypassing it.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Optional

from ..execute.flow import run_work_unit
from ..execute.result import CandidateResult
from ..ledger.ledger import Ledger
from ..types import RedundancyPolicy
from ..verify.aggregate import VerifyVerdict, verify_unit
from ..verify.honeypot import Honeypot
from .adapter import PilotNodeAdapter
from .cause import (
    PILOT_CAUSE_ID,
    build_pilot_units,
    gold_answer,
    honeypot_snippet,
    load_snippets,
    unit_task_id,
)

_LEASE_SECONDS = 60.0


@dataclass(frozen=True)
class UnitRunResult:
    """Per-unit outcome of the pilot run."""

    task_id: str
    status: str
    accepted: bool
    model_families_in_quorum: list[str] = field(default_factory=list)
    honeypot_catches: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status,
            "accepted": self.accepted,
            "model_families_in_quorum": self.model_families_in_quorum,
            "honeypot_catches": self.honeypot_catches,
        }


@dataclass(frozen=True)
class PilotRunSummary:
    """Structured summary of a full pilot run over the real backbone."""

    cause_id: str
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
            "units": [u.to_dict() for u in self.units],
            "reputation": self.reputation,
            "total_honeypot_catches": self.total_honeypot_catches,
            "log_head": self.log_head,
            "result_recorded": self.result_recorded,
            "verdict_recorded": self.verdict_recorded,
            "all_accepted": self.all_accepted,
        }

    def pretty(self) -> str:
        lines = [f"pilot cause: {self.cause_id}", ""]
        for u in self.units:
            verdict = "ACCEPTED" if u.accepted else f"NOT-ACCEPTED ({u.status})"
            fam = ", ".join(u.model_families_in_quorum) or "-"
            lines.append(f"  {u.task_id}")
            lines.append(f"      verdict: {verdict}  | quorum families: {fam}")
            if u.honeypot_catches:
                lines.append(
                    f"      honeypot caught: {', '.join(u.honeypot_catches)}"
                )
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


def run_pilot(
    ledger: Ledger,
    *,
    node_families: Optional[list[str]] = None,
    bad_family: Optional[str] = None,
) -> PilotRunSummary:
    """Run the benign pilot cause end-to-end over a real ``Ledger``.

    Args:
      ledger: a real, fresh ``Ledger`` (carries its injected ``Clock``).
      node_families: distinct model-family labels to simulate (>= 2 so the
        diversity quorum is satisfiable). Defaults to two families.
      bad_family: if set, that family runs ``wrong=True`` ON THE HONEYPOT UNIT,
        modeling a malicious/faulty node the honeypot catches.

    Returns a ``PilotRunSummary``.
    """
    node_families = node_families or ["claude", "gpt"]

    snippets = load_snippets()
    units = build_pilot_units(snippets)
    hp_task_id = unit_task_id(honeypot_snippet(snippets)["snippet_id"])
    hp_gold = gold_answer(honeypot_snippet(snippets))

    unit_results: list[UnitRunResult] = []
    result_recorded = 0

    for unit_dict, snippet in zip(units, snippets):
        task_id = ledger.define_task(unit_dict)

        candidates: list[CandidateResult] = []
        for family in node_families:
            node_id = f"node-{family}"
            wrong = (
                bad_family is not None
                and family == bad_family
                and task_id == hp_task_id
            )
            adapter = PilotNodeAdapter(model_family=family, wrong=wrong)

            # Real atomic exclusive claim, held while this node executes.
            claim = ledger.claim_task(task_id, node_id=node_id, lease_seconds=_LEASE_SECONDS)
            outcome = run_work_unit(unit_dict, adapter)
            assert outcome.candidate is not None  # honest+wrong both produce
            # Stamp the per-node identity onto the candidate (node_id == subject).
            cand = replace(outcome.candidate, adapter_name=node_id)
            candidates.append(cand)
            ledger.store_result(cand)
            result_recorded += 1
            # Release the exclusive claim so the next node can claim the unit.
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
        subject: ledger.reputation.score(subject)
        for subject in ledger.reputation.known_subjects()
    }
    kinds = [e.kind for e in ledger.translog.entries()]

    return PilotRunSummary(
        cause_id=PILOT_CAUSE_ID,
        units=unit_results,
        reputation=reputation,
        total_honeypot_catches=sum(len(u.honeypot_catches) for u in unit_results),
        log_head=ledger.translog.head_hash(),
        result_recorded=kinds.count("RESULT_RECORDED"),
        verdict_recorded=kinds.count("VERDICT_RECORDED"),
    )
