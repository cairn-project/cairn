#!/usr/bin/env bash
#
# cairn — end-to-end cause demo.
#
# Runs the full benign cause loop with a single invocation, on a throwaway
# ledger, fully offline (no network, no model spawn):
#
#   request a cause -> approve it through the five-frame safety gate
#   -> contribute work -> read the public transparency surfaces -> verify the log
#
# This is the runnable companion to docs/WALKTHROUGH.md. Run it from the
# repository root after installing the package (see docs/QUICKSTART.md):
#
#   ./examples/demo.sh
#
# It prints each step and exits 0 only if the whole chain succeeds.

set -euo pipefail

# --- locate the repo root (this script lives in <root>/examples) ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

# --- locate the cairn command: prefer the repo venv, fall back to PATH ---
if [ -x ".venv/bin/cairn" ]; then
  CAIRN=".venv/bin/cairn"
elif command -v cairn >/dev/null 2>&1; then
  CAIRN="cairn"
else
  echo "error: 'cairn' command not found." >&2
  echo "Install the package first (see docs/QUICKSTART.md):" >&2
  echo "  python3.13 -m venv .venv && .venv/bin/pip install -e \".[dev]\"" >&2
  exit 1
fi

DRAFT="src/cairn/fixtures/cause_draft_benign.json"

# --- a throwaway ledger, cleaned up on exit ---
LEDGER="$(mktemp -d -t cairn-demo)"
cleanup() { rm -rf "$LEDGER"; }
trap cleanup EXIT

echo "==> cairn end-to-end demo"
echo "    cairn:  $CAIRN"
echo "    ledger: $LEDGER"
echo

echo "==> 1. request the benign cause"
"$CAIRN" cause-request "$DRAFT" --by demo-requester --ledger "$LEDGER" --json
# The cause_id is the content hash of the draft, so re-requesting is idempotent.
# Read it back from the requested-status history view (JSON) for portability.
CID="$("$CAIRN" causes --status requested --ledger "$LEDGER" --json \
       | python3 -c 'import sys,json; print(json.load(sys.stdin)[0]["cause_id"])')"
echo "    cause_id: $CID"
echo

echo "==> 2. approve through the complete five-frame gate"
"$CAIRN" cause-decide "$CID" \
  --approve \
  --reason "Benign mission-neutral worked example; all five safety frames addressed." \
  --by demo-reviewer \
  --frame-pass works \
  --frame-pass doesnt_target_good_people \
  --frame-pass legal \
  --frame-pass court_grade_auditable \
  --frame-pass human_verified \
  --ledger "$LEDGER"
echo

echo "==> 3. the cause is now publicly listable"
"$CAIRN" causes --ledger "$LEDGER"
echo

echo "==> 4. contribute work to the approved cause"
"$CAIRN" contribute "$CID" --node demo-node --ledger "$LEDGER"
echo

echo "==> 5. public transparency surfaces"
"$CAIRN" public causes --ledger "$LEDGER"
echo
"$CAIRN" public verify-log --ledger "$LEDGER"
echo

echo "==> demo complete — the full cause loop ran end-to-end on a verifiable ledger."
