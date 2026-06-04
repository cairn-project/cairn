"""Acceptance-evaluation tests: one pass + one fail per kind."""

from __future__ import annotations

import pytest

from cairn import UnknownPredicateError, evaluate_acceptance


def _contract(*predicates):
    return {"predicates": list(predicates)}


# --- required_fields --------------------------------------------------------


def test_required_fields_pass():
    c = _contract({"kind": "required_fields", "fields": ["a", "b"]})
    assert evaluate_acceptance({"a": 1, "b": 2}, c).passed


def test_required_fields_fail():
    c = _contract({"kind": "required_fields", "fields": ["a", "b"]})
    assert not evaluate_acceptance({"a": 1}, c).passed


def test_required_fields_dotted_path():
    c = _contract({"kind": "required_fields", "fields": ["v.url"]})
    assert evaluate_acceptance({"v": {"url": "x"}}, c).passed
    assert not evaluate_acceptance({"v": {}}, c).passed


# --- field_type -------------------------------------------------------------


def test_field_type_pass():
    c = _contract({"kind": "field_type", "field": "n", "json_type": "integer"})
    assert evaluate_acceptance({"n": 5}, c).passed


def test_field_type_fail():
    c = _contract({"kind": "field_type", "field": "n", "json_type": "integer"})
    assert not evaluate_acceptance({"n": "five"}, c).passed


def test_field_type_bool_is_not_integer():
    c = _contract({"kind": "field_type", "field": "n", "json_type": "integer"})
    assert not evaluate_acceptance({"n": True}, c).passed


# --- value_range ------------------------------------------------------------


def test_value_range_pass():
    c = _contract({"kind": "value_range", "field": "c", "min": 0, "max": 1})
    assert evaluate_acceptance({"c": 0.5}, c).passed


def test_value_range_fail_high():
    c = _contract({"kind": "value_range", "field": "c", "min": 0, "max": 1})
    assert not evaluate_acceptance({"c": 1.5}, c).passed


def test_value_range_fail_non_numeric():
    c = _contract({"kind": "value_range", "field": "c", "min": 0})
    assert not evaluate_acceptance({"c": "x"}, c).passed


# --- enum -------------------------------------------------------------------


def test_enum_pass():
    c = _contract({"kind": "enum", "field": "cat", "allowed": ["a", "b"]})
    assert evaluate_acceptance({"cat": "a"}, c).passed


def test_enum_fail():
    c = _contract({"kind": "enum", "field": "cat", "allowed": ["a", "b"]})
    assert not evaluate_acceptance({"cat": "z"}, c).passed


# --- non_empty (refusal-handling) -------------------------------------------


def test_non_empty_pass():
    c = _contract({"kind": "non_empty", "field": "answer"})
    assert evaluate_acceptance({"answer": "hello"}, c).passed


def test_non_empty_fail_empty_string():
    c = _contract({"kind": "non_empty", "field": "answer"})
    assert not evaluate_acceptance({"answer": ""}, c).passed


def test_non_empty_fail_absent():
    c = _contract({"kind": "non_empty", "field": "answer"})
    assert not evaluate_acceptance({}, c).passed


# --- min_items (citations-required) -----------------------------------------


def test_min_items_pass():
    c = _contract({"kind": "min_items", "field": "citations", "count": 1})
    assert evaluate_acceptance({"citations": ["u1"]}, c).passed


def test_min_items_fail():
    c = _contract({"kind": "min_items", "field": "citations", "count": 1})
    assert not evaluate_acceptance({"citations": []}, c).passed


# --- regex_match (format) ---------------------------------------------------


def test_regex_match_pass():
    c = _contract({"kind": "regex_match", "field": "url", "pattern": "^https?://"})
    assert evaluate_acceptance({"url": "https://x"}, c).passed


def test_regex_match_fail():
    c = _contract({"kind": "regex_match", "field": "url", "pattern": "^https?://"})
    assert not evaluate_acceptance({"url": "ftp://x"}, c).passed


def test_dotted_path_indexes_into_array():
    c = _contract({"kind": "regex_match", "field": "citations.0", "pattern": "^https?://"})
    assert evaluate_acceptance({"citations": ["https://x"]}, c).passed
    assert not evaluate_acceptance({"citations": ["ftp://x"]}, c).passed
    assert not evaluate_acceptance({"citations": []}, c).passed  # index out of range


# --- conjunction + unknown kind --------------------------------------------


def test_conjunction_one_failing_predicate_fails_whole_contract():
    c = _contract(
        {"kind": "required_fields", "fields": ["a"]},
        {"kind": "non_empty", "field": "a"},
        {"kind": "value_range", "field": "n", "min": 0, "max": 1},
    )
    res = evaluate_acceptance({"a": "ok", "n": 99}, c)
    assert not res.passed
    # exactly the value_range predicate should be the failing one
    failed = [r for r in res.results if not r.passed]
    assert len(failed) == 1
    assert failed[0].kind == "value_range"


def test_unknown_predicate_kind_raises():
    c = _contract({"kind": "totally_made_up"})
    with pytest.raises(UnknownPredicateError):
        evaluate_acceptance({}, c)


def test_structured_fixture_contract_passes_on_good_result():
    from cairn import load_fixture

    unit = load_fixture("structured_acceptance")
    good = {
        "category": "electronics",
        "confidence": 0.82,
        "citations": ["https://example-marketplace.test/items/usb-c-hub-7in1"],
        "rationale": "7-port USB-C hub is consumer electronics.",
    }
    assert evaluate_acceptance(good, unit["acceptance_contract"]).passed


def test_structured_fixture_contract_fails_on_bad_result():
    from cairn import load_fixture

    unit = load_fixture("structured_acceptance")
    bad = {
        "category": "spaceship",  # not in enum
        "confidence": 2.0,  # out of range
        "citations": [],  # below min_items
        "rationale": "",  # empty
    }
    assert not evaluate_acceptance(bad, unit["acceptance_contract"]).passed
