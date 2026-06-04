"""Cause-layer tests: the cause CLI commands.

Exercises the REAL CLI entry via subprocess (OUTCOME-ALTITUDE: fresh ledger dir,
no pre-arranged state) and via ``main()`` in-process. Offline.
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


def _run_cli(args):
    env = dict(os.environ)
    env["PYTHONPATH"] = _SRC + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "cairn.cli", *args],
        capture_output=True,
        text=True,
        env=env,
    )


def _request_id(ledger_dir):
    proc = _run_cli(["cause-request", _BENIGN_DRAFT, "--ledger", str(ledger_dir), "--json"])
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)["cause_id"], proc


def test_cli_cause_request_not_listed_until_approved(tmp_path):
    ledger_dir = tmp_path / "ledger"
    cause_id, req = _request_id(ledger_dir)
    assert cause_id
    # The requested cause is NOT in the public causes list yet (the gate).
    proc = _run_cli(["causes", "--ledger", str(ledger_dir), "--json"])
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout) == []


def test_cli_cause_approve_then_listed(tmp_path):
    ledger_dir = tmp_path / "ledger"
    cause_id, _ = _request_id(ledger_dir)
    frames = []
    for f in (
        "works",
        "doesnt_target_good_people",
        "legal",
        "court_grade_auditable",
        "human_verified",
    ):
        frames += ["--frame-pass", f]
    proc = _run_cli(
        [
            "cause-decide",
            cause_id,
            "--approve",
            "--reason",
            "benign; passes all five frames",
            "--by",
            "anchor",
            "--ledger",
            str(ledger_dir),
            *frames,
        ]
    )
    assert proc.returncode == 0, proc.stderr
    # Now it shows up in the public list.
    proc = _run_cli(["causes", "--ledger", str(ledger_dir), "--json"])
    rows = json.loads(proc.stdout)
    assert [r["cause_id"] for r in rows] == [cause_id]
    assert rows[0]["listable"] is True


def test_cli_cause_reject_stays_unlisted_and_log_verifies(tmp_path):
    ledger_dir = tmp_path / "ledger"
    cause_id, _ = _request_id(ledger_dir)
    frames = []
    for f in (
        "works",
        "doesnt_target_good_people",
        "legal",
        "court_grade_auditable",
        "human_verified",
    ):
        frames += ["--frame-pass", f]
    proc = _run_cli(
        [
            "cause-decide",
            cause_id,
            "--reject",
            "--reason",
            "rejected for the record",
            "--by",
            "anchor",
            "--ledger",
            str(ledger_dir),
            *frames,
        ]
    )
    assert proc.returncode == 0, proc.stderr
    # Rejected cause stays out of the public list.
    proc = _run_cli(["causes", "--ledger", str(ledger_dir), "--json"])
    assert json.loads(proc.stdout) == []
    # The reasoned decision is on a verifiable transparency log.
    log_path = ledger_dir / "translog.jsonl"
    assert main(["verify-log", str(log_path)]) == 0


def test_cli_cause_decide_empty_reason_fails(tmp_path):
    ledger_dir = tmp_path / "ledger"
    cause_id, _ = _request_id(ledger_dir)
    frames = []
    for f in (
        "works",
        "doesnt_target_good_people",
        "legal",
        "court_grade_auditable",
        "human_verified",
    ):
        frames += ["--frame-pass", f]
    proc = _run_cli(
        [
            "cause-decide",
            cause_id,
            "--approve",
            "--reason",
            "  ",
            "--by",
            "anchor",
            "--ledger",
            str(ledger_dir),
            *frames,
        ]
    )
    assert proc.returncode == 1  # no silent decision
    assert "DECISION REJECTED" in proc.stdout


def test_cli_cause_decide_unknown_frame_fails(tmp_path):
    # The CLI always addresses all five frames (unnamed default to fail), so the
    # gate structure is complete by construction; the surface guards against an
    # UNKNOWN frame key (a typo) rather than letting it slip silently.
    ledger_dir = tmp_path / "ledger"
    cause_id, _ = _request_id(ledger_dir)
    proc = _run_cli(
        [
            "cause-decide",
            cause_id,
            "--approve",
            "--reason",
            "ok",
            "--by",
            "anchor",
            "--ledger",
            str(ledger_dir),
            "--frame-pass",
            "not_a_real_frame",
        ]
    )
    assert proc.returncode == 2  # unknown frame rejected
    assert "unknown frame" in proc.stdout


def test_cli_outcome_altitude_request_decide_list_subprocess(tmp_path):
    # OUTCOME-ALTITUDE: full request→decide→list flow via the real CLI subprocess.
    ledger_dir = tmp_path / "ledger"
    cause_id, _ = _request_id(ledger_dir)
    frames = []
    for f in (
        "works",
        "doesnt_target_good_people",
        "legal",
        "court_grade_auditable",
        "human_verified",
    ):
        frames += ["--frame-pass", f]
    assert (
        _run_cli(
            [
                "cause-decide",
                cause_id,
                "--approve",
                "--reason",
                "ok",
                "--by",
                "anchor",
                "--ledger",
                str(ledger_dir),
                *frames,
            ]
        ).returncode
        == 0
    )
    proc = _run_cli(["causes", "--ledger", str(ledger_dir)])
    assert proc.returncode == 0
    assert cause_id[:12] in proc.stdout
