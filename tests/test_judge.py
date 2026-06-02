"""MockJudge determinism tests.

The MockJudge is a deterministic offline test double for the real LLM judge.
Its agreement_key must be deterministic, key-order-insensitive, and
case/whitespace-insensitive, while keeping distinct meanings distinct.
"""

from __future__ import annotations

from cairn.verify import MockJudge

from ._verify_helpers import make_result


def test_deterministic_repeatable():
    j = MockJudge()
    r = make_result({"a": "X", "b": "Y"}, node="n", family="f")
    assert j.agreement_key(r) == j.agreement_key(r)


def test_key_order_insensitive():
    j = MockJudge()
    r1 = make_result({"a": "x", "b": "y"}, node="n1", family="f")
    r2 = make_result({"b": "y", "a": "x"}, node="n2", family="g")
    assert j.agreement_key(r1) == j.agreement_key(r2)


def test_case_and_whitespace_insensitive():
    j = MockJudge()
    r1 = make_result({"v": "Hello  World"}, node="n1", family="f")
    r2 = make_result({"v": " hello world "}, node="n2", family="g")
    assert j.agreement_key(r1) == j.agreement_key(r2)


def test_distinct_meanings_distinct_keys():
    j = MockJudge()
    r1 = make_result({"v": "predator"}, node="n1", family="f")
    r2 = make_result({"v": "benign"}, node="n2", family="g")
    assert j.agreement_key(r1) != j.agreement_key(r2)


def test_normalize_fn_hook_drops_volatile_field():
    # A real judge ignores volatile fields; the normalize_fn hook models that.
    j = MockJudge(normalize_fn=lambda o: {k: v for k, v in o.items() if k != "ts"})
    r1 = make_result({"v": "same", "ts": "t1"}, node="n1", family="f")
    r2 = make_result({"v": "same", "ts": "t2"}, node="n2", family="g")
    assert j.agreement_key(r1) == j.agreement_key(r2)
