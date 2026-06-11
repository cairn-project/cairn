"""CLI tests for the documented `cairn scenario` flow.

OUTCOME-ALTITUDE: exercises the QUICKSTART value-demo flow exactly as a cold
user runs it — `scenario run --offline` → `scenario list` → `scenario review`
fed the TRUNCATED hash the human `list` output prints — via subprocess on a
fresh ledger, no pre-arranged state. This is the flow that used to dead-end in
"REVIEW REFUSED" because `review` demanded the full 64-char hash while `run`
printed 12 chars and `list` printed 16. Offline.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[1] / "src")

# the human-readable `scenario list` line: "  pending   <16-char hash prefix>"
_LIST_LINE = re.compile(r"^\s+(?P<state>\S+)\s+(?P<hash>[0-9a-f]{16})\s*$")


def _run_cli(args):
    env = dict(os.environ)
    env["PYTHONPATH"] = _SRC + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "cairn.cli", *args],
        capture_output=True,
        text=True,
        env=env,
    )


def test_documented_scenario_flow_with_the_hash_list_prints(tmp_path):
    ledger = str(tmp_path / "ledger")
    review_dir = str(tmp_path / "review")

    # 1. `cairn scenario run --offline` (QUICKSTART verbatim, hermetic).
    proc = _run_cli(
        ["scenario", "run", "--offline", "--ledger", ledger, "--review-dir", review_dir]
    )
    assert proc.returncode == 0, proc.stderr

    # 2. `cairn scenario list` — take the truncated hash from the HUMAN output.
    proc = _run_cli(["scenario", "list", "--ledger", ledger])
    assert proc.returncode == 0, proc.stderr
    shown = [m.group("hash") for m in map(_LIST_LINE.match, proc.stdout.splitlines()) if m]
    assert shown, f"no finding lines parsed from:\n{proc.stdout}"

    # 3. `cairn scenario review <finding_hash>` with the printed truncated hash.
    proc = _run_cli(
        [
            "scenario",
            "review",
            shown[0],
            "--routable",
            "--reason",
            "verified benign",
            "--by",
            "reviewer",
            "--ledger",
            ledger,
        ]
    )
    assert proc.returncode == 0, f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
    assert "recorded ROUTABLE verdict" in proc.stdout
    # the confirmation names the FULL resolved hash, not the prefix.
    full = re.search(r"verdict for ([0-9a-f]{64})", proc.stdout)
    assert full is not None, proc.stdout
    assert full.group(1).startswith(shown[0])

    # 4. the gate state really flipped (machine-readable check).
    proc = _run_cli(["scenario", "list", "--ledger", ledger, "--json"])
    assert proc.returncode == 0, proc.stderr
    rows = {r["finding_hash"]: r["state"] for r in json.loads(proc.stdout)}
    assert rows[full.group(1)] == "routable"


def test_scenario_review_still_refuses_garbage_hash(tmp_path):
    ledger = str(tmp_path / "ledger")
    proc = _run_cli(
        ["scenario", "run", "--offline", "--ledger", ledger, "--review-dir", str(tmp_path / "r")]
    )
    assert proc.returncode == 0, proc.stderr

    proc = _run_cli(
        [
            "scenario",
            "review",
            "deadbeef0000",
            "--routable",
            "--reason",
            "x",
            "--by",
            "reviewer",
            "--ledger",
            ledger,
        ]
    )
    assert proc.returncode == 1
    assert "REVIEW REFUSED" in proc.stdout
