"""Wave-5 tests: run_pilot drives the REAL backbone end-to-end (BUILD-PLAN §35).

OUTCOME-ALTITUDE: invokes the real production runner on a FRESH ledger with no
pre-arranged verdict/result/claim state. Offline.
"""

from __future__ import annotations

from cairn.ledger import FixedClock, Ledger, verify_log
from cairn.pilot import run_pilot, unit_task_id

_KEY = b"pilot-runner-test-key"


def _fresh_ledger(tmp_path):
    return Ledger(tmp_path, FixedClock(start=0.0), signing_key=_KEY)


def test_run_pilot_reaches_accepted_with_diversity(tmp_path):
    # OUTCOME-ALTITUDE: fresh ledger, real backbone, two distinct honest families.
    ledger = _fresh_ledger(tmp_path)
    summary = run_pilot(ledger, node_families=["claude", "gpt"])

    assert summary.units, "pilot produced no units"
    assert summary.all_accepted, [u.to_dict() for u in summary.units]
    for u in summary.units:
        assert u.accepted
        # diversity satisfied: the winning cluster spans >= 2 distinct families.
        assert len(u.model_families_in_quorum) >= 2, u.to_dict()

    # The real transparency log is consistent and independently verifiable.
    assert summary.verdict_recorded == len(summary.units)
    assert summary.result_recorded == len(summary.units) * 2  # 2 nodes per unit
    v = verify_log(tmp_path / "translog.jsonl")
    assert v.ok is True
    assert v.head_hash == summary.log_head


def test_run_pilot_honeypot_catches_bad_node(tmp_path):
    ledger = _fresh_ledger(tmp_path)
    summary = run_pilot(
        ledger, node_families=["claude", "gpt"], bad_family="gpt"
    )

    # The bad node is caught on the honeypot (seeded) unit, regardless of peer
    # agreement — PLAN §3.5 L4.
    assert summary.total_honeypot_catches >= 1
    hp_units = [u for u in summary.units if u.honeypot_catches]
    assert hp_units, "no unit reported a honeypot catch"
    assert any("node-gpt" in u.honeypot_catches for u in hp_units)


def test_run_pilot_log_independently_verifies_and_counts(tmp_path):
    ledger = _fresh_ledger(tmp_path)
    summary = run_pilot(ledger, node_families=["claude", "gpt", "gemini"])

    # 3 nodes per unit now.
    assert summary.result_recorded == len(summary.units) * 3
    assert summary.verdict_recorded == len(summary.units)
    assert verify_log(tmp_path / "translog.jsonl").ok is True

    # Reputation was earned + persisted on the real ledger.
    assert summary.reputation  # consensus + honeypot deltas accumulated
