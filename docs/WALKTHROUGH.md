# cairn — End-to-end cause walkthrough

This is the full loop a newcomer follows: **request a cause → approve it
through the five-frame safety gate → contribute work → read the public
transparency surfaces.** Every command below is real and offline (no network,
no model spawn). Copy-paste them in order.

Prerequisites: you have installed the package per
[`QUICKSTART.md`](QUICKSTART.md) (`python3.13 -m venv .venv` then
`.venv/bin/pip install -e ".[dev]"`), so the `cairn` command is available as
`.venv/bin/cairn`.

> **What this exercises.** A *benign, mission-neutral worked example* — the
> shipped `cause_draft_benign.json` ("Open-data link-rot audit"). The whole
> chain runs on a tamper-evident, hash-chained ledger you can independently
> re-verify. Live capture and live recipient delivery are deferred,
> offline-by-design waves (see `QUICKSTART.md` and `docs/THREAT-MODEL.md`).

---

## One shared ledger

Every step records onto, or reads from, **one ledger directory**. The
cause-flow commands (`cause-request`, `cause-decide`, `causes`, `contribute`)
share a **persisted default ledger** when you do not pass `--ledger`, so the
multi-step flow below "just works". You have two equivalent options:

- **Default ledger (simplest):** omit `--ledger` on every command. State
  persists under `$CAIRN_LEDGER` if set, else `$XDG_DATA_HOME/cairn/ledger`,
  else `~/.local/share/cairn/ledger`.
- **Explicit ledger (used in this doc for a clean, throwaway run):** pass the
  same `--ledger DIR` to every command. We bind it to a shell variable so you
  can paste each block as-is:

```sh
export CAIRN_WALKTHROUGH_LEDGER="$(mktemp -d -t cairn-walkthrough)"
echo "ledger: $CAIRN_WALKTHROUGH_LEDGER"
```

Throughout, `--ledger "$CAIRN_WALKTHROUGH_LEDGER"` appears on each command. To
use the persisted default instead, simply delete the `--ledger ...` argument
from every command — the flow is identical.

---

## 1. Request a cause

Submit the shipped benign cause draft. This records a `CAUSE_REQUEST` on the
transparency log. The cause is **not** publicly listable yet — it is awaiting a
human decision.

```sh
.venv/bin/cairn cause-request src/cairn/fixtures/cause_draft_benign.json \
    --by alice \
    --ledger "$CAIRN_WALKTHROUGH_LEDGER"
```

```
REQUESTED cause_id=1e37059bc686d5da92e624b6818eee3af1d36ad9066c08496bc5ddb5ada5e3a2
  name: Open-data link-rot audit
  not publicly listable until approved
```

Capture the `cause_id` for the next steps. The `--json` flag makes this
scriptable:

```sh
CID="$(.venv/bin/cairn cause-request src/cairn/fixtures/cause_draft_benign.json \
        --by alice --ledger "$CAIRN_WALKTHROUGH_LEDGER" --json \
        | .venv/bin/python -c 'import sys,json; print(json.load(sys.stdin)["cause_id"])')"
echo "cause_id: $CID"
```

> If you re-run `cause-request` you create a *second* request; the `cause_id` is
> the content hash of the draft, so the same draft yields the same id. To see
> the history view of everything in the `requested` state:
>
> ```sh
> .venv/bin/cairn causes --status requested --ledger "$CAIRN_WALKTHROUGH_LEDGER"
> ```

---

## 2. Approve the cause through the five-frame gate

A cause becomes publicly listable only after a **reasoned human decision** that
addresses all five safety frames. There is no silent decision: an empty reason
or an incomplete gate is refused.

The five frame keys are exactly:

| frame key | the question it answers |
|---|---|
| `works` | Does approving this lead to a concrete real-world action? |
| `doesnt_target_good_people` | Does it target conduct, not good-faith people? |
| `legal` | Is the activity lawful (public surfaces, no ToS-evasion)? |
| `court_grade_auditable` | Is every step recorded on the tamper-evident log? |
| `human_verified` | Does a human confirm before anything acts on the result? |

> Two of these frames — `court_grade_auditable` and `human_verified` — name an
> **aspiration the protocol is built toward**, not a guarantee. Approving a
> cause asserts the decider judged each frame satisfied for *this* cause; it is
> not a court certification. See the honesty block in `README.md`.

Pass each frame the decider judges satisfied with a repeated `--frame-pass`.
All five must be addressed for a complete gate:

```sh
.venv/bin/cairn cause-decide "$CID" \
    --approve \
    --reason "Benign mission-neutral worked example; all five safety frames addressed." \
    --by reviewer-bob \
    --frame-pass works \
    --frame-pass doesnt_target_good_people \
    --frame-pass legal \
    --frame-pass court_grade_auditable \
    --frame-pass human_verified \
    --ledger "$CAIRN_WALKTHROUGH_LEDGER"
```

```
APPROVED cause_id=1e37059bc686d5da92e624b6818eee3af1d36ad9066c08496bc5ddb5ada5e3a2
  reason: Benign mission-neutral worked example; all five safety frames addressed.
  now publicly listable: True
```

To **reject** instead, use `--reject` with a reason; the cause stays
unlistable. Omitting frames (an incomplete gate) is also refused — try it to
see the gate enforce itself.

The cause is now on the public list:

```sh
.venv/bin/cairn causes --ledger "$CAIRN_WALKTHROUGH_LEDGER"
```

```
public causes: 1
  approved  1e37059bc686  Open-data link-rot audit
```

---

## 3. Contribute work to the approved cause

A node opts in to the approved cause and runs its bound benign work units
end-to-end (define → claim → run → verify → record), offline via the mock
adapter. Opt-in is **refused** for a cause that is not publicly listable, so this
step only works *after* approval — the gate enforces no silent enlistment.

```sh
.venv/bin/cairn contribute "$CID" \
    --node node-charlie \
    --ledger "$CAIRN_WALKTHROUGH_LEDGER"
```

```
cause: 1e37059bc686d5da92e624b6818eee3af1d36ad9066c08496bc5ddb5ada5e3a2
contributor node: node-charlie (opted in)

  ...::bike-counts          verdict: ACCEPTED  | quorum families: claude, gpt
  ...::air-quality          verdict: ACCEPTED  | quorum families: claude, gpt
  ...::transit-feed         verdict: ACCEPTED  | quorum families: claude, gpt
  ...::proprietary-index    verdict: ACCEPTED  | quorum families: claude, gpt

units accepted: 4/4  | honeypot catches: 0
transparency log: 8 results recorded, 4 verdicts recorded
log head: 0c4539f3...
```

Each unit is verified by **quorum across model families** (not bit-equality),
guarded by a honeypot unit. To watch the honeypot catch a misbehaving node, add
`--bad-family gpt`: one family is flipped wrong on the honeypot unit and the run
reports the catch.

---

## 4. Read the public transparency surfaces

These are **read-only projections** over the ledger — redacted by construction,
no privileged access. This is what an outside observer sees. The `public`
commands require an explicit `--ledger` (they project over an existing ledger
and never fabricate one).

Published causes (approved/live only — the listing gate):

```sh
.venv/bin/cairn public causes --ledger "$CAIRN_WALKTHROUGH_LEDGER"
```

```
published causes (approved/live only): 1
  approved  1e37059bc686  Open-data link-rot audit  [self-frames 5/5]
```

Independently re-verify the tamper-evident transparency log (re-runs the same
`verify_log` an auditor would):

```sh
.venv/bin/cairn public verify-log --ledger "$CAIRN_WALKTHROUGH_LEDGER"
```

```
OK length=16 head=9b785670...
```

The redacted public log skeleton (entry kinds + hashes, no payloads):

```sh
.venv/bin/cairn public log --ledger "$CAIRN_WALKTHROUGH_LEDGER"
```

Vetted outcomes:

```sh
.venv/bin/cairn public outcomes --ledger "$CAIRN_WALKTHROUGH_LEDGER"
```

```
vetted outcomes (human-verified, redacted metadata only): 0
```

> **Why is `public outcomes` zero after a clean contribute run?** A *vetted
> outcome* is a finding that has gone through the **capture → analysis →
> human-vet** path (a captured packet, flagged by an analysis policy, then
> human-reviewed). The `contribute` command above exercises the
> **cause → execute → verify** spine, which records *results and verdicts* on
> the log (visible via `public log` and counted in the contribute summary) — it
> does not by itself produce human-vetted findings. So zero here is correct, not
> a bug. The vetting path is exercised by the vetting/analysis modules and their
> tests (`test_vetting_e2e`, `test_analysis_e2e`); wiring it into a single CLI
> command is a later phase.

---

## 5. Inspect and re-verify directly (optional)

The same ledger can be inspected and re-verified without the `public`
projection:

```sh
.venv/bin/cairn inspect "$CAIRN_WALKTHROUGH_LEDGER"
.venv/bin/cairn verify-log "$CAIRN_WALKTHROUGH_LEDGER/translog.jsonl"
```

---

## Clean up

The explicit walkthrough ledger is a throwaway temp directory:

```sh
rm -rf "$CAIRN_WALKTHROUGH_LEDGER"
unset CAIRN_WALKTHROUGH_LEDGER
```

If you used the **persisted default ledger** instead (no `--ledger`), it lives
under `~/.local/share/cairn/ledger` (or `$XDG_DATA_HOME` / `$CAIRN_LEDGER`);
remove that directory to reset.

---

## What you just proved

- A cause is **inert until a human approves it** through a complete,
  reasoned five-frame gate — no silent decisions.
- Contribution is **gated and recorded** — a node cannot enlist in an
  unapproved cause.
- Every step lands on a **tamper-evident, independently-verifiable** log.
- The public surfaces are **redacted by construction** — an observer sees the
  causes and the verifiable log skeleton, not the underlying payloads.

For a single-command runnable version of this same chain, see
[`examples/demo.sh`](../examples/demo.sh).
