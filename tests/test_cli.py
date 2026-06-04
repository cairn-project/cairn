"""Tests: the thin cairn CLI.

Exercises the REAL CLI entry via subprocess (OUTCOME-ALTITUDE: no pre-arranged
state) and also via ``main()`` in-process for the verify-log OK/tamper paths.
Offline.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from cairn.cli import main

# src/ is on the path via pyproject pythonpath; point subprocess at it too.
_SRC = str(Path(__file__).resolve().parents[1] / "src")


def _run_cli(args, env_extra=None):
    import os

    env = dict(os.environ)
    env["PYTHONPATH"] = _SRC + os.pathsep + env.get("PYTHONPATH", "")
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-m", "cairn.cli", *args],
        capture_output=True,
        text=True,
        env=env,
    )


def test_cli_version_flag_exits_0_and_prints_package_version():
    # OUTCOME-ALTITUDE: real CLI entry, no pre-arranged state. `cairn --version`
    # is the literal first thing a curious dev types; it must succeed (exit 0)
    # and print the SAME version the installed package reports, not an argparse
    # "required: command" error.
    from importlib.metadata import version as _pkg_version

    expected = _pkg_version("cairn")
    proc = _run_cli(["--version"])
    assert proc.returncode == 0, proc.stderr
    assert expected in proc.stdout


def test_cli_short_version_flag_exits_0():
    proc = _run_cli(["-V"])
    assert proc.returncode == 0, proc.stderr
    from importlib.metadata import version as _pkg_version

    assert _pkg_version("cairn") in proc.stdout


def test_cli_no_args_prints_help_and_exits_0():
    # OUTCOME-ALTITUDE: bare `cairn` (no subcommand) is the friendly-CLI
    # convention — it prints top-level help and exits 0, instead of the
    # argparse "required: command" usage error (exit 2).
    proc = _run_cli([])
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout + proc.stderr
    assert "usage: cairn" in out
    # Help lists the subcommands a new user is looking for.
    assert "pilot" in out
    assert "verify-log" in out


def test_cli_pilot_runs_end_to_end_fresh(tmp_path):
    # OUTCOME-ALTITUDE: real CLI entry, fresh ledger dir, no pre-arranged state.
    ledger_dir = tmp_path / "ledger"
    proc = _run_cli(["pilot", "--ledger", str(ledger_dir)])
    assert proc.returncode == 0, proc.stderr
    assert "ACCEPTED" in proc.stdout
    assert "log head:" in proc.stdout
    # The pilot actually wrote a real, verifiable ledger to disk.
    assert (ledger_dir / "translog.jsonl").exists()


def test_cli_pilot_json_shape(tmp_path):
    ledger_dir = tmp_path / "ledger"
    proc = _run_cli(["pilot", "--ledger", str(ledger_dir), "--json"])
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["all_accepted"] is True
    assert payload["verdict_recorded"] == len(payload["units"])
    assert payload["log_head"]


def test_cli_verify_log_ok_and_tamper_fails(tmp_path):
    # Produce a real log via the pilot.
    ledger_dir = tmp_path / "ledger"
    assert main(["pilot", "--ledger", str(ledger_dir)]) == 0
    log_path = ledger_dir / "translog.jsonl"
    assert log_path.exists()

    # verify-log passes on the honest log (exit 0).
    assert main(["verify-log", str(log_path)]) == 0
    proc = _run_cli(["verify-log", str(log_path)])
    assert proc.returncode == 0
    assert proc.stdout.startswith("OK ")

    # Tamper a copy -> verify-log fails (nonzero) + names a failing index.
    tampered = tmp_path / "tampered.jsonl"
    lines = log_path.read_text().splitlines()
    lines[0] = lines[0].replace("result_key", "forged_key", 1)
    tampered.write_text("\n".join(lines) + "\n")

    assert main(["verify-log", str(tampered)]) == 1
    proc = _run_cli(["verify-log", str(tampered)])
    assert proc.returncode == 1
    assert "failed_index=" in proc.stdout


def test_cli_inspect_counts(tmp_path):
    ledger_dir = tmp_path / "ledger"
    assert main(["pilot", "--ledger", str(ledger_dir)]) == 0

    proc = _run_cli(["inspect", str(ledger_dir), "--json"])
    assert proc.returncode == 0, proc.stderr
    counts = json.loads(proc.stdout)
    assert counts["tasks"] >= 3
    assert counts["results"] >= 6  # >= 3 units x 2 nodes
    assert counts["verdict_recorded"] == counts["tasks"]
