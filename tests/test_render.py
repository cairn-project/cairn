"""Portable-payload render tests.

objective + inputs + output_schema + acceptance_contract is the
ENTIRE portable payload — nothing else crosses the adapter seam.
"""

from __future__ import annotations

import pytest

from cairn import load_fixture
from cairn.execute import render_payload
from cairn.types import WorkUnit

_NAMES = ["benign_pilot", "cause_threaded", "structured_acceptance"]


@pytest.mark.parametrize("name", _NAMES)
def test_render_copies_only_the_four_tuple(name):
    unit = WorkUnit.from_dict(load_fixture(name))
    payload = render_payload(unit)

    assert payload.objective == unit.objective
    assert payload.inputs == unit.inputs
    assert payload.output_schema == unit.output_schema
    # acceptance_contract is normalized to dict form
    assert "predicates" in payload.acceptance_contract


@pytest.mark.parametrize("name", _NAMES)
def test_prompt_mentions_objective(name):
    unit = WorkUnit.from_dict(load_fixture(name))
    payload = render_payload(unit)
    assert unit.objective in payload.prompt


def test_no_other_unit_field_leaks_into_payload():
    """The payload must not carry task_id / capability_floor / provenance etc."""
    unit = WorkUnit.from_dict(load_fixture("cause_threaded"))
    payload = render_payload(unit)

    serialized = repr(payload)
    # task_id, the lease, and capability_floor's window are NOT part of the
    # portable payload — they stay behind the seam.
    assert unit.task_id not in serialized
    assert "duration_seconds" not in serialized
    # the rendered payload exposes exactly five public attributes
    assert set(vars(payload).keys()) == {
        "objective",
        "inputs",
        "output_schema",
        "acceptance_contract",
        "prompt",
    }
