# Security Policy

Cairn is a trust-critical project. We take security reports seriously and practice
coordinated disclosure.

## Reporting a vulnerability

**Do not open a public issue for security vulnerabilities.**

- Preferred: use GitHub's **private security advisories** ("Report a vulnerability"
  on the Security tab) once the repository is public.
- Or email: `[SECURITY CONTACT — owner to fill]`.

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
real headless-browser / network-egress capture port is a deferred, separately
security-reviewed wave and is NOT yet in this repository.

It also includes the **human-in-the-loop two-gate vetting queue** (`cairn.vetting`):
the two fail-closed human-review gates (the cause-vetting gate `CauseVetQueue` whose
`apply_cause_verdict` is the only path feeding the existing cause decision, and the
finding-vetting gate `FindingVetQueue` whose `is_routable` is true only after a
recorded human verdict). The load-bearing trust property here is the *absence of an
advance-path*: a report of any way to make a cause publicly listable, or a finding
routable, WITHOUT a recorded human verdict (or any way to record a silent rejection
with no reason) is in scope. Note that onward routing of a routable finding to real
external recipients is NOT in this repository — it is a deferred, network-touching,
separately security-reviewed wave; this gate only produces the human-verified
ROUTABLE/REJECTED state.

Out of scope here: third-party runtimes a contributor chooses to run, and the
operational deployment of any specific cause (those carry their own policies).

## Supported versions

Pre-1.0: only the latest released minor receives security fixes. This will be
revised at 1.0.
