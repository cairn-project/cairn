"""Cause-scoped run loop tests (PLAN §2 + §3.3 + §3.9b).

Drives ``run_cause`` over the REAL engine (ledger / execute / verify / translog)
+ the REAL cause layer. Offline.
"""

from __future__ import annotations

import pytest

from cairn.cause import CauseRegistry, WorkUnitRegistry, five_frame_gate_check
from cairn.cause.model import FRAME_KEYS
from cairn.contribute import CauseRunRefused, OptInRegistry, run_cause
from cairn.ledger import FixedClock, Ledger
from cairn.ledger.translog import (
    KIND_RESULT_RECORDED,
    KIND_VERDICT_RECORDED,
    verify_log,
)

_DEMO_KEY = b"cairn-contribute-run-test-key-not-secret"
_NODE = "node-runner"


def _draft():
    return {
        "name": "Benign cause",
        "description": "a generic, mission-neutral cause",
        "target_conduct": "some publicly-observable conduct",
        "protected_boundary": "no persons profiled/stored/reported",
        "output_schema_ref": "result_v0",
        "partner_of_record_posture": "maintainer is actor-of-record",
        "created_by": "req",
        "five_frame": {
            k: {"frame": k, "claim": f"{k} ok", "passes": True} for k in FRAME_KEYS
        },
    }


def _setup(tmp_path):
    ledger = Ledger(tmp_path / "ledger", FixedClock(start=0.0), signing_key=_DEMO_KEY)
    causes = CauseRegistry(ledger)
    optin = OptInRegistry(ledger, causes)
    work_units = WorkUnitRegistry()
    return ledger, causes, optin, work_units


def _approve(causes):
    cause = causes.submit_cause_request(_draft())
    causes.decide_cause(
        cause.cause_id,
        approve=True,
        reason="benign; passes all five frames",
        decider="anchor",
        gate_result=five_frame_gate_check({k: True for k in FRAME_KEYS}),
    )
    return cause.cause_id


def _run(ledger, causes, optin, work_units, cause_id, **kw):
    return run_cause(
        cause_id,
        cause_registry=causes,
        optin_registry=optin,
        work_unit_registry=work_units,
        ledger=ledger,
        node_id=_NODE,
        **kw,
    )


def test_run_refused_when_not_opted_in(tmp_path):
    ledger, causes, optin, work_units = _setup(tmp_path)
    cause_id = _approve(causes)
    work_units.bind_pilot(cause_id)
    with pytest.raises(CauseRunRefused):
        _run(ledger, causes, optin, work_units, cause_id)  # no opt-in


def test_run_refused_when_cause_not_listable(tmp_path):
    ledger, causes, optin, work_units = _setup(tmp_path)
    cause = causes.submit_cause_request(_draft())  # REQUESTED, not listable
    work_units.bind_pilot(cause.cause_id)
    with pytest.raises(CauseRunRefused):
        _run(ledger, causes, optin, work_units, cause.cause_id)


def test_optin_then_run_works_and_records_against_cause(tmp_path):
    ledger, causes, optin, work_units = _setup(tmp_path)
    cause_id = _approve(causes)
    work_units.bind_pilot(cause_id)
    optin.opt_in(_NODE, cause_id, "agreed to run benign units")

    summary = _run(ledger, causes, optin, work_units, cause_id)

    assert summary.all_accepted
    assert summary.cause_id == cause_id and summary.node_id == _NODE
    # Every unit flowed through verify (quorum families present) + recorded.
    for u in summary.units:
        assert u.task_id.startswith(f"{cause_id}::")
        assert u.model_families_in_quorum  # quorum reached -> verify ran
    assert summary.result_recorded > 0 and summary.verdict_recorded > 0
    # Results + verdicts are on the translog, recorded against this cause's units.
    kinds = [e.kind for e in ledger.translog.entries()]
    assert KIND_RESULT_RECORDED in kinds and KIND_VERDICT_RECORDED in kinds
    recorded_task_ids = {
        e.payload.get("task_id")
        for e in ledger.translog.entries()
        if e.kind == KIND_VERDICT_RECORDED
    }
    assert all(tid.startswith(f"{cause_id}::") for tid in recorded_task_ids)
    assert verify_log(ledger.translog._path).ok  # noqa: SLF001


def test_run_honeypot_catches_faulty_node(tmp_path):
    ledger, causes, optin, work_units = _setup(tmp_path)
    cause_id = _approve(causes)
    work_units.bind_pilot(cause_id)
    optin.opt_in(_NODE, cause_id, "agreed")

    summary = _run(ledger, causes, optin, work_units, cause_id, bad_family="gpt")
    # The honeypot still catches a faulty node on the gold unit.
    assert summary.total_honeypot_catches >= 1
