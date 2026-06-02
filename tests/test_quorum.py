"""Quorum + model-diversity tests.

ACCEPTED requires both size (>= min_quorum) AND diversity (>= 2 families).
A single-family cluster that meets size is INSUFFICIENT_DIVERSITY — the
anti-collusion rejection.
"""

from __future__ import annotations

from cairn.verify import (
    DEFAULT_MODEL_DIVERSITY,
    STATUS_ACCEPTED,
    STATUS_DISPUTED,
    STATUS_INSUFFICIENT_DIVERSITY,
    STATUS_NO_QUORUM,
    ObjectiveAgreement,
    decide_quorum,
    required_diversity,
)

from ._verify_helpers import make_result, policy


def _clusters(results):
    return ObjectiveAgreement().cluster(results)


def test_quorum_reached_with_diversity():
    rs = [
        make_result({"v": "yes"}, node="a", family="anthropic"),
        make_result({"v": "yes"}, node="b", family="openai"),
        make_result({"v": "no"}, node="c", family="meta"),
    ]
    res = decide_quorum(_clusters(rs), policy(min_quorum=2))
    assert res.status == STATUS_ACCEPTED
    assert res.winning_cluster is not None
    assert res.winning_cluster.size == 2
    assert len(res.winning_cluster.model_families) >= 2


def test_below_min_quorum_is_no_quorum():
    rs = [
        make_result({"v": "yes"}, node="a", family="anthropic"),
        make_result({"v": "no"}, node="b", family="openai"),
        make_result({"v": "maybe"}, node="c", family="meta"),
    ]
    res = decide_quorum(_clusters(rs), policy(min_quorum=2))
    assert res.status == STATUS_NO_QUORUM


def test_two_competing_clusters_is_disputed():
    rs = [
        make_result({"v": "yes"}, node="a", family="anthropic"),
        make_result({"v": "yes"}, node="b", family="openai"),
        make_result({"v": "no"}, node="c", family="meta"),
        make_result({"v": "no"}, node="d", family="mistral"),
    ]
    # min_quorum 3: neither size-2 cluster reaches it, but two clusters of >=2
    # compete -> DISPUTED.
    res = decide_quorum(_clusters(rs), policy(target_nresults=4, min_quorum=3))
    assert res.status == STATUS_DISPUTED


def test_single_family_consensus_rejected():
    # Three agreeing results but ALL one family -> not a valid quorum.
    rs = [
        make_result({"v": "yes"}, node="a", family="anthropic"),
        make_result({"v": "yes"}, node="b", family="anthropic"),
        make_result({"v": "yes"}, node="c", family="anthropic"),
    ]
    res = decide_quorum(_clusters(rs), policy(min_quorum=2))
    assert res.status == STATUS_INSUFFICIENT_DIVERSITY
    assert res.winning_cluster is None


def test_diversity_default_applied_when_policy_unset():
    # model_diversity=0 (fixture default) -> safe default of 2 applied.
    assert required_diversity(policy(model_diversity=0)) == DEFAULT_MODEL_DIVERSITY
    assert DEFAULT_MODEL_DIVERSITY == 2


def test_explicit_diversity_one_disables_gate():
    # A deliberately configured model_diversity=1 lets a single-family consensus pass.
    rs = [
        make_result({"v": "yes"}, node="a", family="anthropic"),
        make_result({"v": "yes"}, node="b", family="anthropic"),
    ]
    res = decide_quorum(_clusters(rs), policy(min_quorum=2, model_diversity=1))
    assert res.status == STATUS_ACCEPTED
