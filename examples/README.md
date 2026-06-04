# cairn — examples

Runnable artefacts that exercise a real, fully-offline cairn workflow.

## `demo.sh` — the full cause loop in one command

```sh
./examples/demo.sh
```

Runs the complete benign cause loop on a throwaway ledger, offline (no network,
no model spawn):

1. **request** the shipped benign cause (`cause_draft_benign.json`),
2. **approve** it through the complete five-frame safety gate,
3. **contribute** work to the approved cause (define → claim → run → verify →
   record),
4. read the **public transparency surfaces** and independently **verify** the
   tamper-evident log.

It prints each step and exits non-zero if any step fails, so it doubles as a
smoke test. The ledger is a temp directory, cleaned up on exit.

Prerequisite: install the package first (see [`../docs/QUICKSTART.md`](../docs/QUICKSTART.md)):

```sh
python3.13 -m venv .venv          # any python >= 3.11
.venv/bin/pip install -e ".[dev]"
```

The script prefers `.venv/bin/cairn` and falls back to a `cairn` on your `PATH`.

## Want the step-by-step version?

[`../docs/WALKTHROUGH.md`](../docs/WALKTHROUGH.md) walks through the same chain
one command at a time, explaining each gate and surface — start there if you
want to understand *why* each step does what it does.
