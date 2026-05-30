"""live_smoke — run the benign pilot with a LIVE Claude node (wave 6, §42).

The wave-5 ``run_pilot`` drives the real backbone with deterministic offline
``PilotNodeAdapter`` nodes. ``live_smoke`` is the same end-to-end backbone
(real ledger / verify / honeypot / transparency-log) but with ONE node driven by
the live ``ClaudeCliAdapter`` — a real Claude model via the isolated ``claude -p``
spawn — proving the machinery works with a real AI in the loop.

DIVERSITY NOTE (surfaced, not faked): the pilot unit's ``model_diversity=2``
quorum needs ≥2 DISTINCT model families. ``live_smoke`` supplies the live
``claude`` family PLUS one genuinely-distinct deterministic ``reference`` family
(``PilotNodeAdapter``) so the quorum is satisfiable. We do NOT fake a second
Claude identity — a real second model family is the production path, documented
here. The live node's correctness is judged by the REAL verify layer against the
``reference`` node + the honeypot gold standard.

The live spawn is reached only when ``transcript_fn`` is ``None`` (the default);
inject a fake ``transcript_fn`` to exercise this path offline + deterministically.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Optional

from ..execute.claude_adapter import ClockFn, TranscriptFn
from ..execute.claude_adapter import ClaudeCliAdapter
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
from .runner import PilotRunSummary, UnitRunResult

_LEASE_SECONDS = 60.0

#: the live model family + the distinct deterministic reference family.
LIVE_FAMILY = "claude"
REFERENCE_FAMILY = "reference"


def live_smoke(
    ledger: Ledger,
    *,
    transcript_fn: Optional[TranscriptFn] = None,
    clock_fn: Optional[ClockFn] = None,
    model: str = "sonnet",
    timeout: float = 120.0,
) -> PilotRunSummary:
    """Run the benign pilot end-to-end with a live Claude node over a real Ledger.

    Args:
      ledger: a real, fresh ``Ledger`` (carries its injected ``Clock``).
      transcript_fn: injected fake transcript producer for offline tests; when
        ``None`` the ``ClaudeCliAdapter`` performs the REAL isolated ``claude -p``
        spawn (the live path).
      clock_fn: provenance clock for the live candidate (injectable, deterministic
        in tests).
      model: subscription model tier for the live call (default ``sonnet``).
      timeout: per-call subprocess timeout (seconds).

    Returns a ``PilotRunSummary`` (same shape as ``run_pilot``). The live
    ``claude`` node and a distinct deterministic ``reference`` node both execute
    every unit; the REAL verify layer aggregates them (diversity quorum of 2
    satisfiable; honeypot scores the seeded unit against the gold standard).
    """
    snippets = load_snippets()
    units = build_pilot_units(snippets)
    hp_task_id = unit_task_id(honeypot_snippet(snippets)["snippet_id"])
    hp_gold = gold_answer(honeypot_snippet(snippets))

    live_adapter = ClaudeCliAdapter(
        transcript_fn=transcript_fn,
        clock_fn=clock_fn,
        model=model,
        timeout=timeout,
    )
    reference_adapter = PilotNodeAdapter(model_family=REFERENCE_FAMILY)

    # (family-label, node-id, adapter) tuples — the live node + the reference node.
    nodes = [
        (LIVE_FAMILY, f"node-{LIVE_FAMILY}", live_adapter),
        (REFERENCE_FAMILY, f"node-{REFERENCE_FAMILY}", reference_adapter),
    ]

    unit_results: list[UnitRunResult] = []

    for unit_dict in units:
        task_id = ledger.define_task(unit_dict)

        candidates: list[CandidateResult] = []
        for _family, node_id, adapter in nodes:
            claim = ledger.claim_task(
                task_id, node_id=node_id, lease_seconds=_LEASE_SECONDS
            )
            outcome = run_work_unit(unit_dict, adapter)
            # The live adapter fails closed (empty output) rather than returning
            # None, so a candidate always exists; it may fail acceptance/verify.
            assert outcome.candidate is not None
            cand = replace(outcome.candidate, adapter_name=node_id)
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
