"""Tiebreak policy tests.

DISPUTED with headroom ⇒ escalate one more node; ACCEPTED ⇒ no escalation;
DISPUTED at the target_nresults ceiling ⇒ no escalation (escalating past budget
is a policy/owner call, not automatic).
"""

from __future__ import annotations

from cairn.verify import ObjectiveAgreement, decide_quorum, decide_tiebreak

from ._verify_helpers import make_result, policy


def _quorum(results, pol):
    return decide_quorum(ObjectiveAgreement().cluster(results), pol)


def test_disputed_with_headroom_escalates_one():
    rs = [
        make_result({"v": "yes"}, node="a", family="anthropic"),
        make_result({"v": "yes"}, node="b", family="openai"),
        make_result({"v": "no"}, node="c", family="meta"),
        make_result({"v": "no"}, node="d", family="mistral"),
    ]
    pol = policy(target_nresults=5, min_quorum=3)  # headroom: 5 - 4 = 1
    q = _quorum(rs, pol)
    dec = decide_tiebreak(q, pol, unit_task_id="unit-1")
    assert dec.escalate is True
    assert dec.extra_nodes == 1
    assert dec.unit_task_id == "unit-1"


def test_accepted_no_escalation():
    rs = [
        make_result({"v": "yes"}, node="a", family="anthropic"),
        make_result({"v": "yes"}, node="b", family="openai"),
    ]
    pol = policy(target_nresults=3, min_quorum=2)
    q = _quorum(rs, pol)
    dec = decide_tiebreak(q, pol)
    assert dec.escalate is False
    assert dec.extra_nodes == 0


def test_no_headroom_no_escalation():
    # 4 results collected, target_nresults already 4 -> no headroom.
    rs = [
        make_result({"v": "yes"}, node="a", family="anthropic"),
        make_result({"v": "yes"}, node="b", family="openai"),
        make_result({"v": "no"}, node="c", family="meta"),
        make_result({"v": "no"}, node="d", family="mistral"),
    ]
    pol = policy(target_nresults=4, min_quorum=3)
    q = _quorum(rs, pol)
    dec = decide_tiebreak(q, pol)
    assert dec.escalate is False
    assert "consumed" in dec.reason


def test_insufficient_diversity_escalates():
    # Single-family consensus with headroom -> escalate to bring a new family.
    rs = [
        make_result({"v": "yes"}, node="a", family="anthropic"),
        make_result({"v": "yes"}, node="b", family="anthropic"),
    ]
    pol = policy(target_nresults=3, min_quorum=2)
    q = _quorum(rs, pol)
    dec = decide_tiebreak(q, pol)
    assert dec.escalate is True
    assert dec.extra_nodes == 1
