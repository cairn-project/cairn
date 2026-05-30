"""Transparency-log tests (BUILD-PLAN §25.4, PLAN §3.6 + REQUIREMENTS Frame 4).

THE LOAD-BEARING TEST OF THE WAVE: the transparency guarantee is only real if an
independent monitor (verify_log) DETECTS tampering — a flipped byte, a removed
entry, or a reordered entry must all break verification. Also covers the dual-use
property (one chain carries both detection-audit and cause-governance entries).
"""

from __future__ import annotations

from cairn.ledger import (
    KIND_CAUSE_DECISION,
    KIND_RESULT_RECORDED,
    FixedClock,
    TransparencyLog,
    verify_log,
)


def _seed_log(path, clock):
    log = TransparencyLog(path, clock)
    log.append(KIND_RESULT_RECORDED, {"task_id": "t1", "result_key": "aaa"})
    log.append(KIND_CAUSE_DECISION, {"cause_id": "c1", "decision": "approved",
                                     "reason": "meets criteria"})
    log.append(KIND_RESULT_RECORDED, {"task_id": "t2", "result_key": "bbb"})
    return log


def test_append_and_independent_verify_ok(tmp_path):
    path = tmp_path / "translog.jsonl"
    log = _seed_log(path, FixedClock())
    assert len(log.entries()) == 3

    v = verify_log(path)
    assert v.ok is True
    assert v.length == 3
    assert v.head_hash == log.head_hash()


def test_dual_use_entries_both_verify(tmp_path):
    """One chain carries detection-audit AND cause-governance entries (PLAN §3.6)."""
    path = tmp_path / "translog.jsonl"
    log = _seed_log(path, FixedClock())
    kinds = {e.kind for e in log.entries()}
    assert KIND_RESULT_RECORDED in kinds  # detection auditability (Frame 4)
    assert KIND_CAUSE_DECISION in kinds  # cause-governance no-silent-rejection
    assert verify_log(path).ok is True


def test_tamper_flipped_byte_detected(tmp_path):
    """Flip ONE byte in a payload => verify_log fails at that entry."""
    path = tmp_path / "translog.jsonl"
    _seed_log(path, FixedClock())
    assert verify_log(path).ok is True

    lines = path.read_text().splitlines()
    # Corrupt the middle entry's payload (change "approved" -> "approvee").
    assert "approved" in lines[1]
    lines[1] = lines[1].replace("approved", "approvee", 1)
    path.write_text("\n".join(lines) + "\n")

    v = verify_log(path)
    assert v.ok is False
    assert v.failed_index == 1


def test_tamper_removed_entry_detected(tmp_path):
    """Delete an entry => the index gap / broken chain is detected."""
    path = tmp_path / "translog.jsonl"
    _seed_log(path, FixedClock())

    lines = path.read_text().splitlines()
    del lines[1]  # remove the middle entry
    path.write_text("\n".join(lines) + "\n")

    v = verify_log(path)
    assert v.ok is False
    assert v.failed_index == 1


def test_tamper_reordered_entries_detected(tmp_path):
    """Swap two entries => the prev_hash chain / index order breaks."""
    path = tmp_path / "translog.jsonl"
    _seed_log(path, FixedClock())

    lines = path.read_text().splitlines()
    lines[1], lines[2] = lines[2], lines[1]  # reorder
    path.write_text("\n".join(lines) + "\n")

    v = verify_log(path)
    assert v.ok is False


def test_tamper_appended_forged_entry_detected(tmp_path):
    """Append an entry with a hand-forged hash => recomputation catches it."""
    path = tmp_path / "translog.jsonl"
    _seed_log(path, FixedClock())

    forged = (
        '{"entry_hash": "deadbeef", "index": 3, "kind": "RESULT_RECORDED", '
        '"payload": {"task_id": "t9"}, "prev_hash": "00", "recorded_at": 0.0}'
    )
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(forged + "\n")

    v = verify_log(path)
    assert v.ok is False
    assert v.failed_index == 3
