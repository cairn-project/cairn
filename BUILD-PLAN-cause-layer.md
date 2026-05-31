# BUILD-PLAN — Cause Layer (first cause-layer wave)

Composes on the committed engine (waves 1–6: spec, execute/adapter, verify,
ledger + transparency log, pilot, CLI; 159 tests). This wave adds the **CAUSE
data model + registry + public list + request intake + gated-listing gate**,
built ON TOP of the existing `TransparencyLog` (`CAUSE_REQUEST` /
`CAUSE_DECISION` kinds already exist) and `BlobStore` (content-addressing). It
is **mission-NEUTRAL** — a "cause" is a generic first-class object; scam/SN
detection logic, the vetting UI, the detection-vetting workflow, distribution
ramps, and the action engine are **LATER waves, explicitly out of scope here.**

## Design traceability

Every module maps to a named PLAN / REQUIREMENTS element:

| Module | Design source |
|---|---|
| `Cause` first-class object | PLAN §2 ("a cause is a first-class object": id, name, status, 5-frame gate compliance record, partner-of-record posture, output_schema ref) |
| 5-frame self-assessment + gate-check | PLAN §6 (the five-frame acceptance gate) + REQUIREMENTS "ACCEPTANCE GATE — five non-negotiable frames" |
| target-conduct + protected-boundary fields | PLAN §5.1 (conduct-only target) / REQUIREMENTS Frame 2 — generic here (no SN specifics) |
| Registry + `list_causes(status_filter)` | PLAN §3.9(a) cause directory/marketplace; §3.8 multi-cause; only approved/live publicly listable |
| `submit_cause_request` → `CAUSE_REQUEST` | PLAN §3.9(c) cause-vetting; REQUIREMENTS §3(c) "cause REQUESTS are open and transparent" |
| `decide_cause` → `CAUSE_DECISION` | PLAN §3.9 "both approvals AND rejections are public, each with a clear recorded reason"; no-silent-rejection |
| Gated listing (cannot list/accept-compute until approved) | PLAN §3.9(c) "Cause listing MUST be gated"; §1 sequencing "Cause listing itself is gated" |
| 5-frame-gate-check structure (decider passes a checklist) | PLAN §6 table + §3.9 "same discipline as partner-vetting, applied to the demand side"; structure enforced, human judgment is the decider's |
| transparency-log verification over cause entries | PLAN §3.6 (ONE log, TWO uses) — reuse `verify_log`, no silent rejection |
| CLI `causes` / `cause-request` / `cause-decide` | PLAN §3.9(a/c); composes on existing `cairn` CLI |

## File layout

```
src/cairn/cause/
  __init__.py        exports: Cause, CauseStatus, FiveFrameAssessment,
                     FrameVerdict, CauseRegistry, gate_check, GateCheckResult
  model.py           Cause dataclass + CauseStatus + 5-frame assessment types
  gate.py            five_frame_gate_check(...) — structured checklist enforcer
  registry.py        CauseRegistry — persist (content-addressed) + intake +
                     decide + list_causes, all over the real Ledger/translog
```
CLI additions land in `src/cairn/cli.py` (compose on the existing parser).
Tests in `tests/test_cause_model.py`, `tests/test_cause_registry.py`,
`tests/test_cause_gate.py`, and cause cases appended to CLI testing via a new
`tests/test_cli_cause.py`.

## The `Cause` type (model.py)

`CauseStatus` enum (str): `REQUESTED`, `APPROVED`, `REJECTED`, `LIVE`, `PAUSED`.

Public-listability rule: a cause is **publicly listable / accepting-compute**
iff status ∈ {`APPROVED`, `LIVE`}. `REQUESTED` / `REJECTED` / `PAUSED` are NOT
publicly listable (visible only in request/decision history via the translog).

`FrameVerdict` (per-frame self-assessment): `frame` (one of the 5 frame keys),
`claim` (free-text self-assessment), `passes` (bool the requester asserts).
Five frame keys: `works`, `doesnt_target_good_people`, `legal`,
`court_grade_auditable`, `human_verified` (mirror PLAN §6 / REQUIREMENTS gate).

`FiveFrameAssessment`: the five `FrameVerdict`s (requester's self-assessment —
PLAN §2 "its own 5-frame gate compliance record").

`Cause` (frozen dataclass):
- `cause_id` (content-addressed id, derived from the canonical draft bytes)
- `name`, `description`
- `status` (CauseStatus)
- `five_frame` (FiveFrameAssessment — requester self-assessment)
- `target_conduct` (str — the conduct definition; generic)
- `protected_boundary` (str — who/what must never be targeted; generic)
- `output_schema_ref` (str — content-address / name of the output schema; the
  cause's work-units bind to this; PLAN §3.3 output_schema)
- `partner_of_record_posture` (str — federated/cause-scoped posture note; PLAN §7)
- `created_at` (float — from injected clock), `created_by` (str)
- `decided_at` (float | None), `decided_by` (str | None),
  `decision_reason` (str | None)

`to_dict` / `from_dict` for canonical-JSON content-addressing + persistence.
`is_publicly_listable` property = status ∈ {APPROVED, LIVE}.

## The 5-frame gate-check (gate.py)

`five_frame_gate_check(assessment, decider) -> GateCheckResult` — the STRUCTURE
enforcer. It does NOT make the human judgment (PLAN §3.9: "the human judgment is
the decider's, but the STRUCTURE is enforced"). It verifies the decider supplied
a verdict for **all five** named frames (no frame skipped) and records the
per-frame decider verdicts. `GateCheckResult`: `all_frames_present` (bool),
`frames_passed` (list), `frames_failed` (list), `complete` (bool — every frame
addressed). A gate-check that omits any of the five frames is INCOMPLETE; the
decider cannot approve on an incomplete checklist (enforced in `decide_cause`).

## Registry / intake / decision flow (registry.py)

`CauseRegistry(ledger)` — wraps the real `Ledger` (uses `ledger.blobs` for
content-addressed cause storage + `ledger.translog` for the public append-only
record). State (cause status) is held in a small on-ledger index
(`causes/<cause_id>` ref → current cause blob key), rebuilt-verifiable from the
translog.

1. `submit_cause_request(draft) -> Cause`
   - builds a `Cause` with status=REQUESTED, content-addressed `cause_id`,
     `created_at` from the clock.
   - stores the cause blob (content-addressed), writes the `causes/<id>` index.
   - appends a `CAUSE_REQUEST` translog entry (public, append-only) carrying
     {cause_id, name, blob_key, created_by}.
   - returns the Cause. A requested cause is **NOT** publicly listable.

2. `decide_cause(cause_id, approve, reason, decider, gate_result) -> Cause`
   - REQUIRES a non-empty `reason` (no silent decision) AND a COMPLETE
     `gate_result` (all five frames addressed) — else raises.
   - on approve → status flips APPROVED (listable); on reject → REJECTED
     (stays unlistable). Records `decided_at/by` + `decision_reason`.
   - re-stores the updated cause blob, updates the index.
   - appends a `CAUSE_DECISION` translog entry carrying {cause_id, approved,
     reason, decider, frames_passed, frames_failed} — approval OR rejection,
     WITH the reason (PLAN §3.9 no-silent-rejection).
   - **Gated listing:** only approval flips `is_publicly_listable` true.

3. `list_causes(status_filter=None) -> list[Cause]`
   - default (no filter) returns ONLY publicly-listable causes (APPROVED/LIVE)
     — the PUBLIC cause list.
   - an explicit `status_filter` (e.g. REQUESTED, REJECTED) returns the
     request/decision history view for that status (visible, but those are not
     "accepting compute").

4. `get_cause(cause_id)` / `verify_transparency()` (delegates to `verify_log`
   over the ledger's translog — the no-silent-rejection guarantee).

## CLI additions (cli.py)

Compose on the existing argparse parser; each command is thin (parse → library
call → print → exit code), mirroring the existing command style. A shared
`--ledger` opens a real `Ledger` with the existing `_DEMO_KEY` + `FixedClock`.

- `cairn causes [--ledger DIR] [--status STATUS] [--json]` — list public causes
  (or a status-filtered history view). Exit 0.
- `cairn cause-request <file> [--ledger DIR] [--by WHO] [--json]` — read a cause
  draft JSON file, submit it, print the new cause_id + REQUESTED status. Exit 0.
- `cairn cause-decide <cause_id> --approve|--reject --reason TEXT --by WHO
  [--ledger DIR] [--frame-pass k ...] [--json]` — record the reasoned decision
  via a complete 5-frame gate-check. Exit 0 on a recorded decision; nonzero if
  the gate-check is incomplete or the reason is empty.

The draft-file format: a JSON object with name/description/target_conduct/
protected_boundary/output_schema_ref/partner_of_record_posture + a `five_frame`
object of the five requester self-assessment verdicts. A benign sample draft
ships at `src/cairn/fixtures/cause_draft_benign.json` (mission-neutral — e.g. a
generic "open-data link-rot audit" cause) so the flow is exercisable offline.

## Test list

`test_cause_model.py`
- a fresh Cause defaults to REQUESTED and is NOT `is_publicly_listable`.
- APPROVED / LIVE are publicly listable; REJECTED / PAUSED are not.
- `to_dict`/`from_dict` round-trips; content-addressed id is stable for the
  same draft bytes.

`test_cause_gate.py`
- a gate-check addressing all five named frames is `complete`.
- a gate-check omitting any frame is INCOMPLETE (`all_frames_present` false).
- frames_passed / frames_failed partition correctly.

`test_cause_registry.py`
- `submit_cause_request` → cause is REQUESTED, NOT publicly listable, and a
  `CAUSE_REQUEST` entry is on the translog.
- approval (`decide_cause(approve=True, ...)`) → cause becomes listable AND a
  `CAUSE_DECISION` entry with `approved=true` + the reason is logged.
- rejection → cause stays UNlistable AND a `CAUSE_DECISION` with `approved=false`
  + the reason is logged (no silent rejection).
- `decide_cause` with an EMPTY reason raises (no silent decision).
- `decide_cause` with an INCOMPLETE gate-check (a frame omitted) raises (gate
  structure enforced).
- `list_causes()` default returns only APPROVED/LIVE; a REQUESTED cause is
  absent from the public list but present under `list_causes(REQUESTED)`.
- **transparency:** after a request + an approval + a rejection, `verify_log`
  over the ledger translog is `ok` (the chain incl. cause entries verifies).
- **OUTCOME-ALTITUDE e2e:** on a fresh ledger, request → decide(approve) →
  list_causes() returns the now-listable cause, driving the real registry +
  real translog with no pre-arranged state.

`test_cli_cause.py`
- `cairn cause-request <draft>` on a fresh ledger → exit 0, prints REQUESTED +
  a cause_id; the cause is NOT in `cairn causes` output yet.
- `cairn cause-decide <id> --approve --reason ... --by ...` with all five frames
  passed → exit 0; `cairn causes` now lists it.
- `cairn cause-decide <id> --reject --reason ...` → exit 0; the rejected cause
  stays out of `cairn causes`; the decision (with reason) is on the verifiable
  translog (`cairn verify-log` exit 0).
- a decide with an empty reason or an incomplete gate (missing frame) → nonzero
  exit (no silent decision; structure enforced).
- OUTCOME-ALTITUDE: the request→decide→list flow runs via the REAL CLI
  subprocess on a fresh ledger dir.

## Deferrals (OUT OF SCOPE this wave — STOP here)

- Scam/SN-specific detection logic + the capture fleet (LATER mission wave).
- The vetting UI + the detection-vetting workflow.
- Distribution / onboarding storefronts (PLAN §3.7).
- The escalation + action engine (PLAN §4).
- Federated partner sourcing + the matching method (PLAN §7) — only a generic
  `partner_of_record_posture` string field is carried, no sourcing logic.
- Contributor opt-in / capacity direction (PLAN §3.9(b)).
- Real anchor-institution identity / multi-vetter federation (PLAN §3.9 "later").
- Network mirroring / transport (filesystem-local only, consistent with the
  engine's current posture).

## Constraints honored

- Composes on the real engine (`Ledger`, `TransparencyLog`, `BlobStore`,
  `FixedClock`, the existing `KIND_CAUSE_REQUEST` / `KIND_CAUSE_DECISION`
  kinds) — reimplements none of it.
- NOT loam; no loam import.
- Mission-neutral — no scam/SN/sensitive specifics; benign sample draft only.
- Offline, stdlib + existing deps only; deterministic via `FixedClock`.
- No secrets (reuses the existing public `_DEMO_KEY` demo key).
- Branch + PR only; no push to main; no merge (Ren reviews + merges).
