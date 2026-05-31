# Changelog

All notable changes to this project are documented here. Format based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). Pre-1.0 (0.x): minor
versions may include breaking changes; patch versions are fixes.

## [Unreleased]

The initial pre-1.0 engine (Layer A) — the reusable, model-agnostic distributed
detection-and-analysis core.

### Added
- **Work-unit + acceptance-contract spec** — the versioned, runtime-agnostic
  interface (JSON Schema) defining a unit of AI work and its machine-checkable
  acceptance contract.
- **Execute / adapter layer** — a model-agnostic adapter seam; a deterministic mock
  adapter; and a live `claude -p` adapter (spawn-isolated by construction).
- **Verify layer** — redundancy + model-diversity quorum, semantic agreement (not
  bit-equality), honeypot/gold-standard scoring, reputation, and a tiebreak policy.
- **Ledger + transparency** — content-addressed blob store, atomic exclusive claim
  with leases, HMAC attestation seam, and an append-only hash-chained
  Certificate-Transparency-style log with independent `verify_log` verification.
- **Runnable benign pilot** + the `cairn` CLI (`pilot`, `live-smoke`, `verify-log`,
  `inspect`).
- **Cause layer** (PLAN §2 / §3.9 / §6) — a mission-neutral `Cause` first-class
  object (id, status, 5-frame self-assessment, target-conduct + protected-boundary,
  partner-of-record posture), a `CauseRegistry` composing on the existing ledger +
  transparency log, request intake (`CAUSE_REQUEST`), a gated reasoned decision
  (`CAUSE_DECISION`, approval OR rejection WITH reason — no silent rejection), a
  five-frame gate-check structure enforcer, a gated public `list_causes`
  (approved/live only), and CLI commands `causes` / `cause-request` /
  `cause-decide`.
- **Cause-bound execution + contributor opt-in** (PLAN §2 / §3.3 / §3.8 / §3.9b) —
  a cause ⇄ work-units binding (`WorkUnitProvider` + `WorkUnitRegistry`, with a
  mission-neutral `PilotWorkUnitProvider` re-stamping the benign pilot units onto
  a bound cause); an explicit, gated, revocable contributor opt-in
  (`OptInRegistry` / `ConsentRecord` — opt-in to a non-listable cause is REFUSED;
  `CONSENT_RECORDED` / `CONSENT_REVOKED` on the same transparency log); a
  cause-scoped run loop (`run_cause` — verifies listable + opted-in, then drives
  the cause's units through the existing execute → verify → ledger/translog path);
  and the `cairn contribute <cause_id> [--adapter mock]` CLI command.
- **Inert evidence-bundle (examination-packet) capture abstraction** (PLAN §3.5 /
  §3.6 / §3.9b) — the seam by which a trust-gated CAPTURE operator freezes a live
  target into a STATIC, INERT, content-addressed `ExaminationPacket` that the open
  analysis layer judges WITHOUT anyone re-visiting the live target. Comprises the
  inert artifact (`Observation` + `ExaminationPacket` + a read-only `AnalysisView`
  with no live-locator / fetch surface — "re-visit the live target" is not
  expressible on the analysis path), a `CapturePort` seam with a deterministic,
  OFFLINE `StaticDocumentCapturePort` (reads a synthetic LOCAL document fixture; no
  real browser, no real URL fetched, no network egress), a fail-closed trust-gated
  CAPTURE role (`CaptureGate` / `CaptureGrant` — producing a packet is privileged,
  analyzing is open; `CAPTURE_ROLE_GRANTED` / `CAPTURE_ROLE_REVOKED` on the same
  transparency log), and the `capture_packet` (gated produce → content-address in
  the ledger blob store → `PACKET_CAPTURED` log entry) + `load_packet_for_analysis`
  (open load → `AnalysisView`) flow. The real headless-browser / IP-masked capture
  port is a deliberately deferred, separately-security-reviewed later wave.
- **Human-in-the-loop two-gate vetting queue** (REQUIREMENTS Frame 5 / PLAN §3.9) —
  the "human-verified" safety frame made concrete and STRUCTURAL: two distinct
  fail-closed review gates, each enforcing that nothing advances without a recorded
  human verdict (the guarantee is the ABSENCE of an advance-path, not policy).
  (1) A **cause-vetting gate** (`CauseVetQueue`) queues a REQUESTED cause for human
  review, supports reviewer assignment, and records a human verdict; its
  `apply_cause_verdict` is the ONLY path from the queue into the EXISTING
  `CauseRegistry.decide_cause` and refuses unless a human verdict was recorded, so
  no cause becomes publicly listable without a recorded human cause-vetter verdict.
  (2) A **finding-vetting gate** (`FindingVetQueue`) flags a mission-neutral
  `Finding` (a `packet_hash` reference + a generic `AutomatedVerdict`
  {flag_label, confidence} — no domain detection logic), supports reviewer
  assignment, and records a human verdict; a finding is `is_routable` ONLY after a
  recorded human ROUTABLE verdict (fail-closed PENDING by default; no setter marks
  a finding routable without a verdict). A rejection at either gate REQUIRES a
  reason (no silent rejection). Every queue event + verdict is recorded on the SAME
  append-only transparency log (`CAUSE_VET_ENQUEUED` / `CAUSE_VET_ASSIGNED` /
  `CAUSE_VET_VERDICT` / `FINDING_FLAGGED` / `FINDING_VET_ASSIGNED` /
  `FINDING_VET_VERDICT`), covered by the unchanged `verify_log`. The actual onward
  routing of a routable finding to real external recipients is a deliberately
  deferred, network-touching, separately-security-reviewed later wave.

- **Public transparency read-surfaces** (REQUIREMENTS Frame 4 / PLAN §3.6 / §3.9) —
  the "court-grade / auditable / maximally transparent" frame made concrete as a
  READ-ONLY projection (`cairn.public` + a `cairn public ...` CLI surface) that lets
  anyone independently verify Cairn's integrity WITHOUT privileged access. It adds
  NO write path, NO mutation, and NO new trust surface; it composes on existing
  state and reimplements nothing. Three surfaces: (1) **published causes**
  (`list_published_causes` → `PublicCauseView`) reusing the EXISTING listing gate
  `CauseRegistry.list_causes` (approved/live only — a requested/rejected/paused
  cause never appears), exposing only the public summary (id, name, description,
  status, the 5-frame self-assessment, partner-of-record posture, non-sensitive
  self-frame counts) and OMITTING internal decision/requester provenance; (2)
  **vetted outcomes** (`list_vetted_outcomes` → `PublicVettedOutcomeView`) reusing
  the finding-vetting verdict state (`FindingVetQueue.list_reviewed` — a new
  read-only inverse of `list_pending`), exposed as REDACTED metadata ONLY
  (packet-hash reference, opaque generic flag label, verdict, reviewer-of-record id,
  timestamp); and (3) **public log verification** (`public_verify_log` reusing the
  EXISTING independent `verify_log` verbatim) plus a redacted append-only log view
  (`list_public_log` → `PublicLogEntryView`: index / kind / entry_hash / prev_hash /
  recorded_at — the hash-chain skeleton, NO payload). **Redaction is by
  construction**: the public view dataclasses have NO FIELD that could carry raw
  captured content, observation bytes, analysis text, or PII — the safety is the
  projection's shape, not a call-time filter. CLI: `cairn public causes` /
  `public outcomes` / `public verify-log` / `public log`. A served web/HTTP read
  API + HTML rendering of these surfaces is a deliberately deferred later wave.

### Notes
- Honest limitations are documented in `docs/THREAT-MODEL.md`.
