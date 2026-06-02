"""CLI tests for `cairn contribute`.

Exercises the REAL CLI: the outcome-altitude e2e runs via subprocess (fresh
ledger dir, no pre-arranged state) — submit→approve a benign cause, then
contribute (opt in + run) and verify the transparency log. Offline.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from cairn.cli import main

_SRC = str(Path(__file__).resolve().parents[1] / "src")
_BENIGN_DRAFT = _SRC + "/cairn/fixtures/cause_draft_benign.json"
_FRAMES = (
    "works",
    "doesnt_target_good_people",
    "legal",
    "court_grade_auditable",
    "human_verified",
)


def _run_cli(args):
    env = dict(os.environ)
    env["PYTHONPATH"] = _SRC + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "cairn.cli", *args],
        capture_output=True, text=True, env=env,
    )


def _request_id(ledger_dir):
    proc = _run_cli(["cause-request", _BENIGN_DRAFT, "--ledger", str(ledger_dir),
                     "--json"])
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)["cause_id"]


def _approve(ledger_dir, cause_id):
    frames = []
    for f in _FRAMES:
        frames += ["--frame-pass", f]
    proc = _run_cli([
        "cause-decide", cause_id, "--approve", "--reason",
        "benign; passes all five frames", "--by", "anchor",
        "--ledger", str(ledger_dir), *frames,
    ])
    assert proc.returncode == 0, proc.stderr


def test_contribute_refused_for_unapproved_cause(tmp_path):
    ledger_dir = tmp_path / "ledger"
    cause_id = _request_id(ledger_dir)  # requested, NOT approved
    proc = _run_cli(["contribute", cause_id, "--ledger", str(ledger_dir)])
    assert proc.returncode == 1 # the gate refuses opt-in
    assert "REFUSED" in proc.stdout


def test_contribute_unsupported_adapter_exits_2(tmp_path):
    ledger_dir = tmp_path / "ledger"
    cause_id = _request_id(ledger_dir)
    _approve(ledger_dir, cause_id)
    proc = _run_cli([
        "contribute", cause_id, "--adapter", "notmock", "--ledger", str(ledger_dir)
    ])
    assert proc.returncode == 2
    assert "adapter" in proc.stdout.lower()


def test_contribute_outcome_altitude_e2e_subprocess(tmp_path):
    # OUTCOME-ALTITUDE: full submit→approve→contribute(opt-in + run)→verify via
    # the REAL CLI subprocess, fresh ledger, no pre-arranged state.
    ledger_dir = tmp_path / "ledger"
    cause_id = _request_id(ledger_dir)
    _approve(ledger_dir, cause_id)

    proc = _run_cli([
        "contribute", cause_id, "--adapter", "mock", "--node", "vol-1",
        "--ledger", str(ledger_dir), "--json",
    ])
    assert proc.returncode == 0, proc.stderr
    summary = json.loads(proc.stdout)
    assert summary["cause_id"] == cause_id
    assert summary["all_accepted"] is True
    assert summary["result_recorded"] > 0 and summary["verdict_recorded"] > 0

    # The produced transparency log independently verifies via the real CLI.
    log_path = ledger_dir / "translog.jsonl"
    assert main(["verify-log", str(log_path)]) == 0
