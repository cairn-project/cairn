---
name: Cause request
about: Propose a new cause for the Cairn network to take on
title: "[cause] "
labels: cause-request
---

<!--
A cause is a mission-neutral unit of work the network can run. This issue is the
human-readable front door; an approved cause is recorded on-ledger via
`cairn cause-request` and decided through the five-frame gate. The fields below
mirror the cause draft the engine actually consumes (see src/cairn/cause/model.py).
A cause is only ever publicly listable AFTER a recorded human cause-vetter
decision approves it — filing this issue is a proposal, not an approval.
-->

## Cause name

A short, mission-neutral name.

## Description

What this cause asks the network to detect/analyze, in plain language.

## Target conduct

The specific conduct this cause is aimed at. Be precise.

## Protected boundary

Who or what must NOT be caught in this — the good actors and legitimate activity
the cause must never target. (Frame 2.)

## Output schema reference

What a finding for this cause looks like (a schema id or a description of the
fields a verified finding carries).

## Partner-of-record posture

Which institution(s) a verified finding would be routed to, and the
strict-vetting posture for that partner. (If unknown, say so.)

## Five-frame self-assessment

For each frame, state your claim and whether you believe it passes:

- **works** — can this actually be detected reliably?
- **doesnt_target_good_people** — does it avoid harming good actors / protect the vulnerable?
- **legal** — is the activity lawful in the relevant jurisdiction(s)?
- **court_grade_auditable** — is the evidence trail auditable and tamper-evident?
  (Note: today the engine delivers a tamper-evident, append-only audit log;
  identity-authentication, external anchoring, and non-repudiation are deferred
  phases, so "court-grade" is an aspirational target, not a verified property.)
- **human_verified** — is a human in the loop before any action is taken? (Note:
  the gate records a human verdict; the human is currently unauthenticated
  free-text — see SECURITY.md for the precise boundary.)

## Anything else

Context, prior art, urgency, locality considerations.
