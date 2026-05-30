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

### Notes
- Honest limitations are documented in `docs/THREAT-MODEL.md`.
