"""Fixture-parse tests (BUILD-PLAN §6.3)."""

from __future__ import annotations

import pytest

from cairn import list_fixtures, load_fixture, validate_work_unit
from cairn.types import WorkUnit


def test_three_fixtures_available():
    assert set(list_fixtures()) == {
        "benign_pilot",
        "cause_threaded",
        "structured_acceptance",
    }


@pytest.mark.parametrize("name", ["benign_pilot", "cause_threaded", "structured_acceptance"])
def test_fixture_validates_against_schema(name):
    result = validate_work_unit(load_fixture(name))
    assert result.valid, result.errors


@pytest.mark.parametrize("name", ["benign_pilot", "cause_threaded", "structured_acceptance"])
def test_fixture_round_trips_into_dataclass(name):
    unit = WorkUnit.from_dict(load_fixture(name))
    assert unit.task_id
    assert unit.cause_id
    assert unit.schema_version == "1.0.0"


def test_unknown_fixture_raises():
    with pytest.raises(KeyError):
        load_fixture("does_not_exist")


def test_cause_threaded_uses_content_addressed_inputs():
    unit = load_fixture("cause_threaded")
    assert "pointer" in unit["inputs"]
    assert "hash" in unit["inputs"]
    assert "inline" not in unit["inputs"]


def test_cause_threaded_has_capability_floor_and_cause_thread():
    unit = load_fixture("cause_threaded")
    assert unit["cause_id"]
    assert unit["capability_floor"]["context_window"] >= 1
