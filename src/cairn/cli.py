"""cairn CLI — the thin command surface over the library.

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
      isolated ``claude -p`` CLI. This is the ONLY command
      that touches a real model — every other command stays fully offline. The
      spawn is isolated (``--strict-mcp-config`` + empty ``--mcp-config``) so it
      loads no MCP servers or plugins from the caller's environment. Exit 0 on a clean run.

The ``pilot`` / ``verify-log`` / ``inspect`` commands are offline, stdlib-only
(argparse); ``live-smoke`` additionally spawns the isolated ``claude`` subprocess. ``FixedClock`` is used for the pilot so output is
reproducible; the HMAC signing key is a fixed non-secret CLI parameter (never a
checked-in production secret).

The cause-layer commands compose on the same CLI:

  cairn causes [--ledger DIR] [--status S] [--json]
      List the PUBLIC cause list (approved/live only) — or, with --status, the
      request/decision history view for that status. Exit 0.

  cairn cause-request FILE [--ledger DIR] [--by WHO] [--json]
      Submit a cause draft (JSON file). Records a CAUSE_REQUEST on the
      transparency log; the cause is NOT publicly listable yet. Exit 0.

  cairn cause-decide ID --approve|--reject --reason TEXT --by WHO [--frame-pass K]
                     [--ledger DIR] [--json]
      Record a reasoned CAUSE_DECISION via a COMPLETE five-frame gate-check.
      Only --approve flips the cause listable. Exit 0 on a recorded decision;
      nonzero on an empty reason or an incomplete gate (no silent decision).

The contribute command binds the cause layer
to the engine + adds the explicit, gated, recorded contributor opt-in:

  cairn contribute CAUSE_ID [--adapter mock] [--node ID] [--ledger DIR] [--json]
      Opt a node into an APPROVED cause (REFUSED if the cause is not publicly
      listable — the gate, no silent enlistment) and run that cause's bound
      benign work units end-to-end (define→claim→run→verify→record) offline via
      the mock pilot adapter. Exit 0 on a clean run; nonzero if the cause is not
      found / not listable / the node could not opt in.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Optional, Sequence

from .cause import (
    CauseError,
    CauseRegistry,
    CauseStatus,
    WorkUnitRegistry,
    five_frame_gate_check,
)
from .cause.model import FRAME_KEYS
from .contribute import CauseRunRefused, OptInRefused, OptInRegistry, run_cause
from .ledger import FixedClock, Ledger, verify_log
from .ledger.translog import KIND_RESULT_RECORDED, KIND_VERDICT_RECORDED, TransparencyLog
from .pilot import live_smoke, run_pilot
from .public import PublicTransparency

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


def _open_registry(ledger_arg: Optional[str]) -> CauseRegistry:
    """Open a CauseRegistry over a real ledger (offline, FixedClock, demo key)."""
    ledger_dir = (
        Path(ledger_arg)
        if ledger_arg
        else Path(tempfile.mkdtemp(prefix="cairn-cause-"))
    )
    ledger = Ledger(ledger_dir, FixedClock(start=0.0), signing_key=_DEMO_KEY)
    return CauseRegistry(ledger)


def _cmd_causes(args: argparse.Namespace) -> int:
    registry = _open_registry(args.ledger)
    status = CauseStatus(args.status) if args.status else None
    causes = registry.list_causes(status_filter=status)
    rows = [
        {
            "cause_id": c.cause_id,
            "name": c.name,
            "status": c.status.value,
            "listable": c.is_publicly_listable,
        }
        for c in causes
    ]
    if args.json:
        print(json.dumps(rows, indent=2, sort_keys=True))
    else:
        label = "public causes" if status is None else f"causes [{status.value}]"
        print(f"{label}: {len(rows)}")
        for r in rows:
            print(f"  {r['status']:9} {r['cause_id'][:12]}  {r['name']}")
    return 0


def _cmd_cause_request(args: argparse.Namespace) -> int:
    draft = json.loads(Path(args.file).read_text(encoding="utf-8"))
    if args.by:
        draft["created_by"] = args.by
    registry = _open_registry(args.ledger)
    cause = registry.submit_cause_request(draft)
    if args.json:
        print(json.dumps({"cause_id": cause.cause_id, "status": cause.status.value,
                          "listable": cause.is_publicly_listable}, indent=2,
                         sort_keys=True))
    else:
        print(f"REQUESTED cause_id={cause.cause_id}")
        print(f"  name: {cause.name}")
        print("  not publicly listable until approved")
    return 0


def _cmd_cause_decide(args: argparse.Namespace) -> int:
    # The decider's per-frame verdicts: every frame defaults to fail unless named
    # in --frame-pass, so the gate is COMPLETE only when all five are supplied.
    passed = set(args.frame_pass or [])
    unknown = passed - set(FRAME_KEYS)
    if unknown:
        print(f"unknown frame(s): {sorted(unknown)}; valid: {list(FRAME_KEYS)}")
        return 2
    verdicts = {k: (k in passed) for k in FRAME_KEYS}
    gate = five_frame_gate_check(verdicts)

    registry = _open_registry(args.ledger)
    try:
        cause = registry.decide_cause(
            args.cause_id,
            approve=args.approve,
            reason=args.reason,
            decider=args.by,
            gate_result=gate,
        )
    except CauseError as exc:
        print(f"DECISION REJECTED: {exc}")
        return 1

    if args.json:
        print(json.dumps(
            {"cause_id": cause.cause_id, "status": cause.status.value,
             "listable": cause.is_publicly_listable,
             "decision_reason": cause.decision_reason,
             "frames_passed": gate.frames_passed,
             "frames_failed": gate.frames_failed},
            indent=2, sort_keys=True))
    else:
        verb = "APPROVED" if args.approve else "REJECTED"
        print(f"{verb} cause_id={cause.cause_id}")
        print(f"  reason: {cause.decision_reason}")
        print(f"  now publicly listable: {cause.is_publicly_listable}")
    return 0


def _cmd_contribute(args: argparse.Namespace) -> int:
    # Offline only for now: the mock pilot adapter (real-model contribute is a
    # later phase; `live-smoke` already covers the one real spawn for the pilot).
    if args.adapter != "mock":
        print(
            f"unsupported adapter {args.adapter!r}: only 'mock' is supported "
            "(offline). Real-model contribute is a later phase."
        )
        return 2

    ledger_dir = (
        Path(args.ledger)
        if args.ledger
        else Path(tempfile.mkdtemp(prefix="cairn-contribute-"))
    )
    ledger = Ledger(ledger_dir, FixedClock(start=0.0), signing_key=_DEMO_KEY)
    cause_registry = CauseRegistry(ledger)
    optin_registry = OptInRegistry(ledger, cause_registry)

    # Bind the benign pilot units to this cause (mission-neutral worked example).
    work_units = WorkUnitRegistry()
    work_units.bind_pilot(args.cause_id)

    agreed = (
        f"Run the bound benign work units for cause {args.cause_id} on the local "
        "mock adapter (offline; no network, no PII)."
    )
    # Opt in (REFUSED if the cause is not publicly listable — the gate).
    try:
        optin_registry.opt_in(args.node, args.cause_id, agreed)
    except (OptInRefused, CauseError) as exc:
        print(f"OPT-IN REFUSED: {exc}")
        return 1

    try:
        summary = run_cause(
            args.cause_id,
            cause_registry=cause_registry,
            optin_registry=optin_registry,
            work_unit_registry=work_units,
            ledger=ledger,
            node_id=args.node,
            bad_family=args.bad_family,
        )
    except CauseRunRefused as exc:
        print(f"RUN REFUSED: {exc}")
        return 1

    if args.json:
        out = summary.to_dict()
        out["ledger_dir"] = str(ledger_dir)
        print(json.dumps(out, indent=2, sort_keys=True))
    else:
        print(summary.pretty())
        print(f"ledger dir: {ledger_dir}")
    return 0


def _open_public(ledger_arg: Optional[str]) -> Optional[PublicTransparency]:
    """Open a read-only PublicTransparency over an EXISTING ledger dir.

    The public surfaces project over already-recorded state; a missing ledger dir
    has nothing to project, so we report it rather than fabricate an empty temp one.
    """
    if not ledger_arg:
        return None
    root = Path(ledger_arg)
    if not root.exists():
        return None
    ledger = Ledger(root, FixedClock(start=0.0), signing_key=_DEMO_KEY)
    return PublicTransparency(ledger)


def _cmd_public_causes(args: argparse.Namespace) -> int:
    public = _open_public(args.ledger)
    if public is None:
        print(f"no ledger at {args.ledger!r}")
        return 1
    rows = [v.to_dict() for v in public.list_published_causes()]
    if args.json:
        print(json.dumps(rows, indent=2, sort_keys=True))
    else:
        print(f"published causes (approved/live only): {len(rows)}")
        for r in rows:
            print(
                f"  {r['status']:9} {r['cause_id'][:12]}  {r['name']}  "
                f"[self-frames {r['frames_self_passed']}/{r['frames_self_total']}]"
            )
    return 0


def _cmd_public_outcomes(args: argparse.Namespace) -> int:
    public = _open_public(args.ledger)
    if public is None:
        print(f"no ledger at {args.ledger!r}")
        return 1
    rows = [v.to_dict() for v in public.list_vetted_outcomes()]
    if args.json:
        print(json.dumps(rows, indent=2, sort_keys=True))
    else:
        print(f"vetted outcomes (human-verified, redacted metadata only): {len(rows)}")
        for r in rows:
            print(
                f"  {r['verdict']:8} packet={r['packet_hash'][:12]}  "
                f"flag={r['flag_label']!r}  reviewer={r['reviewer_of_record']}"
            )
    return 0


def _cmd_public_verify_log(args: argparse.Namespace) -> int:
    public = _open_public(args.ledger)
    if public is None:
        print(f"no ledger at {args.ledger!r}")
        return 1
    result = public.public_verify_log()
    if result.ok:
        print(f"OK length={result.length} head={result.head_hash}")
        return 0
    print(
        f"FAIL failed_index={result.failed_index} reason={result.reason!r} "
        f"(verified {result.length} entries before failure)"
    )
    return 1


def _cmd_public_log(args: argparse.Namespace) -> int:
    public = _open_public(args.ledger)
    if public is None:
        print(f"no ledger at {args.ledger!r}")
        return 1
    rows = [v.to_dict() for v in public.list_public_log()]
    if args.json:
        print(json.dumps(rows, indent=2, sort_keys=True))
    else:
        print(f"public transparency log (redacted skeleton, no payloads): {len(rows)}")
        for r in rows:
            print(f"  {r['index']:4} {r['kind']:22} hash={r['entry_hash'][:12]}")
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
        "--model", default="sonnet", help="model tier (default: sonnet)"
    )
    p_live.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="per-call claude -p subprocess timeout in seconds (default: 120)",
    )
    p_live.add_argument("--json", action="store_true", help="emit JSON summary")
    p_live.set_defaults(func=_cmd_live_smoke)

    # --- cause-layer commands ---
    p_causes = sub.add_parser(
        "causes", help="list public causes (approved/live), or a status history view"
    )
    p_causes.add_argument("--ledger", default=None, help="ledger directory")
    p_causes.add_argument(
        "--status",
        default=None,
        choices=[s.value for s in CauseStatus],
        help="filter to a status history view (default: public list only)",
    )
    p_causes.add_argument("--json", action="store_true", help="emit JSON rows")
    p_causes.set_defaults(func=_cmd_causes)

    p_creq = sub.add_parser(
        "cause-request", help="submit a cause draft (records a CAUSE_REQUEST)"
    )
    p_creq.add_argument("file", help="path to the cause draft JSON file")
    p_creq.add_argument("--ledger", default=None, help="ledger directory")
    p_creq.add_argument("--by", default=None, help="requester id (created_by)")
    p_creq.add_argument("--json", action="store_true", help="emit JSON summary")
    p_creq.set_defaults(func=_cmd_cause_request)

    p_cdec = sub.add_parser(
        "cause-decide",
        help="record a reasoned approve/reject decision via the five-frame gate",
    )
    p_cdec.add_argument("cause_id", help="the cause_id to decide")
    grp = p_cdec.add_mutually_exclusive_group(required=True)
    grp.add_argument("--approve", action="store_true", help="approve (→ listable)")
    grp.add_argument("--reject", action="store_true", help="reject (stays unlistable)")
    p_cdec.add_argument(
        "--reason", required=True, help="the recorded decision reason (no silent decision)"
    )
    p_cdec.add_argument("--by", required=True, help="the decider id")
    p_cdec.add_argument(
        "--frame-pass",
        dest="frame_pass",
        action="append",
        default=[],
        metavar="FRAME",
        help=f"a frame the decider passes (repeatable); all of {list(FRAME_KEYS)} "
        "must be addressed for a complete gate-check",
    )
    p_cdec.add_argument("--ledger", default=None, help="ledger directory")
    p_cdec.add_argument("--json", action="store_true", help="emit JSON summary")
    p_cdec.set_defaults(func=_cmd_cause_decide)

    p_contrib = sub.add_parser(
        "contribute",
        help="opt a node into an APPROVED cause and run its available units (offline)",
    )
    p_contrib.add_argument("cause_id", help="the approved cause_id to contribute to")
    p_contrib.add_argument(
        "--adapter",
        default="mock",
        help="execution adapter (only 'mock' supported in this release; offline)",
    )
    p_contrib.add_argument(
        "--node", default="contributor", help="the contributor node id"
    )
    p_contrib.add_argument(
        "--bad-family",
        dest="bad_family",
        default=None,
        help="run this model family as a faulty node on the honeypot unit",
    )
    p_contrib.add_argument("--ledger", default=None, help="ledger directory")
    p_contrib.add_argument("--json", action="store_true", help="emit JSON summary")
    p_contrib.set_defaults(func=_cmd_contribute)

    # --- public transparency read-surfaces (READ-ONLY projection) ---
    p_public = sub.add_parser(
        "public",
        help="public read-only transparency surfaces (no privileged access)",
    )
    pub_sub = p_public.add_subparsers(dest="public_command", required=True)

    pub_causes = pub_sub.add_parser(
        "causes", help="list PUBLISHED causes (approved/live only — the listing gate)"
    )
    pub_causes.add_argument("--ledger", required=True, help="ledger directory to read")
    pub_causes.add_argument("--json", action="store_true", help="emit JSON rows")
    pub_causes.set_defaults(func=_cmd_public_causes)

    pub_out = pub_sub.add_parser(
        "outcomes",
        help="list human-verified vetted outcomes (REDACTED metadata only)",
    )
    pub_out.add_argument("--ledger", required=True, help="ledger directory to read")
    pub_out.add_argument("--json", action="store_true", help="emit JSON rows")
    pub_out.set_defaults(func=_cmd_public_outcomes)

    pub_vl = pub_sub.add_parser(
        "verify-log",
        help="public independent transparency-log verify (reuses verify_log)",
    )
    pub_vl.add_argument("--ledger", required=True, help="ledger directory to read")
    pub_vl.set_defaults(func=_cmd_public_verify_log)

    pub_log = pub_sub.add_parser(
        "log",
        help="redacted public transparency-log skeleton view (no payloads)",
    )
    pub_log.add_argument("--ledger", required=True, help="ledger directory to read")
    pub_log.add_argument("--json", action="store_true", help="emit JSON rows")
    pub_log.set_defaults(func=_cmd_public_log)

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
