# Contributing to Cairn

Thank you for considering a contribution. Cairn is a model-agnostic
detection-and-analysis force-multiplier being built to become a decentralized,
distributed, volunteer-powered network — that decentralized network is the
target the project is working toward, while today it runs as a single-operator,
offline pilot. It is explicitly a **trust-requiring** project: it exists to feed
credible evidence to institutions that have authority to act. That means the bar for transparency,
auditability, and honest limitations is high, and contributions are reviewed
against that bar.

> **Name.** "Cairn" is mission-neutral by design. The repository lives at
> <https://github.com/cairn-project/cairn>.

By contributing you agree that your contributions are licensed under the
project's [MIT License](LICENSE), and you agree to abide by our
[Code of Conduct](CODE_OF_CONDUCT.md).

---

## Before you start

- **Security vulnerabilities are NOT public issues.** If you have found a
  security or trust-integrity vulnerability, do **not** open a public issue or
  pull request. Follow the private disclosure process in [SECURITY.md](SECURITY.md).
- **Read the threat model.** [`docs/THREAT-MODEL.md`](docs/THREAT-MODEL.md)
  states plainly what Cairn does and does not guarantee. Changes that touch the
  verify layer, the ledger, the transparency log, or any safety gate should be
  weighed against it.
- **Understand the safety frames.** Every significant design choice in this
  project is checked against five named frames (works / doesn't-target-good-people
  / legal / court-grade-auditable / human-verified). A change that weakens any
  frame will be declined regardless of how clean the code is. Two of these frame
  names are **aspirational, not yet verified properties**: `court_grade_auditable`
  today means a tamper-evident, append-only audit log (identity-authentication,
  external anchoring, and non-repudiation are deferred phases), and
  `human_verified` means a recorded
  human verdict exists (the human is unauthenticated free-text). See
  [SECURITY.md](SECURITY.md) → "What the human gate does — and does NOT —
  guarantee today" for the precise boundary.

---

## Development setup

Cairn targets **Python 3.11+** and is standard-library-first (the only runtime
dependency is `jsonschema`).

```sh
# clone your fork, then:
python3.11 -m venv .venv          # any python >= 3.11 works
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```

`pytest` must be green locally before you open a pull request, and **CI runs
the full `pytest` suite on every push and pull request** across Python 3.11,
3.12, and 3.13 (see [`.github/workflows/ci.yml`](.github/workflows/ci.yml)).
A green suite — locally and in CI — is the merge bar. Run the suite locally on
at least your target Python before opening a PR so CI confirms rather than
discovers.

---

## Workflow — pull-request based, no direct pushes to `main`

`main` is protected. **All changes land through pull requests; no one pushes
directly to `main`.**

1. **Fork** the repository (<https://github.com/cairn-project/cairn>).
2. **Branch** from `main` with a descriptive name
   (`fix/lease-expiry-off-by-one`, `feat/honeypot-density-knob`).
3. **Make your change** with tests. New behavior requires a test; a bug fix
   requires a regression test that fails before and passes after.
4. **Open a pull request** against `main`. Fill in the
   [pull-request template](.github/PULL_REQUEST_TEMPLATE.md) honestly —
   including the safety-frames and "no secrets" checklist items.
5. **Review.** At least one maintainer reviews. Discussion happens in the open
   on the PR. See [GOVERNANCE.md](GOVERNANCE.md) for how decisions are made.
6. **Tests must be green.** The full `pytest` suite passes locally and in CI
   (the CI matrix runs on every push and pull request).
7. **Merge.** A maintainer merges once review is approved and the suite is green.

---

## Commit messages

Use clear, conventional-style messages: a short imperative subject line,
optionally prefixed with a type and scope.

```
feat(verify): add per-cause honeypot-density override
fix(ledger): reopen unit when claim lease expires
docs(threat-model): state HMAC-vs-PKI boundary plainly
test(pilot): cover bad-node honeypot-catch path
```

- Subject line in the imperative mood ("add", not "added"), ~72 chars or fewer.
- Reference issues in the body (`Closes #123`) where relevant.
- One logical change per commit where practical.

---

## Tests are required for merge

- Every behavioral change ships with a test.
- Bug fixes ship with a regression test.
- The full `pytest` suite must pass locally and in CI before merge.
- Changes to a safety-relevant path (verify quorum, honeypots, ledger,
  transparency log, acceptance contract) should include a test that exercises
  the failure mode the code defends against — not just the happy path.

---

## Code style

- **Standard library first.** Do not add a runtime dependency without a
  maintainer discussion; the small dependency surface is a deliberate trust
  property.
- Follow the style of the surrounding code. Keep functions small and named for
  their observable outcome.
- No checked-in secrets, keys, tokens, or credentials — ever. CI and review
  will reject them. See [SECURITY.md](SECURITY.md).
- Public functions get docstrings; non-obvious decisions get a comment that
  names the design source.

---

## Where to ask

- **General questions / design discussion:** open a
  [discussion or issue](.github/ISSUE_TEMPLATE/) on the repository
  (<https://github.com/cairn-project/cairn>).
- **Security / trust-integrity vulnerabilities:** **private** channel only —
  [SECURITY.md](SECURITY.md).
- **Conduct concerns:** see [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

Small, well-scoped, well-tested pull requests are the easiest to review and the
fastest to merge. Thank you for adding your stone to the cairn.
