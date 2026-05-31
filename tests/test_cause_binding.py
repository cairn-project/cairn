"""Cause ⇄ work-units binding tests (PLAN §2 + §3.3 + §3.8)."""

from __future__ import annotations

import pytest

from cairn.cause import PilotWorkUnitProvider, WorkUnitRegistry
from cairn.pilot.cause import HONEYPOT_SNIPPET_ID
from cairn.validate import validate_work_unit

_CAUSE = "demo.benign-cause"


def test_provider_restamps_units_to_bound_cause():
    provider = PilotWorkUnitProvider(_CAUSE)
    units = provider.work_units()
    assert units, "expected at least one bound unit"
    for u in units:
        # Every unit belongs to the bound cause, not the hard-coded pilot literal.
        assert u["cause_id"] == _CAUSE
        assert u["task_id"].startswith(f"{_CAUSE}::")
        # And still validates against the wave-1 spec (no new schema introduced).
        assert validate_work_unit(u).valid


def test_provider_honeypot_seed_matches_a_bound_unit():
    provider = PilotWorkUnitProvider(_CAUSE)
    hp_task = provider.honeypot_task_id()
    assert hp_task == f"{_CAUSE}::{HONEYPOT_SNIPPET_ID}"
    task_ids = {u["task_id"] for u in provider.work_units()}
    assert hp_task in task_ids
    gold = provider.honeypot_gold()
    assert set(gold) == {"is_open_license", "license_id"}


def test_registry_binds_and_resolves_provider():
    reg = WorkUnitRegistry()
    assert not reg.is_bound(_CAUSE)
    provider = reg.bind_pilot(_CAUSE)
    assert reg.is_bound(_CAUSE)
    assert reg.provider_for(_CAUSE) is provider


def test_registry_unknown_cause_raises():
    reg = WorkUnitRegistry()
    with pytest.raises(KeyError):
        reg.provider_for("nope.unbound")
