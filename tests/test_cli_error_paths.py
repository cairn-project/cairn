"""CLI error/exit-path + human-readable-output coverage.

These exercise the command bodies a skeptic would run to embarrass the suite:
the refusal exits (unsupported adapter, opt-in refused), the missing-ledger
guards on every public surface, and the non-JSON pretty-print branches. Every
assertion checks a REAL observable — the process exit code and the text the
command actually prints — against behaviour the engine guarantees, not a
tautology.

The pilot run seeds a complete real ledger (no pre-arranged state) that the
inspect / public commands then project over, so the human-readable branches run
against genuine recorded data.
"""

from __future__ import annotations

import json

import pytest

from cairn.cli import main


def _seed_pilot_ledger(tmp_path) -> str:
    """Run the real pilot into a fresh ledger dir; return that dir."""
    ledger_dir = str(tmp_path / "ledger")
    assert main(["pilot", "--ledger", ledger_dir, "--json"]) == 0
    return ledger_dir


# --- contribute refusal exits ------------------------------------------------


def test_contribute_unsupported_adapter_exits_2(capsys):
    rc = main(["contribute", "x", "--node", "n", "--adapter", "gpt4"])
    assert rc == 2
    assert "unsupported adapter" in capsys.readouterr().out


def test_contribute_opt_in_refused_on_unlisted_cause_exits_1(tmp_path, capsys):
    # A cause that was never approved is not publicly listable, so opt-in is
    # refused (the gate) and the command exits 1 with OPT-IN REFUSED.
    ledger_dir = str(tmp_path / "ledger")
    rc = main(
        [
            "contribute",
            "never-approved",
            "--node",
            "node-A",
            "--adapter",
            "mock",
            "--ledger",
            ledger_dir,
        ]
    )
    assert rc == 1
    assert "OPT-IN REFUSED" in capsys.readouterr().out


# --- public surfaces: missing ledger -> exit 1 -------------------------------


@pytest.mark.parametrize(
    "argv",
    [
        ["public", "causes"],
        ["public", "outcomes"],
        ["public", "verify-log"],
        ["public", "log"],
    ],
)
def test_public_surface_missing_ledger_exits_1(argv, tmp_path, capsys):
    missing = str(tmp_path / "does-not-exist")
    rc = main([*argv, "--ledger", missing])
    assert rc == 1
    assert "no ledger" in capsys.readouterr().out


# --- inspect -----------------------------------------------------------------


def test_inspect_missing_ledger_exits_1(tmp_path, capsys):
    rc = main(["inspect", str(tmp_path / "nope")])
    assert rc == 1
    assert "no ledger" in capsys.readouterr().out


def test_inspect_pilot_ledger_reports_real_counts(tmp_path, capsys):
    ledger_dir = _seed_pilot_ledger(tmp_path)
    capsys.readouterr()  # drop the pilot's own output

    rc = main(["inspect", ledger_dir, "--json"])
    assert rc == 0
    counts = json.loads(capsys.readouterr().out)
    # The pilot writes tasks, records results, and records at least one verdict;
    # these are real recorded artefacts, not zeros.
    assert counts["tasks"] >= 1
    assert counts["result_recorded"] >= 1
    assert counts["log_entries"] >= counts["result_recorded"]


def test_inspect_pretty_output_lists_each_count(tmp_path, capsys):
    ledger_dir = _seed_pilot_ledger(tmp_path)
    capsys.readouterr()

    rc = main(["inspect", ledger_dir])  # non-JSON pretty branch
    assert rc == 0
    out = capsys.readouterr().out
    for key in ("tasks", "claims", "results", "log_entries", "verdict_recorded"):
        assert key in out


# --- public surfaces over a real ledger (pretty branches) --------------------


def test_public_verify_log_ok_over_pilot_ledger(tmp_path, capsys):
    ledger_dir = _seed_pilot_ledger(tmp_path)
    capsys.readouterr()

    rc = main(["public", "verify-log", "--ledger", ledger_dir])
    assert rc == 0
    assert "OK length=" in capsys.readouterr().out


def test_public_log_pretty_over_pilot_ledger(tmp_path, capsys):
    ledger_dir = _seed_pilot_ledger(tmp_path)
    capsys.readouterr()

    rc = main(["public", "log", "--ledger", ledger_dir])  # non-JSON pretty branch
    assert rc == 0
    out = capsys.readouterr().out
    assert "public transparency log" in out


def test_public_causes_pretty_over_pilot_ledger(tmp_path, capsys):
    ledger_dir = _seed_pilot_ledger(tmp_path)
    capsys.readouterr()

    rc = main(["public", "causes", "--ledger", ledger_dir])  # non-JSON pretty branch
    assert rc == 0
    assert "published causes" in capsys.readouterr().out


# --- top-level: no subcommand prints help (friendly CLI), exits 0 -----------


def test_no_subcommand_prints_help_and_exits_0(capsys):
    # Bare `cairn` is the friendly-CLI convention: print the top-level help and
    # exit 0, rather than the argparse "required: command" usage error.
    rc = main([])
    assert rc == 0
    out = capsys.readouterr().out
    assert "usage: cairn" in out
    assert "pilot" in out


def test_version_flag_exits_0_and_prints_version(capsys):
    # `cairn --version` exits 0 via argparse's `version` action and prints the
    # installed package version, not a "required: command" error.
    from importlib.metadata import version as _pkg_version

    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert _pkg_version("cairn") in capsys.readouterr().out
