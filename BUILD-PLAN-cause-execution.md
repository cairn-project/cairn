# BUILD-PLAN — cause-bound execution + contributor opt-in

Branch: `feat/cause-execution`. PR-only (main is branch-protected). Composes on
the engine (execute/verify/ledger) AND the cause layer (model/registry/gate);
forks nothing. Mission-NEUTRAL — the existing benign pilot cause
(OSS-license-classification) is the worked example. NO scam/SN/sensitive logic,
NO capture fleet, NO vetting UI, NO distribution ramps, NO escalation/action
engine (all later waves).

Traces to: PLAN §2 (cause owns its work-units), §3.3 (work-unit shape),
§3.8 (multi-cause), §3.9b (explicit contributor OPT-IN — informed consent to a
SPECIFIC cause, never silent enlistment; opt-in only to a *listable* cause).

---

## 1. What this PR connects

The cause layer can already request/approve/list a cause; the engine can already
run+verify+record a work unit; the pilot already drives the engine end-to-end on
ONE hard-coded benign cause. This PR closes the gap between them:

1. **Cause ⇄ work-units binding** — a general way for a *listable* cause to have
   a SOURCE of work units (PLAN §2: "a cause owns its work-units").
2. **Contributor opt-in** — an explicit, recorded, revocable consent (PLAN §3.9b:
   "explicit contributor OPT-IN. Informed consent to exactly what their AI will
   do + which cause — never silent enlistment"). Opt-in to a non-listable
   (requested/rejected/paused) cause is REFUSED (the §3.9 gate, demand side).
3. **Cause-scoped run loop** — `run_cause(...)`: gate-check (listable + opted-in)
   → pull the bound cause's units → run each via `run_work_unit` → verify via
   `verify_unit` → record results+verdicts against the cause on the ledger +
   transparency log. Composes; reimplements nothing.
4. **CLI** — `cairn contribute <cause_id> [--adapter mock]`: opt in + run that
   cause's available units offline, end-to-end.

---

## 2. File layout

```
src/cairn/cause/binding.py        NEW  WorkUnitProvider protocol + WorkUnitRegistry
                                       (cause_id -> provider); PilotWorkUnitProvider
                                       wrapping the existing benign pilot units.
src/cairn/cause/__init__.py       EDIT export binding symbols.

src/cairn/contribute/__init__.py  NEW  package docstring + re-exports.
src/cairn/contribute/model.py     NEW  ConsentRecord (node_id + cause_id + ts +
                                       agreed_summary + active) + to/from_dict.
src/cairn/contribute/optin.py     NEW  OptInRegistry: opt_in (REFUSES non-listable),
                                       revoke, is_opted_in, get_consent. Persists
                                       over ledger.blobs; logs CONSENT_RECORDED /
                                       CONSENT_REVOKED to the SAME translog.
src/cairn/contribute/run.py       NEW  run_cause(...) -> CauseRunSummary. Gate +
                                       provider pull + the per-unit loop reusing
                                       the pilot's exclusive-claim/run/verify path.

src/cairn/ledger/translog.py      EDIT add KIND_CONSENT_RECORDED / _REVOKED
                                       (cause-governance vocabulary; same chain).

src/cairn/cli.py                  EDIT add `cairn contribute <cause_id>
                                       [--adapter mock] [--node ID] [--ledger DIR]
                                       [--json]`.
pyproject.toml / scripts          unchanged (entry point already `cairn.cli:main`).

src/cairn/fixtures/               REUSE cause_draft_benign.json as the approvable
                                       cause; the bound provider supplies the
                                       pilot OSS-license units for ANY cause id the
                                       caller binds to the pilot provider.

tests/test_cause_binding.py       NEW
tests/test_contribute_optin.py    NEW
tests/test_contribute_run.py      NEW
tests/test_cli_contribute.py      NEW (incl. the outcome-altitude e2e)
```

---

## 3. The binding design (general, not pilot-specific)

`WorkUnitProvider` is a tiny protocol: `cause_id: str` + `work_units() ->
list[dict]` (raw wave-1 work-unit dicts). `WorkUnitRegistry` maps
`cause_id -> WorkUnitProvider` (in-memory; binding is a runtime wiring concern,
not ledger state — keeps it general and lets a future cause supply units from any
source). `PilotWorkUnitProvider(cause_id)` wraps the existing
`build_pilot_units()` so the benign pilot's units become "the units for this
cause." The pilot units carry their own `cause_id` field internally
(`PILOT_CAUSE_ID`); the provider RE-STAMPS each unit's `cause_id` + `task_id`
namespace to the bound cause so the run records against the APPROVED cause id,
not the hard-coded pilot literal. Re-stamping is a dict copy — no new spec.

Why a registry not a method on Cause: `Cause` is a frozen content-addressed
record (its id derives from immutable fields); a units-provider is runtime
behavior, not part of the cause's identity. Binding stays out of the hash.

---

## 4. opt-in flow

`OptInRegistry(ledger, cause_registry)`:

- `opt_in(node_id, cause_id, agreed_summary) -> ConsentRecord`
  1. `cause = cause_registry.get_cause(cause_id)` (raises on unknown).
  2. **REFUSE if not `cause.is_publicly_listable`** — raise `OptInRefused`
     (the §3.9 gate: consent is only valid for an approved+listable cause; a
     requested/rejected/paused cause cannot accept compute).
  3. record `ConsentRecord(active=True, ts=clock.now())`; persist over
     `ledger.blobs`; index under `<root>/consents/<node>__<cause>`; append a
     `CONSENT_RECORDED` translog entry (node + cause + agreed_summary).
- `revoke(node_id, cause_id)` — flips active False; appends `CONSENT_REVOKED`.
- `is_opted_in(node_id, cause_id) -> bool` — True iff an ACTIVE consent exists.
- `get_consent(node_id, cause_id) -> Optional[ConsentRecord]`.

`agreed_summary` is the "what it agreed to" — human-readable text describing
exactly what the node's AI will do for this cause (informed consent, §3.9b).

---

## 5. run_cause flow

`run_cause(cause_id, *, cause_registry, optin_registry, work_unit_registry,
ledger, node_families=None, node_id="contributor", bad_family=None)
-> CauseRunSummary`:

1. **Gate-check** (fail-closed):
   - `cause = cause_registry.get_cause(cause_id)`; raise `CauseRunRefused` if
     `not cause.is_publicly_listable` (cannot work a non-listable cause).
   - raise `CauseRunRefused` if `not optin_registry.is_opted_in(node_id,
     cause_id)` (no silent enlistment — must have opted in).
2. **Pull units**: `provider = work_unit_registry.provider_for(cause_id)`;
   `units = provider.work_units()` (already re-stamped to this cause_id).
3. **Per-unit loop** — REUSE the exact pilot pattern (define_task → N nodes each
   atomic-claim/run_work_unit/store_result/release → verify_unit with the cause's
   honeypot seed → record_verdict). Factor the shared per-unit body so the pilot
   runner and run_cause both call it (or run_cause calls a thin internal that
   mirrors it) — but DO NOT change run_pilot's public behavior. Lowest-risk:
   run_cause has its own loop calling the SAME engine functions (compose, not
   refactor run_pilot) — keeps the 183 green untouched.
4. **Record against the cause**: results + verdicts already carry the unit's
   `task_id`, which is now namespaced under `cause_id`; the translog entries
   (RESULT_RECORDED / VERDICT_RECORDED) therefore tie to the cause. Additionally
   append nothing new beyond what the engine already logs — the binding is the
   task_id namespace + the consent record.
5. Return `CauseRunSummary(cause_id, units=[UnitRunResult...], reputation,
   total_honeypot_catches, log_head, result_recorded, verdict_recorded,
   opted_in_node)`.

Honeypot: the pilot provider exposes its gold unit + gold answer (reuse
`honeypot_snippet` / `gold_answer` / `unit_task_id`), re-stamped to the cause id,
so the run keeps the L4 honeypot exactly as the pilot has it.

---

## 6. CLI

`cairn contribute <cause_id> [--adapter mock] [--node ID] [--ledger DIR]
[--json]`:

- opens a ledger + `CauseRegistry` + `OptInRegistry`; binds the pilot provider to
  `<cause_id>` in a fresh `WorkUnitRegistry`.
- `--adapter` only accepts `mock` in this PR (offline). Any other value → exit 2
  with a clear message (real-model contribute is a later wave; `live-smoke`
  already covers the one real spawn for the pilot).
- opts the node in (a default `agreed_summary` naming the benign work), then calls
  `run_cause`, prints the summary (or `--json`). Exit 0 on a clean run; nonzero
  with a clear message if the cause is not listable / not found (the gate).

A `contribute` against a NOT-approved cause exits nonzero (the opt-in refusal
surfaces) — this is the CLI demonstration of the §3.9 demand-side gate.

---

## 7. test list

`test_cause_binding.py`:
- `PilotWorkUnitProvider` re-stamps every unit's `cause_id` + task_id namespace to
  the bound cause; units still validate against the wave-1 spec.
- `WorkUnitRegistry.provider_for` returns the bound provider; unknown cause raises.

`test_contribute_optin.py`:
- **opt-in REFUSED for a non-listable cause** (requested, then also rejected) —
  raises `OptInRefused`; no consent recorded; translog has no CONSENT_RECORDED.
- opt-in SUCCEEDS for an approved cause; `is_opted_in` True; CONSENT_RECORDED on
  the log; the log still passes `verify_log`.
- revoke flips `is_opted_in` to False; CONSENT_REVOKED logged.

`test_contribute_run.py`:
- run REFUSED when not opted in (raises `CauseRunRefused`).
- run REFUSED when cause not listable.
- opt-in + run WORKS for an approved cause: all units ACCEPTED, the run flows
  through `verify_unit` (quorum families present), results+verdicts RECORDED
  against the cause's task_id namespace on the ledger + translog.
- a faulty node on the honeypot unit is CAUGHT (honeypot still wired).

`test_cli_contribute.py`:
- `contribute` against a requested-but-not-approved cause exits nonzero (gate).
- **OUTCOME-ALTITUDE e2e (subprocess, fresh ledger, no pre-arranged state):**
  submit → approve a benign cause via the real CLI, then `cairn contribute
  <id> --adapter mock` opts in + runs it; assert exit 0, results recorded, and
  `cairn verify-log <translog>` exits 0 (the transparency log verifies).
- `--adapter notmock` exits 2.

Keep the existing 183 green (no change to run_pilot's public behavior).

---

## 8. deferrals (STOP here — later PRs)

- real-model contribute adapter (only `mock` offline now; `live-smoke` covers the
  one real spawn for the pilot).
- capture / detection / classification logic (mission-specific; sensitive waves).
- vetting UI / cause-discovery marketplace front end (§3.9a directory beyond the
  existing `causes` list).
- distribution onboarding ramps / storefronts (§3.7).
- escalation + action engine, partner sourcing, closed-loop tracking (§4/§7).
- network transport / multi-node coordination over a wire (units run locally,
  redundancy simulated by N families as the pilot does).
- persisted/federated WorkUnitRegistry (binding is in-memory runtime wiring now).

---

## 9. constraints honored

- Composes on engine (`run_work_unit` / `verify_unit` / `Ledger`) + cause layer
  (`CauseRegistry` / `Cause.is_publicly_listable` / gate) — forks nothing.
- NOT loam; mission-neutral; benign pilot units only; no secrets; no API key.
- Every new module traces to a PLAN element (§2 / §3.3 / §3.8 / §3.9b).
- Fail-closed gate: non-listable cause or no opt-in → refused, never waved
  through.
- Branch + PR only; never main; do not merge (Ren reviews + merges).
