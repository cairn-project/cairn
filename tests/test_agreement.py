"""Agreement clustering tests.

Agreement is semantic, NOT bit-equality. ObjectiveAgreement clusters
normalized-equal outputs; SubjectiveAgreement + MockJudge clusters
semantically-equal-but-not-bit-equal outputs.
"""

from __future__ import annotations

from cairn.verify import MockJudge, ObjectiveAgreement, SubjectiveAgreement

from ._verify_helpers import make_result


def test_objective_clusters_identical_outputs():
    rs = [
        make_result({"verdict": "yes"}, node="a", family="anthropic"),
        make_result({"verdict": "yes"}, node="b", family="openai"),
        make_result({"verdict": "no"}, node="c", family="meta"),
    ]
    clusters = ObjectiveAgreement().cluster(rs)
    assert len(clusters) == 2
    # The "yes" cluster has two members from two families.
    yes = max(clusters, key=lambda c: c.size)
    assert yes.size == 2
    assert yes.model_families == {"anthropic", "openai"}


def test_objective_normalizes_case_and_whitespace():
    rs = [
        make_result({"answer": "Hello World"}, node="a", family="x"),
        make_result({"answer": "hello   world"}, node="b", family="y"),
        make_result({"answer": " HELLO WORLD "}, node="c", family="z"),
    ]
    clusters = ObjectiveAgreement(normalize=True).cluster(rs)
    assert len(clusters) == 1
    assert clusters[0].size == 3


def test_objective_strict_mode_splits_trivially_different():
    rs = [
        make_result({"answer": "Hello World"}, node="a", family="x"),
        make_result({"answer": "hello world"}, node="b", family="y"),
    ]
    clusters = ObjectiveAgreement(normalize=False).cluster(rs)
    assert len(clusters) == 2


def test_objective_field_keying():
    # Cluster on a single field; other (divergent) fields are ignored.
    rs = [
        make_result({"verdict": "yes", "note": "alpha"}, node="a", family="x"),
        make_result({"verdict": "yes", "note": "beta"}, node="b", family="y"),
    ]
    clusters = ObjectiveAgreement(field="verdict").cluster(rs)
    assert len(clusters) == 1
    assert clusters[0].size == 2


def test_subjective_mockjudge_clusters_semantically_equal():
    # Different key ORDER + casing/whitespace — never bit-equal, but the judge
    # canonicalizes them into one cluster.
    rs = [
        make_result(
            {"verdict": "Predator Vendor", "confidence": "High"},
            node="a",
            family="anthropic",
        ),
        make_result(
            {"confidence": "high", "verdict": "predator   vendor"},
            node="b",
            family="openai",
        ),
        make_result({"verdict": "benign", "confidence": "low"}, node="c", family="meta"),
    ]
    clusters = SubjectiveAgreement(MockJudge()).cluster(rs)
    assert len(clusters) == 2
    agree = max(clusters, key=lambda c: c.size)
    assert agree.size == 2
    assert agree.model_families == {"anthropic", "openai"}
