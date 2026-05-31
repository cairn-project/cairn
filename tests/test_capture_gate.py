"""Trust-gated CAPTURE role — fail-closed grant/revoke + logging (AC.CAP.3)."""

from __future__ import annotations

import pytest

from cairn.capture import CaptureGate, CaptureGateError
from cairn.ledger import FixedClock, Ledger, verify_log
from cairn.ledger.translog import (
    KIND_CAPTURE_ROLE_GRANTED,
    KIND_CAPTURE_ROLE_REVOKED,
)

_KEY = b"capture-test-key-not-secret"


def _ledger(tmp_path) -> Ledger:
    return Ledger(tmp_path / "ledger", FixedClock(start=0.0), signing_key=_KEY)


def test_unknown_node_is_not_granted_fail_closed(tmp_path):
    gate = CaptureGate(_ledger(tmp_path))
    assert gate.is_granted("nobody") is False  # default-deny


def test_grant_then_revoke_flips_and_logs(tmp_path):
    ledger = _ledger(tmp_path)
    gate = CaptureGate(ledger)

    gate.grant("op-1", granted_by="anchor", scope_summary="benign synthetic docs")
    assert gate.is_granted("op-1") is True

    gate.revoke("op-1")
    assert gate.is_granted("op-1") is False

    kinds = [e.kind for e in ledger.translog.entries()]
    assert kinds.count(KIND_CAPTURE_ROLE_GRANTED) == 1
    assert kinds.count(KIND_CAPTURE_ROLE_REVOKED) == 1
    # The log still verifies after the grant + revoke entries.
    assert verify_log(ledger.translog._path).ok  # noqa: SLF001


def test_revoke_without_grant_raises(tmp_path):
    gate = CaptureGate(_ledger(tmp_path))
    with pytest.raises(CaptureGateError):
        gate.revoke("never-granted")


def test_grant_persists_scope_summary(tmp_path):
    gate = CaptureGate(_ledger(tmp_path))
    gate.grant("op-2", granted_by="anchor", scope_summary="only fixture targets")
    grant = gate.get_grant("op-2")
    assert grant is not None
    assert grant.scope_summary == "only fixture targets"
    assert grant.granted_by == "anchor"
    assert grant.active is True
