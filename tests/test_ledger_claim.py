"""Atomic claim + lease-expiry tests.

The atomic O_EXCL claim makes double-claim impossible; an expired lease reopens
the unit. Time is an injected FixedClock so the lease behaviour is deterministic.
"""

from __future__ import annotations

import threading

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


def _race_claim(reg, task_id, n_threads, lease_seconds):
    """Run n_threads concurrent claims of one task; return (winners, errors).

    A barrier releases all threads as close to simultaneously as possible to
    maximise contention on the underlying create/replace.
    """
    barrier = threading.Barrier(n_threads)
    winners: list[str] = []
    errors: list[Exception] = []
    lock = threading.Lock()

    def worker(node_id: str) -> None:
        barrier.wait()
        try:
            claim = reg.claim(task_id, node_id=node_id, lease_seconds=lease_seconds)
        except ClaimError as exc:  # noqa: PERF203 - branch is the point of the test
            with lock:
                errors.append(exc)
        else:
            with lock:
                winners.append(claim.node_id)

    threads = [threading.Thread(target=worker, args=(f"node-{i}",)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return winners, errors


def test_concurrent_fresh_claim_has_exactly_one_winner(tmp_path):
    # N threads race to claim ONE fresh task. O_EXCL must admit exactly one
    # winner; every other thread gets a ClaimError.
    clock = FixedClock(start=0.0)
    reg = ClaimRegistry(tmp_path, clock)

    n = 16
    winners, errors = _race_claim(reg, "hot-task", n_threads=n, lease_seconds=60)

    assert len(winners) == 1, f"expected exactly one winner, got {winners}"
    assert len(errors) == n - 1
    # The surviving claim on disk is the sole winner's.
    active = reg.active_claim("hot-task")
    assert active is not None and active.node_id == winners[0]


def test_concurrent_expired_reclaim_has_exactly_one_winner(tmp_path):
    # An expired lease exists on disk; N threads race to RECLAIM it. This drives
    # the detect-and-retry path (O_EXCL fails -> os.replace + claim_id confirm),
    # including the lost-race branch where a thread's os.replace is overwritten
    # and its claim_id no longer matches. Exactly one reclaimer must win.
    clock = FixedClock(start=1000.0)
    reg = ClaimRegistry(tmp_path, clock)

    # Seed an expired claim so the file already exists when the race begins.
    reg.claim("stale-task", node_id="vanished", lease_seconds=10)
    clock.advance(11)  # now 1011 >= 1000 + 10 -> expired
    assert reg.active_claim("stale-task") is None

    n = 16
    winners, errors = _race_claim(reg, "stale-task", n_threads=n, lease_seconds=60)

    assert len(winners) == 1, f"expected exactly one reclaim winner, got {winners}"
    assert len(errors) == n - 1
    active = reg.active_claim("stale-task")
    assert active is not None and active.node_id == winners[0]
