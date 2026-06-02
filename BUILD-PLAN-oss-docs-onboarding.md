# BUILD-PLAN — OSS community-health + contributor onboarding

**Scope:** documentation + onboarding surface only. No `src/` logic changes.
No CI workflow files (`.github/workflows/*` are out — they need a separate
owner-granted GitHub scope). The full test suite must stay green and unchanged
in count (276).

Branch: `feat/oss-docs-onboarding` off `origin/main` (ef7adb0). Opened as a PR
against `main`, left open for owner review/merge.

## Deliverables + per-doc accuracy acceptance

Each doc is verified against named real code; no aspirational features; deferred
features marked deferred.

1. **CODE_OF_CONDUCT.md** — Contributor Covenant v2.1 standard text;
   enforcement contact `[CONDUCT CONTACT — owner to fill]`.
   - Acceptance: standard Covenant structure; placeholder present; no invented
     project-specific rules.

2. **GOVERNANCE.md** — maintainer model, PR/decision flow, how the two human
   vetting roles (cause-vetter, finding-vetter) + the trust-gated
   capture-operator role are granted/revoked at the project level, strict-vetting
   posture for partners, path to becoming a maintainer/vetter. Mission-neutral.
   - Acceptance: the two vetting roles match `vetting/review.py` +
     `vetting/cause_queue.py` + `vetting/finding_queue.py`; the capture-operator
     role matches `capture/gate.py` (`CaptureGate` grant/revoke, fail-closed);
     the five-frame gate matches `cause/gate.py` + `cause/model.py` FRAME_KEYS.

3. **RELEASING.md** — SemVer (pre-1.0 0.x per CHANGELOG), PR + branch-protection
   + linear-history flow, CHANGELOG discipline, per-minor smoke expectation,
   intent to ship signed (Sigstore) releases + SBOM (described as process /
   intent; no release claimed).
   - Acceptance: SemVer rules match CHANGELOG header; smoke = `cairn pilot` /
     `cairn live-smoke` (real CLI, `cli.py`); no claim a release happened;
     signing/SBOM marked as intended/planned.

4. **CITATION.cff** — valid CFF 1.2.0; title Cairn; authors
   `[AUTHOR — owner to fill]` + the project; MIT; repo
   github.com/lukeivers/cairn; version `0.1.0-pre` (0.x-pre).
   - Acceptance: parses as YAML; required CFF 1.2.0 keys present.

5. **.github/ISSUE_TEMPLATE/** — `bug_report.md`, `feature_request.md`,
   `cause_request.md` (fields aligned to the real cause-request shape),
   `config.yml` pointing security → SECURITY.md, issues off for security.
   - Acceptance: cause_request fields == `cause/model.py` Cause draft fields
     (name, description, target_conduct, protected_boundary, output_schema_ref,
     partner_of_record_posture, created_by, five_frame with the five FRAME_KEYS:
     works / doesnt_target_good_people / legal / court_grade_auditable /
     human_verified) — cross-checked against `fixtures/cause_draft_benign.json`
     and the `cairn cause-request FILE` CLI path.

6. **docs/THREAT-MODEL.md** — engine security threat model, mission-neutral,
   clinical. Adversaries: trust/reputation gaming + Sybil, quorum poisoning,
   honeypot evasion, examination-bundle forgery/spoofing, capture-operator abuse,
   transparency-log tampering (+ how `verify_log` detects it), prompt-injection
   against analysis; fail-closed gates as mitigations; honest limitations.
   Resolves the dangling `docs/THREAT-MODEL.md` reference in CHANGELOG +
   CONTRIBUTING.
   - Acceptance: each mitigation maps to a named module — `verify/quorum.py`
     (diversity), `verify/honeypot.py`, `verify/reputation.py`,
     `ledger/translog.py` + `verify_log`, `capture/gate.py`, `cause/gate.py`,
     `vetting/*`, `routing/policy.py` + `routing/dispatch.py`.

7. **docs/QUICKSTART.md** (linked from README) — clone → `pip install -e .` →
   `cairn pilot` → cause-request + cause-decide --approve → `cairn contribute` →
   `cairn public ...` → `cairn public verify-log`. Every command real per
   `cli.py`.
   - Acceptance: every command + flag exists in `cli.py`; the request→approve→
     contribute ordering reflects the real listable-gate (`contribute` REFUSES a
     non-listable cause).

## Process

- Author docs; run full suite in a clean Python 3.13 venv; confirm 276 unchanged.
- Add README link to QUICKSTART (only README change).
- Push, open PR against main, leave open. No amend; corrective commits only.

## Halt-and-surface (existing-doc inaccuracies found — see PR/report)

- README.md is stale (describes "wave 1 — foundation only"; repo is complete
  through routing).
- CONTRIBUTING.md + SECURITY.md reference a CI matrix / `.github/workflows/ci.yml`
  that does not exist (no workflows dir). Out of scope to add CI here.
- pyproject.toml `license = { text = "TBD" }` while LICENSE is MIT and all docs
  say MIT.
- pyproject.toml description still says "wave-1 foundation".

These are surfaced with evidence, not silently fixed (out of scope).
