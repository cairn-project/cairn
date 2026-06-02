"""MockAdapter tests.

The deterministic offline adapter must, for each fixture, produce output
that (a) validates against the fixture's output_schema and (b) passes the
fixture's acceptance_contract via the evaluator. No network.
"""

from __future__ import annotations

import pytest
from jsonschema import Draft202012Validator

from cairn import evaluate_acceptance, load_fixture
from cairn.execute import MockAdapter
from cairn.types import WorkUnit

_NAMES = ["benign_pilot", "cause_threaded", "structured_acceptance"]


@pytest.mark.parametrize("name", _NAMES)
def test_mock_output_matches_output_schema(name):
    unit = WorkUnit.from_dict(load_fixture(name))
    candidate = MockAdapter().produce(unit)
    errors = sorted(
        Draft202012Validator(unit.output_schema).iter_errors(candidate.output),
        key=lambda e: list(e.path),
    )
    assert not errors, [e.message for e in errors]


@pytest.mark.parametrize("name", _NAMES)
def test_mock_output_passes_acceptance(name):
    unit = WorkUnit.from_dict(load_fixture(name))
    candidate = MockAdapter().produce(unit)
    verdict = evaluate_acceptance(candidate.output, unit.acceptance_contract)
    assert verdict.passed, [
        (r.kind, r.detail) for r in verdict.results if not r.passed
    ]


def test_mock_is_deterministic():
    unit = WorkUnit.from_dict(load_fixture("structured_acceptance"))
    a = MockAdapter().produce(unit)
    b = MockAdapter().produce(unit)
    assert a.output == b.output
    assert a.signature == b.signature


def test_mock_stamps_provenance_placeholders():
    unit = WorkUnit.from_dict(load_fixture("benign_pilot"))
    candidate = MockAdapter().produce(unit)
    assert candidate.task_id == unit.task_id
    assert candidate.adapter_name == "mock"
    assert candidate.model_family == "mock"
    assert candidate.signature is not None
    # provenance reporting (no enforcement): model_family + signature satisfied
    report = candidate.provenance_satisfies(unit.provenance_requirements)
    assert report["model_family"] is True
    assert report["signed_result"] is True


def test_corrupt_mode_fails_acceptance():
    unit = WorkUnit.from_dict(load_fixture("benign_pilot"))
    candidate = MockAdapter(corrupt=True).produce(unit)
    verdict = evaluate_acceptance(candidate.output, unit.acceptance_contract)
    assert not verdict.passed
