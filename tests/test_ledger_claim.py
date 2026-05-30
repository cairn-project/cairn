"""Atomic claim + lease-expiry tests (BUILD-PLAN §25.2-3, PLAN §3.1).

The atomic O_EXCL claim makes double-claim impossible; an expired lease reopens
the unit. Time is an injected FixedClock so the lease behaviour is deterministic.
"""

from __future__ import annotations

import pytest

from cairn.ledger import ClaimError, ClaimRegistry, FixedClock


def test_atomic_claim_rejects_double_claim(tmp_path):
    clock = FixedClock(start=100.0)
    reg = ClaimRegistry(tmp_path, clock)

    first = reg.claim("task-1", node_id="node-A", lease_seconds=60)
    assert first.node_id == "node-A"

    # A second claim of the SAME unexpired task is structurally rejected.
    with pytest.raises(ClaimError):
        reg.claim("task-1", node_id="node-B", lease_seconds=60)

    # The active claim is still node-A's.
    active = reg.active_claim("task-1")
    assert active is not None and active.node_id == "node-A"


def test_distinct_tasks_claim_independently(tmp_path):
    clock = FixedClock(start=0.0)
    reg = ClaimRegistry(tmp_path, clock)
    a = reg.claim("task-a", "node-A", lease_seconds=10)
    b = reg.claim("task-b", "node-B", lease_seconds=10)
    assert a.task_id == "task-a" and b.task_id == "task-b"


def test_lease_expiry_reopens_unit(tmp_path):
    clock = FixedClock(start=1000.0)
    reg = ClaimRegistry(tmp_path, clock)

    reg.claim("task-x", node_id="vanished-node", lease_seconds=30)

    # Before expiry: claim is active and re-claim is rejected.
    assert reg.active_claim("task-x") is not None
    with pytest.raises(ClaimError):
        reg.claim("task-x", node_id="fresh-node", lease_seconds=30)

    # Advance past the lease: the vanished node's claim expires.
    clock.advance(31)  # now 1031 >= 1000 + 30

    # The unit is reopened: active_claim is None and a fresh node can claim it.
    assert reg.active_claim("task-x") is None
    reclaim = reg.claim("task-x", node_id="fresh-node", lease_seconds=30)
    assert reclaim.node_id == "fresh-node"
    assert reg.active_claim("task-x").node_id == "fresh-node"


def test_release_by_holder_reopens(tmp_path):
    clock = FixedClock(start=0.0)
    reg = ClaimRegistry(tmp_path, clock)
    c = reg.claim("task-r", "node-A", lease_seconds=100)

    # A non-holder cannot release.
    assert reg.release("task-r", claim_id="wrong-id") is False
    assert reg.active_claim("task-r") is not None

    # The holder can; the unit reopens.
    assert reg.release("task-r", claim_id=c.claim_id) is True
    assert reg.active_claim("task-r") is None
    reg.claim("task-r", "node-B", lease_seconds=100)  # now claimable
