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

### Notes
- Honest limitations are documented in `docs/THREAT-MODEL.md`.
