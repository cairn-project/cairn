"""CLI wiring for the `cairn public...` read-surfaces.

Drives the real ``cairn.cli.main`` over a populated ledger dir. Read-only: every
subcommand returns exit 0 on a clean read; the public verify-log returns exit 1 on
a tampered log. Offline, deterministic.
"""

from __future__ import annotations

import json

from cairn.cause import CauseRegistry, five_frame_gate_check
from cairn.cause.model import FRAME_KEYS
from cairn.cli import main
from cairn.ledger import FixedClock, Ledger
from cairn.vetting import AutomatedVerdict, FindingVetQueue

_KEY = b"cairn-pilot-demo-key-not-secret"


def _populate(ledger_dir):
    ledger = Ledger(ledger_dir, FixedClock(start=0.0), signing_key=_KEY)
    reg = CauseRegistry(ledger)
    queue = FindingVetQueue(ledger)
    draft = {
        "name": "cli-cause",
        "description": "a generic, mission-neutral cause",
        "target_conduct": "publicly-observable conduct",
        "protected_boundary": "no persons profiled",
        "output_schema_ref": "result_v0",
        "partner_of_record_posture": "maintainer is actor-of-record",
        "created_by": "req",
        "five_frame": {
            k: {"frame": k, "claim": f"{k} ok", "passes": True} for k in FRAME_KEYS
        },
    }
    cause = reg.submit_cause_request(draft)
    reg.decide_cause(cause.cause_id, approve=True, reason="ok", decider="anchor",
                     gate_result=five_frame_gate_check({k: True for k in FRAME_KEYS}))
    av = AutomatedVerdict(flag_label="flagged", confidence=0.9)
    finding = queue.flag(packet_hash="ab" * 32, automated_verdict=av,
                         flagged_by="node-1")
    queue.record_verdict(finding.finding_hash, routable=True, reason="ok",
                         reviewer_id="rev-1")
    return ledger


def test_public_causes_cli(tmp_path, capsys):
    _populate(tmp_path / "ledger")
    rc = main(["public", "causes", "--ledger", str(tmp_path / "ledger"), "--json"])
    assert rc == 0
    rows = json.loads(capsys.readouterr().out)
    assert len(rows) == 1
    assert rows[0]["name"] == "cli-cause"
    assert "decision_reason" not in rows[0]


def test_public_outcomes_cli_redacted(tmp_path, capsys):
    _populate(tmp_path / "ledger")
    rc = main(["public", "outcomes", "--ledger", str(tmp_path / "ledger"), "--json"])
    assert rc == 0
    rows = json.loads(capsys.readouterr().out)
    assert len(rows) == 1
    assert set(rows[0]) == {
        "packet_hash", "flag_label", "verdict", "reviewer_of_record", "decided_at",
    }
    assert rows[0]["verdict"] == "routable"


def test_public_log_cli_skeleton(tmp_path, capsys):
    _populate(tmp_path / "ledger")
    rc = main(["public", "log", "--ledger", str(tmp_path / "ledger"), "--json"])
    assert rc == 0
    rows = json.loads(capsys.readouterr().out)
    assert rows
    for r in rows:
        assert set(r) == {"index", "kind", "entry_hash", "prev_hash", "recorded_at"}


def test_public_verify_log_cli_ok_then_tampered(tmp_path, capsys):
    ledger = _populate(tmp_path / "ledger")
    rc = main(["public", "verify-log", "--ledger", str(tmp_path / "ledger")])
    assert rc == 0
    assert "OK" in capsys.readouterr().out

    log_path = ledger.translog._path  # noqa: SLF001
    lines = log_path.read_text(encoding="utf-8").splitlines()
    lines[0] = lines[0].replace("CAUSE_REQUEST", "CAUSE_DEXISION")
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    rc2 = main(["public", "verify-log", "--ledger", str(tmp_path / "ledger")])
    assert rc2 == 1
    assert "FAIL" in capsys.readouterr().out


def test_public_missing_ledger_reports_error(tmp_path, capsys):
    rc = main(["public", "causes", "--ledger", str(tmp_path / "nope"), "--json"])
    assert rc == 1
    assert "no ledger" in capsys.readouterr().out
