"""Schema-validation tests."""

from __future__ import annotations

import pytest

from cairn import load_fixture, validate_work_unit


def _minimal_unit() -> dict:
    """A schema-valid unit with only the required fields."""
    return {
        "schema_version": "1.0.0",
        "task_id": "t-1",
        "cause_id": "c-1",
        "objective": "do the thing",
        "inputs": {"inline": {"x": 1}},
        "output_schema": {"type": "object"},
        "acceptance_contract": {"predicates": []},
        "capability_floor": {},
        "redundancy_policy": {"target_nresults": 1, "min_quorum": 1},
        "provenance_requirements": {},
    }


def test_minimal_valid_unit_passes():
    result = validate_work_unit(_minimal_unit())
    assert result.valid, result.errors


def test_full_valid_unit_with_optionals_passes():
    unit = _minimal_unit()
    unit["capability_floor"] = {
        "context_window": 8192,
        "tools": ["web_fetch"],
        "modalities": ["text"],
    }
    unit["redundancy_policy"]["model_diversity"] = 2
    unit["provenance_requirements"] = {
        "model_family": True,
        "signed_result": True,
        "trace": True,
    }
    unit["deadline"] = "2026-06-15T00:00:00Z"
    unit["lease"] = {"duration_seconds": 3600}
    result = validate_work_unit(unit)
    assert result.valid, result.errors


def test_missing_required_field_fails():
    unit = _minimal_unit()
    del unit["cause_id"]
    result = validate_work_unit(unit)
    assert not result.valid
    assert any("cause_id" in e for e in result.errors)


def test_wrong_type_fails():
    unit = _minimal_unit()
    unit["redundancy_policy"]["target_nresults"] = "two"
    result = validate_work_unit(unit)
    assert not result.valid
    assert any("target_nresults" in e for e in result.errors)


def test_inputs_neither_inline_nor_pointer_fails():
    unit = _minimal_unit()
    unit["inputs"] = {}
    result = validate_work_unit(unit)
    assert not result.valid
    assert any("input" in e.lower() or "oneOf" in e for e in result.errors)


def test_inputs_both_inline_and_pointer_fails():
    unit = _minimal_unit()
    unit["inputs"] = {
        "inline": {"x": 1},
        "pointer": "ledger://p",
        "hash": "sha256:abc",
    }
    result = validate_work_unit(unit)
    assert not result.valid


def test_content_addressed_inputs_pass():
    unit = _minimal_unit()
    unit["inputs"] = {"pointer": "ledger://blob", "hash": "sha256:abc"}
    result = validate_work_unit(unit)
    assert result.valid, result.errors


def test_incompatible_major_version_rejected():
    unit = _minimal_unit()
    unit["schema_version"] = "2.0.0"
    result = validate_work_unit(unit)
    assert not result.valid
    assert any("MAJOR" in e for e in result.errors)


def test_non_dict_input_is_not_valid():
    result = validate_work_unit(["not", "a", "unit"])
    assert not result.valid


def test_additional_properties_rejected():
    unit = _minimal_unit()
    unit["surprise_field"] = "nope"
    result = validate_work_unit(unit)
    assert not result.valid


@pytest.mark.parametrize("name", ["benign_pilot", "cause_threaded", "structured_acceptance"])
def test_fixtures_are_schema_valid(name):
    result = validate_work_unit(load_fixture(name))
    assert result.valid, result.errors
