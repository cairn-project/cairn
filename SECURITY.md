# Security Policy

Cairn is a trust-critical project. We take security reports seriously and practice
coordinated disclosure.

## Reporting a vulnerability

**Do not open a public issue for security vulnerabilities.**

- Preferred: use GitHub's **private security advisories** ("Report a vulnerability"
  on the [Security tab](https://github.com/cairn-project/cairn/security)) once the
  repository is public.
- Or use GitHub's private vulnerability reporting: the repository's **Security** tab → **Report a vulnerability**.

Please include: a description of the issue, steps to reproduce, the affected
component/version, and impact.

## What to expect

- **Acknowledgement** within 3 business days.
- An initial assessment and severity triage within 7 business days.
- We will keep you informed of remediation progress and coordinate a disclosure
  timeline with you. Standard embargo target is up to 90 days, shortened where a fix
  ships sooner.
- Credit in the advisory/changelog if you wish (and unless you prefer to remain
  anonymous).

## Scope

In scope: the Cairn engine code in this repository (work-unit spec, execute/adapter,
verify, ledger/transparency-log, CLI, pilot, cause/contribute layers). This includes
the **inert evidence-bundle capture seam** (`cairn.capture`): the trust-gated CAPTURE
role (fail-closed `CaptureGate`), the inert `ExaminationPacket` / `AnalysisView`
boundary (the guarantee that an analyst only ever sees the frozen bundle and cannot
re-visit the live target), and the `capture_packet` / `load_packet_for_analysis`
flow. Note that the only capture port shipped today is the deterministic, OFFLINE
`StaticDocumentCapturePort` (synthetic local fixture; no real browser/network); the
real headless-browser / network-egress capture port is a deferred, independently
security-reviewed phase and is NOT yet in this repository.

It also includes the **human-in-the-loop two-gate vetting queue** (`cairn.vetting`):
the two fail-closed human-review gates (the cause-vetting gate `CauseVetQueue`, whose
`apply_cause_verdict` is the only path feeding the existing cause decision, and the
finding-vetting gate `FindingVetQueue`, whose `is_routable` is true only after a
recorded human verdict). The load-bearing trust property here is the *absence of an
advance-path*: a report of any way to make a cause publicly listable, or a finding
routable, WITHOUT a recorded human verdict (or any way to record a silent rejection
with no reason) is in scope. Note that onward routing of a routable finding to real
external recipients is NOT in this repository — it is a deferred, network-touching,
independently security-reviewed phase. This gate only produces the human-verified
ROUTABLE/REJECTED state.

It also includes the **routing / action spine** (`cairn.routing`): the
`RecipientChannel` delivery seam, the locality-aware routing policy, and the
fail-closed dispatch driver (`dispatch_routable_finding`). The load-bearing trust
properties here are (1) **fail-closed routable-only dispatch** — only a finding that
is human-verified ROUTABLE (reusing `FindingVetQueue.is_routable`) may be dispatched;
a report of any way to route/deliver/record an action for a PENDING or REJECTED
finding is in scope; and (2) **no silent drop** — every routable finding routes to a
matched recipient OR an explicitly-recorded fallback escalation, never nowhere; a
report of any way to make a routable finding vanish without a recorded routing event
(or a misconfigured registry that drops rather than raising) is in scope. The
`RecipientChannel` seam is the place where, in a later phase, real network egress will
live — and is therefore a deliberately scoped trust boundary worth naming: the ONLY
channel shipped today is the deterministic, OFFLINE `InMemoryRecipientChannel` (no
network, no real recipient, no randomness). Real external-recipient integration /
network egress (Safe Browsing / abuse.ch / registrars / partner endpoints) is a
deferred, independently security-reviewed phase and is NOT yet in this repository.

Out of scope here: third-party runtimes a contributor chooses to run, and the
operational deployment of any specific cause (those carry their own policies).

## What the human gate does — and does NOT — guarantee today

The two fail-closed gates require a **recorded human verdict** before a cause
becomes listable or a finding becomes routable. That is real and load-bearing —
but the word "human-verified" throughout this repository means precisely **"a
recorded human verdict (with a reason) exists,"** and nothing stronger. To be
explicit (these are owned boundaries, not defects):

- **The "human" is unauthenticated.** `reviewer_id`, `granted_by`, `created_by`,
  and `decider` are caller-supplied free-text strings; the engine authenticates
  none of them. A "human verdict" is structurally indistinguishable from an
  automated caller passing a name. (See THREAT-MODEL **INV-Z5**, an explicit
  placeholder.)
- **No enforced separation of duties.** Nothing prevents one actor from
  requesting, vetting, and dispatching under different names. The five-frame
  gate-check enforces that all five frames were *addressed*, not that an
  independent human addressed them.
- **The transparency log proves integrity, not truth, and has no external
  anchor.** `verify_log` proves no entry was edited/removed/reordered; it does
  not prove the finding was correct or the reviewer real. With no external
  anchoring (THREAT-MODEL **INV-U3**), a single operator holding the file could
  rewrite the chain from genesis undetectably to anyone holding only that copy.
- **Attestation is HMAC (symmetric).** It proves a key-holder signed — for a
  single operator, "the operator signed its own work" — **not** third-party
  non-repudiation. Asymmetric signing is a deferred phase.

Wherever this repository uses the **`court_grade_auditable`** frame name, read it
as **aspirational**: the code delivers a *tamper-evident, append-only audit log
with human sign-off required before any action*, with **identity-authentication,
external anchoring, and non-repudiation all deferred**. It is not a verified
evidentiary property and should not be presented as one until counsel and a
security reviewer confirm what would actually meet an evidentiary bar.

## Known, deferred security gaps (named, not hidden)

These are known and deliberately deferred to later, independently reviewed phases —
named here so a reviewer sees them as on-the-radar, not as discoveries:

- **Authenticated identity + separation of duties** (INV-Z5; asymmetric signing).
- **Target-protection against misuse** of the engine to act on a legitimate
  party (INV-Z6) — no code-level mechanism today.
- **External anchoring / third-party witnessing of the log head** (INV-U3) — and
  the related compromised-/multi-operator trust assumption.
- **Anti-abuse at intake**: rate-limiting / coordination-detection to keep the
  routing spine from becoming a brigading machine (INV-A3).
- **Abuse-response**: retraction of a dispatched action, appeal for a
  wrongly-targeted party, key-rotation, and log/incident recovery.

The reviewer-facing summary is in the [README](../README.md); the full register
is in [docs/THREAT-MODEL.md](docs/THREAT-MODEL.md). The **acceptable-cause /
prohibited-target policy** is an open governance decision flagged in
[GOVERNANCE.md](GOVERNANCE.md).

## Supported versions

Pre-1.0: only the latest released minor receives security fixes. This will be
revised at 1.0.
