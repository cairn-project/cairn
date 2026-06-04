# Governance

cairn is maintained by a single maintainer, [@lukeivers](https://github.com/lukeivers), who holds final authority over the project's direction, design, releases, and which contributions are accepted.

## Decisions
For a project of this size, decisions are made directly by the maintainer, who reviews issues and pull requests and decides on them. There is no formal committee or voting process.

## Contributing
Contributions are welcome via pull request. The maintainer reviews, requests changes where needed, and merges. Use the issue templates to report problems or propose changes.

## Evolving this model
This is the governance of a new, single-maintainer project. If a sustained group of contributors forms, the model can be revisited — for example adding co-maintainers or a documented decision process — and the change recorded here.

## What the safety gates do NOT guarantee (governance honesty note)
cairn is a trust-critical, **mission-neutral** engine: it coordinates distributed
detection and can turn a flagged target into a recorded action dispatched to a
third party. The safety story rests on a human sign-off gate, but be precise
about its current limits — these are **owned design boundaries, not hidden
defects**:

- **Identity is unauthenticated free-text.** Every actor (`reviewer_id`,
  `granted_by`, `created_by`, `decider`) is a caller-supplied string with no
  authentication. A recorded "human verdict" proves a string was present, not
  that a real, independent, or qualified human acted.
- **One gate, no enforced separation of duties.** Nothing prevents the same
  person from requesting, vetting, and dispatching.
- **The audit log proves integrity, not truth**, and has no external anchoring
  yet — a single operator who holds the file could in principle rewrite it.
- **The engine is general enough to target a real person.** The conduct a cause
  targets is free-text; the engine imposes no limit on it. The current shipped
  scope is the **benign OSS-license-classification pilot**, which exercises none
  of that surface — but the general engine's misuse surface is real.

The full invariant register, including the explicit `[PLACEHOLDER]` invariants,
is in [docs/THREAT-MODEL.md](docs/THREAT-MODEL.md); the reviewer-facing summary
of known, deferred gaps is in the [README](README.md).

## Acceptable-cause / prohibited-target policy — OPEN (owner decision required)
> **STATUS: NOT YET WRITTEN — flagged open, needs the maintainer's input.**
>
> Because the engine is mission-neutral and general (it can be pointed at any
> target conduct a cause defines), it needs an explicit, written policy stating:
> (a) what categories of conduct a cause may target, (b) what targets are
> **categorically off-limits** (e.g. protected groups, individuals absent
> due-process posture, lawful activity), and (c) the acceptance bar a cause must
> clear before any human vetter may approve it.
>
> This is a **governance decision, not code** — it is the maintainer's to make,
> and it is **deliberately not drafted here** so it is not pre-decided by
> tooling. Until it exists, the only barrier to an abusive cause is the
> (unauthenticated, single-actor-capable) human cause-vetter. Writing this policy
> is a prerequisite before any non-benign cause is accepted. **Owner: please
> author this section.**

## Multi-operator / contributor-and-operator terms — OPEN (counsel + owner)
This project is single-maintainer today, but recruits strangers to act as both
**operators and reviewers** of a trust-critical action system. The operator/
reviewer **authorization scope, qualification, offboarding, acceptable-use, and
data-processing/indemnification terms** are not yet defined and need owner +
legal-counsel input before a multi-operator deployment. Named here so the gap is
visible, not discovered.
