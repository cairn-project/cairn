"""End-to-end execute-flow tests.

run_work_unit wires validate + acceptance with the adapter seam.
Offline (MockAdapter) only.
"""

from __future__ import annotations

import copy

import pytest

from cairn import load_fixture
from cairn.execute import (
    Capabilities,
    MockAdapter,
    TrivialCalibrationProbe,
    run_work_unit,
)
from cairn.execute.flow import (
    STATUS_ACCEPTED,
    STATUS_ACCEPTED_ACCEPTANCE_FAILED,
    STATUS_REJECTED_CALIBRATION,
    STATUS_REJECTED_CAPABILITY,
    STATUS_REJECTED_VALIDATION,
)

_NAMES = ["benign_pilot", "cause_threaded", "structured_acceptance"]


@pytest.mark.parametrize("name", _NAMES)
def test_end_to_end_qualified_adapter_accepts(name):
    outcome = run_work_unit(load_fixture(name), MockAdapter())
    assert outcome.status == STATUS_ACCEPTED, outcome.detail
    assert outcome.candidate is not None
    assert outcome.acceptance is not None and outcome.acceptance.passed
    assert outcome.capability_check.qualifies


def test_under_capable_adapter_rejected_on_capability():
    # benign_pilot floor: context_window 4096. Give the node 1024.
    weak = MockAdapter(
        capabilities=Capabilities(context_window=1024, tools=[], modalities=["text"])
    )
    outcome = run_work_unit(load_fixture("benign_pilot"), weak)
    assert outcome.status == STATUS_REJECTED_CAPABILITY
    assert outcome.candidate is None
    assert not outcome.capability_check.qualifies


def test_invalid_unit_rejected_on_validation():
    bad = load_fixture("benign_pilot")
    del bad["cause_id"]  # required field
    outcome = run_work_unit(bad, MockAdapter())
    assert outcome.status == STATUS_REJECTED_VALIDATION
    assert outcome.candidate is None
    assert not outcome.validation.valid


def test_corrupt_adapter_produces_but_fails_acceptance():
    outcome = run_work_unit(load_fixture("benign_pilot"), MockAdapter(corrupt=True))
    assert outcome.status == STATUS_ACCEPTED_ACCEPTANCE_FAILED
    assert outcome.candidate is not None  # candidate exists
    assert outcome.acceptance is not None and not outcome.acceptance.passed


def test_calibration_probe_rejects_malformed_capabilities():
    bad_caps = MockAdapter(
        capabilities=Capabilities(context_window=-1, tools=[], modalities=["telepathy"])
    )
    outcome = run_work_unit(load_fixture("benign_pilot"), bad_caps, probe=TrivialCalibrationProbe())
    assert outcome.status == STATUS_REJECTED_CALIBRATION
    assert outcome.candidate is None
    assert outcome.calibration is not None and not outcome.calibration.passed


def test_calibration_probe_passes_well_formed_then_runs():
    outcome = run_work_unit(
        load_fixture("structured_acceptance"),
        MockAdapter(),
        probe=TrivialCalibrationProbe(),
    )
    assert outcome.status == STATUS_ACCEPTED
    assert outcome.calibration is not None and outcome.calibration.passed


def test_does_not_mutate_input_unit_dict():
    unit = load_fixture("benign_pilot")
    snapshot = copy.deepcopy(unit)
    run_work_unit(unit, MockAdapter())
    assert unit == snapshot
