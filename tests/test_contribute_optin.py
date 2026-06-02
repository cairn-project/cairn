"""Contributor opt-in tests (gated, recorded, revocable consent)."""

from __future__ import annotations

import pytest

from cairn.cause import CauseRegistry, five_frame_gate_check
from cairn.cause.model import FRAME_KEYS
from cairn.contribute import OptInRefused, OptInRegistry
from cairn.contribute.optin import OptInError
from cairn.ledger import FixedClock, Ledger
from cairn.ledger.translog import (
    KIND_CONSENT_RECORDED,
    KIND_CONSENT_REVOKED,
    verify_log,
)

_DEMO_KEY = b"cairn-contribute-test-key-not-secret"
_NODE = "node-a"


def _ledger(tmp_path):
    return Ledger(tmp_path / "ledger", FixedClock(start=0.0), signing_key=_DEMO_KEY)


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
    ledger = _ledger(tmp_path)
    causes = CauseRegistry(ledger)
    optin = OptInRegistry(ledger, causes)
    return ledger, causes, optin


def _approved_cause(causes):
    cause = causes.submit_cause_request(_draft())
    causes.decide_cause(
        cause.cause_id,
        approve=True,
        reason="benign; passes all five frames",
        decider="anchor",
        gate_result=five_frame_gate_check({k: True for k in FRAME_KEYS}),
    )
    return cause.cause_id


def _kinds(ledger):
    return [e.kind for e in ledger.translog.entries()]


def test_optin_refused_for_requested_cause(tmp_path):
    ledger, causes, optin = _setup(tmp_path)
    cause = causes.submit_cause_request(_draft())  # REQUESTED, not listable
    with pytest.raises(OptInRefused):
        optin.opt_in(_NODE, cause.cause_id, "I agree to work this cause")
    assert optin.is_opted_in(_NODE, cause.cause_id) is False
    assert KIND_CONSENT_RECORDED not in _kinds(ledger)


def test_optin_refused_for_rejected_cause(tmp_path):
    ledger, causes, optin = _setup(tmp_path)
    cause = causes.submit_cause_request(_draft())
    causes.decide_cause(
        cause.cause_id,
        approve=False,
        reason="rejected for the record",
        decider="anchor",
        gate_result=five_frame_gate_check({k: True for k in FRAME_KEYS}),
    )
    with pytest.raises(OptInRefused):
        optin.opt_in(_NODE, cause.cause_id, "I agree")
    assert KIND_CONSENT_RECORDED not in _kinds(ledger)


def test_optin_succeeds_for_approved_cause_and_logs(tmp_path):
    ledger, causes, optin = _setup(tmp_path)
    cause_id = _approved_cause(causes)
    record = optin.opt_in(_NODE, cause_id, "Run benign units on the mock adapter")
    assert record.active is True
    assert record.node_id == _NODE and record.cause_id == cause_id
    assert optin.is_opted_in(_NODE, cause_id) is True
    assert KIND_CONSENT_RECORDED in _kinds(ledger)
    # The whole chain (cause decision + consent) still verifies.
    assert verify_log(ledger.translog._path).ok  # noqa: SLF001


def test_revoke_flips_opted_in_and_logs(tmp_path):
    ledger, causes, optin = _setup(tmp_path)
    cause_id = _approved_cause(causes)
    optin.opt_in(_NODE, cause_id, "agreed")
    optin.revoke(_NODE, cause_id)
    assert optin.is_opted_in(_NODE, cause_id) is False
    assert KIND_CONSENT_REVOKED in _kinds(ledger)


def test_revoke_without_consent_raises(tmp_path):
    _, causes, optin = _setup(tmp_path)
    cause_id = _approved_cause(causes)
    with pytest.raises(OptInError):
        optin.revoke(_NODE, cause_id)
