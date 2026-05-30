"""cairn CLI — the thin command surface over the library (wave 5, BUILD-PLAN §34).

Three commands, no business logic of their own — each parses args, calls a library
function, prints, and maps to an exit code:

  cairn pilot [--ledger DIR] [--json]
      Run the benign pilot cause end-to-end on a fresh ledger (real backbone),
      print the run summary + the transparency-log head. Exit 0 on a clean run.

  cairn verify-log PATH
      Independently re-verify a transparency log via the real ``verify_log``.
      Prints OK + length + head on success (exit 0), or the first failing index +
      reason on failure (exit 1).

  cairn inspect LEDGER
      Count task / claim / result / verdict entries under a ledger dir and print
      them. Exit 0.

  cairn live-smoke [--ledger DIR] [--json] [--timeout S] [--model M]
      Run the benign pilot with ONE node driven by a real Claude model via the
      isolated subscription ``claude -p`` CLI (wave 6). This is the ONLY command
      that touches a real model — every other command stays fully offline. The
      spawn is isolated (``--strict-mcp-config`` + empty ``--mcp-config``) so it
      never loads plugins / steals the Telegram bot slot. Exit 0 on a clean run.

The ``pilot`` / ``verify-log`` / ``inspect`` commands are offline, stdlib-only
(argparse); ``live-smoke`` additionally spawns the isolated ``claude`` subprocess. ``FixedClock`` is used for the pilot so output is
reproducible; the HMAC signing key is a fixed non-secret CLI parameter (never a
checked-in production secret).
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Optional, Sequence

from .ledger import FixedClock, Ledger, verify_log
from .ledger.translog import KIND_RESULT_RECORDED, KIND_VERDICT_RECORDED, TransparencyLog
from .pilot import live_smoke, run_pilot

# Fixed, NON-SECRET signing key for the offline pilot/CLI demo. This is NOT a
# production secret — it is a public demo key so the attestation seam is exercised.
_DEMO_KEY = b"cairn-pilot-demo-key-not-secret"


def _cmd_pilot(args: argparse.Namespace) -> int:
    ledger_dir = Path(args.ledger) if args.ledger else Path(tempfile.mkdtemp(prefix="cairn-pilot-"))
    clock = FixedClock(start=0.0)
    ledger = Ledger(ledger_dir, clock, signing_key=_DEMO_KEY)

    summary = run_pilot(ledger, bad_family=args.bad_family)

    if args.json:
        out = summary.to_dict()
        out["ledger_dir"] = str(ledger_dir)
        print(json.dumps(out, indent=2, sort_keys=True))
    else:
        print(summary.pretty())
        print(f"ledger dir: {ledger_dir}")
    return 0


def _cmd_live_smoke(args: argparse.Namespace) -> int:
    ledger_dir = (
        Path(args.ledger)
        if args.ledger
        else Path(tempfile.mkdtemp(prefix="cairn-live-smoke-"))
    )
    # FixedClock for reproducible lease/claim timing; the live adapter stamps its
    # own REAL produced_at (real provenance) via its default wall clock.
    clock = FixedClock(start=0.0)
    ledger = Ledger(ledger_dir, clock, signing_key=_DEMO_KEY)

    summary = live_smoke(ledger, model=args.model, timeout=args.timeout)

    if args.json:
        out = summary.to_dict()
        out["ledger_dir"] = str(ledger_dir)
        print(json.dumps(out, indent=2, sort_keys=True))
    else:
        print("LIVE SMOKE — one node is a real Claude via isolated `claude -p`\n")
        print(summary.pretty())
        print(f"ledger dir: {ledger_dir}")
    return 0


def _cmd_verify_log(args: argparse.Namespace) -> int:
    result = verify_log(args.path)
    if result.ok:
        print(f"OK length={result.length} head={result.head_hash}")
        return 0
    print(
        f"FAIL failed_index={result.failed_index} reason={result.reason!r} "
        f"(verified {result.length} entries before failure)"
    )
    return 1


def _cmd_inspect(args: argparse.Namespace) -> int:
    root = Path(args.ledger)
    if not root.exists():
        print(f"no ledger at {root}")
        return 1

    tasks = _count_files(root / "tasks")
    claims = _count_files(root / "claims")
    results = sum(
        _count_files(d) for d in (root / "results").glob("*") if d.is_dir()
    )

    log_path = root / "translog.jsonl"
    result_recorded = verdict_recorded = 0
    log_entries = 0
    if log_path.exists():
        entries = TransparencyLog(log_path, FixedClock()).entries()
        log_entries = len(entries)
        result_recorded = sum(e.kind == KIND_RESULT_RECORDED for e in entries)
        verdict_recorded = sum(e.kind == KIND_VERDICT_RECORDED for e in entries)

    counts = {
        "tasks": tasks,
        "claims": claims,
        "results": results,
        "log_entries": log_entries,
        "result_recorded": result_recorded,
        "verdict_recorded": verdict_recorded,
    }
    if args.json:
        print(json.dumps(counts, indent=2, sort_keys=True))
    else:
        print(f"ledger: {root}")
        for k in ("tasks", "claims", "results", "log_entries",
                  "result_recorded", "verdict_recorded"):
            print(f"  {k}: {counts[k]}")
    return 0


def _count_files(directory: Path) -> int:
    if not directory.exists():
        return 0
    return sum(1 for p in directory.iterdir() if p.is_file())


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cairn",
        description="cairn — distributed cause-coordination engine CLI.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_pilot = sub.add_parser(
        "pilot", help="run the benign pilot cause end-to-end on a fresh ledger"
    )
    p_pilot.add_argument(
        "--ledger", default=None, help="ledger directory (default: a temp dir)"
    )
    p_pilot.add_argument(
        "--bad-family",
        dest="bad_family",
        default=None,
        help="run this model family as a faulty node on the honeypot unit",
    )
    p_pilot.add_argument("--json", action="store_true", help="emit JSON summary")
    p_pilot.set_defaults(func=_cmd_pilot)

    p_live = sub.add_parser(
        "live-smoke",
        help="run the benign pilot with one real Claude node (isolated claude -p)",
    )
    p_live.add_argument(
        "--ledger", default=None, help="ledger directory (default: a temp dir)"
    )
    p_live.add_argument(
        "--model", default="sonnet", help="subscription model tier (default: sonnet)"
    )
    p_live.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="per-call claude -p subprocess timeout in seconds (default: 120)",
    )
    p_live.add_argument("--json", action="store_true", help="emit JSON summary")
    p_live.set_defaults(func=_cmd_live_smoke)

    p_verify = sub.add_parser(
        "verify-log", help="independently re-verify a transparency log"
    )
    p_verify.add_argument("path", help="path to the translog.jsonl file")
    p_verify.set_defaults(func=_cmd_verify_log)

    p_inspect = sub.add_parser(
        "inspect", help="count task/claim/result/verdict entries in a ledger dir"
    )
    p_inspect.add_argument("ledger", help="ledger directory")
    p_inspect.add_argument("--json", action="store_true", help="emit JSON counts")
    p_inspect.set_defaults(func=_cmd_inspect)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
