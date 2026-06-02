"""verify_unit end-to-end tests (OUTCOME-ALTITUDE).

verify_unit is invoked with N freshly-built CandidateResults and NO pre-arranged
verdict state — it runs the full L2->L1->L4->L3 + tiebreak pipeline and returns
one VerifyVerdict. This is the layer's outcome-altitude entry point.
"""

from __future__ import annotations

from cairn.verify import (
    EVENT_HONEYPOT_FAIL,
    STATUS_ACCEPTED,
    STATUS_INSUFFICIENT_DIVERSITY,
    Honeypot,
    InMemoryReputation,
    NEUTRAL_PRIOR,
    verify_unit,
)

from ._verify_helpers import make_result, policy


def test_happy_path_two_families_agree_accepted():
    rs = [
        make_result({"verdict": "predator"}, node="a", family="anthropic"),
        make_result({"verdict": "predator"}, node="b", family="openai"),
        make_result({"verdict": "benign"}, node="c", family="meta"),
    ]
    rep = InMemoryReputation()
    verdict = verify_unit(
        rs, policy(target_nresults=3, min_quorum=2), reputation=rep,
        unit_task_id="u1",
    )
    assert verdict.status == STATUS_ACCEPTED
    assert verdict.accepted_output == {"verdict": "predator"}
    assert verdict.reputation_updates  # deltas emitted
    assert verdict.tiebreak.escalate is False
    # Consensus nodes gained, the minority node lost.
    assert rep.score("a") > NEUTRAL_PRIOR
    assert rep.score("c") < NEUTRAL_PRIOR


def test_single_family_consensus_blocked_and_tiebreak_escalates():
    rs = [
        make_result({"verdict": "predator"}, node="a", family="anthropic"),
        make_result({"verdict": "predator"}, node="b", family="anthropic"),
    ]
    verdict = verify_unit(rs, policy(target_nresults=3, min_quorum=2))
    assert verdict.status == STATUS_INSUFFICIENT_DIVERSITY
    assert verdict.accepted_output is None
    assert verdict.tiebreak.escalate is True
    assert verdict.tiebreak.extra_nodes == 1


def test_honeypot_unit_penalizes_bad_node():
    rs = [
        make_result({"verdict": "predator"}, node="good", family="anthropic"),
        make_result({"verdict": "predator"}, node="good2", family="openai"),
        make_result({"verdict": "benign"}, node="bad", family="meta"),
    ]
    rep = InMemoryReputation()
    hp = Honeypot(expected_output={"verdict": "predator"})
    verdict = verify_unit(
        rs, policy(target_nresults=3, min_quorum=2),
        honeypot=hp, reputation=rep, unit_task_id="hp-1",
    )
    scores = {s.node_id: s for s in verdict.honeypot_scores}
    assert scores["bad"].passed is False
    assert scores["good"].passed is True
    # The bad node was penalized via a HONEYPOT_FAIL delta.
    fail_events = [
        d for d in verdict.reputation_updates
        if d.subject == "bad" and d.event == EVENT_HONEYPOT_FAIL
    ]
    assert fail_events
    assert rep.score("bad") < NEUTRAL_PRIOR


def test_default_agreement_used_when_none_passed():
    # No agreement function passed -> ObjectiveAgreement default still clusters.
    rs = [
        make_result({"v": "x"}, node="a", family="anthropic"),
        make_result({"v": "x"}, node="b", family="openai"),
    ]
    verdict = verify_unit(rs, policy(target_nresults=2, min_quorum=2))
    assert verdict.status == STATUS_ACCEPTED
