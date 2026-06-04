"""Smoke test for examples/demo.sh — the one-command end-to-end cause demo.

OUTCOME-ALTITUDE: runs the real shipped script as a stranger would (from the
repo root, no pre-arranged state), and asserts the full chain reached its
verifiable end-state. Offline: the demo spawns no network and no model.

The script invokes the installed ``cairn`` console command; we run it with the
test's own Python on PATH so a `cairn` entry point resolved from this venv is
found even when the repo has no ``.venv/`` (e.g. in CI).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_DEMO = _ROOT / "examples" / "demo.sh"


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
def test_demo_script_runs_full_cause_loop():
    # Put the directory holding THIS interpreter (and its console scripts, incl.
    # `cairn`) at the front of PATH, so the script's `command -v cairn` fallback
    # resolves to this environment's entry point even without a repo .venv/.
    bindir = str(Path(sys.executable).parent)
    env = dict(os.environ)
    env["PATH"] = bindir + os.pathsep + env.get("PATH", "")

    proc = subprocess.run(
        ["bash", str(_DEMO)],
        cwd=str(_ROOT),
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )

    assert proc.returncode == 0, f"demo failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    out = proc.stdout

    # The cause was requested, approved (listable), contributed to, and verified.
    assert "request the benign cause" in out
    assert "now publicly listable: True" in out
    assert "units accepted: 4/4" in out
    assert "published causes (approved/live only): 1" in out
    # The transparency log independently re-verifies OK.
    assert "OK length=" in out
    assert "demo complete" in out
