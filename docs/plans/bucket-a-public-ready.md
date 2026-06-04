# Build plan — Bucket A: engine-to-public usability + readiness

**Branch:** `docs/bucket-a-public-ready` (worktree off `origin/main` @ `c0e750a`)
**Contract:** `pos3/workspace/.scratch/claude-output/cairn-engine-to-public-plan.md`
**Conventions:** Cairn's own — normal TDD (test-per-behavior, regression-test-per-bugfix),
conventional commits, NO `Co-Authored-By` trailer, PR-only to protected `main`,
stdlib-first (no new runtime deps), green 291-test suite stays green.

**Baseline (Tier-0, this worktree, python3.13):** `pytest` → 291 passed, 3.72s.
Full request→approve→contribute→public walkthrough verified by hand on a shared
`--ledger` — it works end-to-end. The only gaps are usability + docs, exactly as
the assessment said.

## Items (Bucket A)

- **A2 — default-ledger UX (only `src/` change).** Today every command does
  `Path(args.ledger) if args.ledger else <fresh temp dir>`, so a multi-step flow
  without `--ledger` silently writes to *different* ledgers each call. Fix:
  a single resolver `resolve_ledger_dir(arg)` that, when no `--ledger` is given,
  returns a *persisted* default: `$CAIRN_LEDGER` env override → else
  `$XDG_DATA_HOME/cairn/ledger` → else `~/.local/share/cairn/ledger`, creating it.
  `--ledger DIR` still overrides. The read-only `public` subcommands keep
  `--ledger` required (unchanged). `pilot`/`live-smoke` keep minting fresh temp
  dirs (a demo wants a clean ledger every run) — but gain a documented note.
  Actually: pilot/live-smoke are demos and SHOULD stay ephemeral-by-default;
  the default-ledger persistence applies to the *cause-flow* commands
  (`causes`, `cause-request`, `cause-decide`, `contribute`) where threading state
  across calls is the whole point. TDD: new `tests/test_ledger_default_path.py`
  exercising env override + XDG + HOME fallback (monkeypatched env/home, no real
  writes outside tmp). New behavior → new test.

- **A1 — `docs/WALKTHROUGH.md`** + QUICKSTART link. The full loop as one
  copy-paste block on a shared `--ledger` (and a second block showing the
  default-ledger "no `--ledger` needed" path). Real frame keys named. Every
  command in it was run by hand this pass. Honest note: `public outcomes` is 0
  after `contribute` because vetted outcomes come from the capture→analysis→
  human-vet path, not the contribute path — do not imply otherwise.

- **A3 — `examples/` + `examples/demo.sh`** running the whole chain with one
  invocation on a scratch ledger, plus `examples/README.md`. Smoke test
  `tests/test_examples_demo.py` runs the script and asserts the end-state
  (cause listed, 4/4 accepted, log verifies).

- **A4 — repo-URL sweep.** `github.com/lukeivers/cairn` → `github.com/cairn-project/cairn`
  in CITATION.cff, RELEASING.md, CONTRIBUTING.md, SECURITY.md, ISSUE_TEMPLATE/config.yml.
  LEAVE: GOVERNANCE.md `@lukeivers` personal-profile maintainer link (identity/
  governance call, not a repo URL — note it, don't guess). CODE_OF_CONDUCT Mozilla
  link untouched. Grep-verify zero stale `lukeivers/cairn` repo refs after.

- **A6 — QUICKSTART expectation-set line** up front: runnable scope is the benign
  offline pilot/worked-example; live capture + recipient egress are deferred,
  by-design-offline waves.

- **A5 — branch hygiene.** `git branch --merged origin/main` shows only `main` —
  the feature branches were squash-merged (don't show as merged). Verify each
  remote feature branch's content is in `main` via the PR-merge commits, then
  document the canonical state. DO NOT delete remote branches (could be others'
  in-flight; deleting is owner/repo-admin hygiene — note recommendation instead).
  Local stale branches in the MAIN checkout are the other agent's / Luke's —
  leave them. This item is verify-and-document, not destructive.

- **A6/A9 — HARD smoke.** Fresh `git clone` of the *pushed branch* into a temp
  dir, clean venv (python3.13), `pip install -e ".[dev]"`, run the documented
  WALKTHROUGH commands verbatim as a stranger would, run `examples/demo.sh`,
  run full `pytest`. Capture output. This proves cold-clone usability.

- **Optional A7 (static HTML render) / A8 (concurrency-safe translog):** SKIP —
  both are scaling, not launch-blocking, and non-trivial. Note as deferred.

## A5 — branch-hygiene findings (verify-and-document; non-destructive)

Verified against `origin` (fetched). `main` is the canonical public state.
Squash-merge means merged feature branches are NOT git-ancestors of `main`;
verified by content-diff instead:

- `origin/chore/scrub-and-polish` — **fully merged** (zero diff vs `main`).
  Safe to delete.
- `origin/feat/analysis-finding-bridge` — **behind `main`** (1 unique tip commit,
  the pre-squash version; `main` is 3 commits ahead and evolved those files).
  Stale; its work is in `main`. Safe to delete.
- `origin/feat/oss-docs-onboarding` — **behind `main`** (11 pre-squash commits;
  `main` is 3 ahead). Stale; its work is in `main`. Safe to delete.
- `origin/docs/bucket-b-governance-policy-drafts` — **a parallel agent's
  in-flight branch (Bucket B). DO NOT TOUCH.**

**Recommendation (owner/repo-admin action, NOT done here):** delete the three
stale remote branches above via the GitHub UI or
`git push origin --delete <branch>`. Left undone deliberately — deleting remote
branches is repo-admin hygiene and a parallel agent is active on this repo;
pruning is owner's call, not a code change to PR.

## Sequence
1. A2 test (red) → A2 code (green) → full suite.
2. A1 + A3 + A4 + A6 docs/examples (no src race).
3. A3 smoke test green; full suite green.
4. Commit in conventional-commit chunks.
5. Push branch; HARD smoke from a fresh clone of the pushed branch.
6. Open PR to `main` (no merge).
