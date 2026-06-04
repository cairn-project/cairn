# Plan — `cairn scenario` value-demo (v0.3.0)

Contract: `cairn-value-demo-design.md` (topic A — stale/broken open-data feeds;
real-Claude analysis + real-org lookup + real human gate; dump-not-send;
structural no-egress). This plan is the implementation contract; every line of
code/test maps to a named AC below.

## Composition (reuse, fork nothing)

- detection → `StaticDocumentCapturePort` + `capture_packet` (REAL inert-packet
  path; gated capture via a granted scenario node) — new seed fixtures only.
- analysis → `ClaudeCliAdapter` (REAL isolated `claude -p`, default) + one
  distinct deterministic `reference` node → REAL `verify_unit` quorum+honeypot.
  `--offline` swaps the live node for a deterministic seeded adapter.
- flag → `flag_from_verdict` + `ThresholdFlagPolicy` (REAL bridge).
- gate → `FindingVetQueue.flag` (PENDING) / `record_verdict` (REAL Gate-2).
- recipient → `Recipient` + `InMemoryRecipientChannel` (offline sink; NOT
  delivered — only resolved + dumped).
- ledger/log → `Ledger` + `TransparencyLog` (REAL; `verify-log`-checkable).

## Key design point — the analysis output must carry a numeric score

`ThresholdFlagPolicy` flags an ACCEPTED verdict whose `accepted_output` carries a
numeric `score_field` >= threshold. The pilot's `{is_open_license, license_id}`
output has no score. So the scenario defines its OWN work-unit shape:

  output schema `{has_defect: bool, defect_kind: str, defect_confidence: number}`

The deterministic reference rule (`classify_defect`) inspects the captured
observations (a planted `download_status: 404` / malformed-license metadata
field) and emits `has_defect`/`defect_kind`/`defect_confidence`. The honeypot
gold answer = the same rule on the seeded gold record. The `ThresholdFlagPolicy`
flags on `score_field="defect_confidence"` >= 0.8. A no-defect record yields
`has_defect=false, defect_confidence=0.0` → below threshold → no flag → no
finding (fail-quiet, AC.SCN.2).

## New components (`src/cairn/scenario/`)

| module | content | ACs |
|--------|---------|-----|
| `seed.py` | seed-record dataclass + 3–5 inert open-data fixtures (some w/ planted defect) + loader; `classify_defect` rule; gold answer; `build_scenario_unit` (output schema + acceptance contract + redundancy policy diversity=2 + `defect_confidence`) | 1,2,7 |
| `node.py` | `ScenarioReferenceNode` (deterministic `Adapter` applying `classify_defect`) | 1,2,7 |
| `org_finder.py` | `ReportingOrgFinder` — resolves a `Recipient` from a PUBLIC, hand-verified seed registry keyed by steward; public-info-only contract; **fails closed** (returns `None` → no recipient) on an unresolvable record. (Live web lookup is the deferred default-on path gated behind the live tier; the seed registry is the deterministic path.) | 6 |
| `packet_builder.py` | `build_review_packet(...)` → assembles the human-readable `packet.md` (banner + evidence + analysis/verdict + resolved org + how-found + draft) + `packet.json` + `provenance.txt`; pure assembly | 1,5 |
| `dump.py` | `write_review_dump(...)` — writes the banner-labeled dir per finding (file I/O only) | 1,5 |
| `runner.py` | `run_scenario(...)` orchestrator: seed→capture→analyze(live|offline)→verify→flag→find-org→build→dump, leaving findings PENDING; `review_scenario(...)`/`list_scenario(...)` wrap the REAL `FindingVetQueue` | 1,2,3,4,7 |
| `__init__.py` | package exports | — |

CLI: `cairn scenario run|review|list` in `cli.py` (thin; no business logic).

Constants: banner `FOR REVIEW — NOT SENT — demonstration scenario, not a live cause`;
`SCENARIO_CAUSE_ID = "scenario.open-data-feed-quality"`.

## Real reporting orgs (claim-or-cite; from the design's live-search feasibility)

Seed registry (public, non-person inboxes only):
- Data.gov fallback steward → `DataGovHelp@gsa.gov` (Data.gov User Guide).
- Per-record listed point-of-contact when the fixture carries one (a public
  agency office inbox), else the Data.gov fallback.
A record whose fixture carries NO resolvable public contact → finder returns
None → dump says "no public contact resolved; do not proceed" (fail-closed).

## ACs (outcome-shaped; Cairn TDD)

- **AC.SCN.1 (outcome-altitude):** `run_scenario(..., offline=True)` on a fresh
  ledger (no pre-arranged finding) produces ≥1 finding that is PENDING and not
  routable, and writes a dump dir containing the banner, evidence, a resolved
  public recipient, and a draft — with no network and no send. Test invokes the
  real entry point; a separate CLI test drives `main(["scenario","run",...])`.
- **AC.SCN.2:** a no-defect seed record produces no finding and writes no dump
  subdir (fail-quiet).
- **AC.SCN.3:** `review_scenario(hash, routable=True, reason=…)` flips PENDING→
  ROUTABLE only via the recorded human verdict; `routable=False` with empty
  reason is refused; both log to the transparency log.
- **AC.SCN.4:** the run's transparency log passes `verify_log`.
- **AC.SCN.5 (no-egress, structural):** a test imports every `cairn.scenario`
  module and asserts NONE references a network-send surface
  (`socket`, `urllib`, `http`, `requests`, `smtplib`, `.send(`, `urlopen`),
  AND every dumped artefact carries the banner. (The only subprocess surface is
  the shared `claude_adapter`, exercised only in the non-offline live path.)
- **AC.SCN.6 (org-finder public-only / fail-closed):** finder resolves a
  recipient only from the public seed registry; an unresolvable record → None →
  dump records "no public contact resolved".
- **AC.SCN.7 (real-AI, live tier):** with a real model, `run_scenario(offline=
  False)` drives analysis through the isolated `claude -p` adapter and the verify
  quorum grades it. Offline-deterministic variant uses an injected `transcript_fn`
  so the hermetic suite never spawns a model (mirrors `test_live_smoke`).

## Version + release

pyproject `[project] version` + `__init__.__version__` → `0.3.0`; CHANGELOG
`[0.3.0]` Added section. Conventional commits, NO Co-Authored-By. PR to main;
merge only on green lint+pytest 3.11/3.12/3.13; tag v0.3.0 on merge commit +
GitHub release with honest pre-1.0 notes (sends nothing).
