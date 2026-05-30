"""End-to-end ledger test (BUILD-PLAN §25.7, OUTCOME-ALTITUDE).

Invokes the full wave-1..4 pipeline on a fresh ledger with NO pre-arranged state:
define_task -> claim_task -> run_work_unit (MockAdapter) x N -> store_result
(blob + attestation + RESULT_RECORDED log entry) -> verify_unit -> record_verdict
-> verify_log. Fully offline.
"""

from __future__ import annotations

from dataclasses import replace

from cairn import load_fixture
from cairn.execute import MockAdapter, run_work_unit
from cairn.ledger import (
    KIND_RESULT_RECORDED,
    KIND_VERDICT_RECORDED,
    FixedClock,
    Ledger,
    verify_log,
)
from cairn.types import RedundancyPolicy
from cairn.verify import verify_unit

_KEY = b"e2e-test-signing-key"


def test_define_claim_execute_store_verify_log(tmp_path):
    clock = FixedClock(start=0.0)
    ledger = Ledger(tmp_path, clock, signing_key=_KEY)

    # 1. DEFINE — content-address the unit under tasks/.
    unit_dict = load_fixture("benign_pilot")
    task_id = ledger.define_task(unit_dict)
    assert ledger.get_task(task_id)["task_id"] == task_id

    # 2. CLAIM — atomic exclusive claim.
    claim = ledger.claim_task(task_id, node_id="node-A", lease_seconds=120)
    assert claim.task_id == task_id

    # 3. EXECUTE — produce a real candidate via the wave-2 flow (MockAdapter),
    #    then form N diverse-family candidates so the wave-3 diversity gate is met.
    outcome = run_work_unit(unit_dict, MockAdapter())
    assert outcome.candidate is not None
    base = outcome.candidate
    candidates = [
        replace(base, adapter_name="node-A", model_family="claude"),
        replace(base, adapter_name="node-B", model_family="gpt"),
    ]

    # 4. STORE — each result becomes a blob + real attestation + a RESULT_RECORDED
    #    transparency entry.
    for cand in candidates:
        ledger.store_result(cand)

    # 5. VERIFY — wave-3 trust decision over the stored candidates. The ledger does
    #    NOT decide truth; verify_unit does.
    policy = RedundancyPolicy.from_dict(unit_dict["redundancy_policy"])
    verdict = verify_unit(
        candidates, policy, reputation=ledger.reputation, unit_task_id=task_id
    )
    assert verdict.accepted  # 2 agreeing distinct families -> ACCEPTED

    # 6. RECORD the verdict in the transparency log.
    ledger.record_verdict(task_id, verdict)

    # 7. The independent monitor verifies the whole chain.
    v = verify_log(tmp_path / "translog.jsonl")
    assert v.ok is True

    kinds = [e.kind for e in ledger.translog.entries()]
    assert kinds.count(KIND_RESULT_RECORDED) == 2
    assert kinds.count(KIND_VERDICT_RECORDED) == 1

    # Reputation was earned + persisted on the ledger (survives a reload).
    from cairn.ledger import LedgerReputation

    reloaded = LedgerReputation(tmp_path / "reputation.jsonl")
    assert reloaded.known_subjects()  # consensus deltas were persisted


def test_e2e_tamper_after_recording_is_detected(tmp_path):
    """A retroactive edit to the recorded log AFTER an honest run is detected."""
    clock = FixedClock(start=0.0)
    ledger = Ledger(tmp_path, clock, signing_key=_KEY)
    unit_dict = load_fixture("benign_pilot")
    task_id = ledger.define_task(unit_dict)
    ledger.claim_task(task_id, "node-A", lease_seconds=60)
    outcome = run_work_unit(unit_dict, MockAdapter())
    ledger.store_result(replace(outcome.candidate, model_family="claude"))

    log_path = tmp_path / "translog.jsonl"
    assert verify_log(log_path).ok is True

    # Tamper with the recorded result key after the fact.
    lines = log_path.read_text().splitlines()
    lines[0] = lines[0].replace("result_key", "forged_key", 1)
    log_path.write_text("\n".join(lines) + "\n")
    assert verify_log(log_path).ok is False
