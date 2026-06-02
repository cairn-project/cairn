# BUILD-PLAN — OSS docs/onboarding, wave 2 (front-door accuracy)

**Scope:** documentation + onboarding-surface accuracy only. No `src/` logic
changes. No CI workflow files. Full test suite stays green at **276** (this
branch is based on `origin/main`, before the PR #7 bridge — 291 includes the
bridge's tests, which are not on this branch). Branch: `feat/oss-docs-onboarding`.

This wave finishes the onboarding surface the first wave started (5 commits
already on-branch: MIT reconcile, governance/releasing/quickstart, CoC,
GitHub-native contact, threat model) and corrects the stale front door.

## Deliverables

### 1. Commit the three leaking untracked files (all belong tracked)
Evidence each is not cruft, decided per repo convention:
- `.github/ISSUE_TEMPLATE/` (bug/feature/cause_request/config.yml) — BUILD-PLAN
  wave-1 deliverable #5; cause_request fields verified == `cause/model.py`
  (name, description, target_conduct, protected_boundary, output_schema_ref,
  partner_of_record_posture, created_by, five_frame w/ the five FRAME_KEYS).
- `CITATION.cff` — wave-1 deliverable #4; pairs with the `dacb1d0` MIT reconcile
  commit; parses as valid CFF 1.2.0.
- `BUILD-PLAN-oss-docs-onboarding.md` + this wave-2 plan — the repo tracks every
  other `BUILD-PLAN-*.md` as its audit trail (7 already tracked); these match
  that convention.

### 2. Rewrite the stale README (the misleading front door)
Current README says "wave 1 — foundation only" / lists only spec+validate and a
long DEFERRED list that is now mostly BUILT. Replace with an accurate map of the
real engine (execute / verify / ledger+transparency / cause / contribute /
capture / vetting / public / routing — all shipped, per CHANGELOG `[Unreleased]`
Added) PLUS an honest maturity statement: pre-1.0 (0.x), unreleased, benign
pilot-stage, mission-neutral, MIT. Point newcomers at QUICKSTART + CONTRIBUTING.
Keep: the cairn epigraph, the name note (now: final/owner-ratified, formerly the
placeholder-name note), the not-built-into-loam note,
stdlib-first/jsonschema requirement. Accuracy both directions: it runs
end-to-end (don't undersell) AND it's 0.x pilot-stage with deferred real-world
adapters (don't oversell).

### 3. Fix pyproject description
`description` still says "wave-1 foundation: the work-unit + acceptance-contract
spec." → accurate one-line description of the whole engine. Version stays `0.1.0`
(authoritative per RELEASING.md; CHANGELOG `[Unreleased]` carries "not released").

### 4. Fix CONTRIBUTING CI false-claims (doc accuracy, NOT adding CI)
Lines 49-50/69 assert "CI runs the same suite on 3.11/3.12/3.13
(see .github/workflows/ci.yml)" + "All matrix Python versions pass before merge"
— no workflows dir exists. Reframe to RELEASING.md's honest posture: green local
pytest is the merge bar today; CI matrix is intended/recommended-not-yet-present.

## Decisions (deviations from wave-1 plan, evidence-based)
- **CITATION version = `0.1.0`, NOT `0.1.0-pre`.** RELEASING.md names pyproject
  `project.version` (`0.1.0`) as the authoritative static version source.
  Introducing `-pre` only in CITATION would make two metadata files disagree —
  itself an inaccuracy. "Unreleased" is honestly carried by CHANGELOG
  `[Unreleased]` + the README maturity statement.

## Acceptance
- `git status` clean after commits (no leaking untracked files).
- README contains no "wave 1 — foundation only" framing; lists the shipped
  layers matching CHANGELOG Added; carries an honest 0.x/pilot/MIT maturity line.
- pyproject description names the engine, not "wave-1 foundation".
- CONTRIBUTING makes no false claim that CI runs today.
- `pytest` = 276 passed (unchanged).
- Branch pushed to private origin; PR against main left for owner; PR #7 untouched.
