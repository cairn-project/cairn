"""Honeypot / gold-standard tests.

The load-bearing case: a node that fails the known-answer unit is flagged EVEN
WHEN it agrees with a (bad) peer majority — L4 catches the collusion L1 quorum
and L2 agreement miss.
"""

from __future__ import annotations

from cairn.verify import Honeypot, MockJudge, SubjectiveAgreement

from ._verify_helpers import make_result


def test_matching_node_passes_diverging_node_fails():
    hp = Honeypot(expected_output={"verdict": "predator"})
    rs = [
        make_result({"verdict": "predator"}, node="good", family="anthropic"),
        make_result({"verdict": "benign"}, node="bad", family="openai"),
    ]
    scores = {s.node_id: s for s in hp.score(rs)}
    assert scores["good"].passed is True
    assert scores["bad"].passed is False


def test_honeypot_catches_colluding_majority():
    # Two nodes AGREE on a WRONG answer (they would form a peer quorum), but the
    # gold standard says otherwise -> both honeypot-fail regardless of agreement.
    hp = Honeypot(expected_output={"verdict": "predator"})
    rs = [
        make_result({"verdict": "benign"}, node="colluder1", family="anthropic"),
        make_result({"verdict": "benign"}, node="colluder2", family="openai"),
        make_result({"verdict": "predator"}, node="honest", family="meta"),
    ]
    scores = {s.node_id: s for s in hp.score(rs)}
    assert scores["colluder1"].passed is False
    assert scores["colluder2"].passed is False
    assert scores["honest"].passed is True


def test_honeypot_with_subjective_agreement():
    # Gold standard scored semantically (case/order-insensitive) via MockJudge.
    hp = Honeypot(
        expected_output={"verdict": "Predator", "confidence": "high"},
        agreement=SubjectiveAgreement(MockJudge()),
    )
    rs = [
        make_result(
            {"confidence": "HIGH", "verdict": "predator"},
            node="paraphrase",
            family="anthropic",
        ),
    ]
    scores = hp.score(rs)
    assert scores[0].passed is True
