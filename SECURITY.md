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
verify, ledger/transparency-log, CLI, pilot).

Out of scope here: third-party runtimes a contributor chooses to run, and the
operational deployment of any specific cause (those carry their own policies).

## Supported versions

Pre-1.0: only the latest released minor receives security fixes. This will be
revised at 1.0.
