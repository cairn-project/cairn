# BUILD-PLAN — analysis→finding bridge (the missing seam)

Branch: `feat/analysis-finding-bridge`. PR-only (main is branch-protected; do
NOT merge — Ren reviews + merges). Composes on the engine (execute/verify),
the capture layer (`ExaminationPacket` / `AnalysisView`), and the vetting layer
(`FindingVetQueue.flag` / `AutomatedVerdict`). Forks nothing; reimplements
nothing. **Mission-NEUTRAL** — the only flagging policy shipped is a generic,
opaque-label threshold over a verify verdict; the worked example stays the
existing benign OSS-license-classification pilot. NO scam/SN/sensitive/detection
domain logic, NO capture fleet, NO escalation/action engine.

Traces to: PLAN §3.5 (the verify layer's "automated verdict that flagged it"
producer), §3.6 (content-addressing), §3.9b (the human-gated Finding the bridge
emits into Gate 2). It is the named-but-unbuilt producer of the
`AutomatedVerdict` that `vetting.Finding` already references but that no code
path currently produces.

---

## 1. The gap this PR closes (Tier-0, from the source)

The engine currently has TWO working halves that never touch:

- **Half A — detect/analyze (works e2e):** cause → opt-in → bound work units →
  `run_work_unit` (adapter) → `verify_unit` (quorum + diversity + honeypot +
  reputation) → `record_verdict` on the transparency log. Driven by
  `pilot.run_pilot` and `contribute.run_cause`.
- **Half B — vet/route (works e2e):** a `Finding` → `FindingVetQueue` human
  Gate-2 review → ROUTABLE → `dispatch_routable_finding` → recipient + recorded
  action. Driven by `routing` over `vetting`.

**The missing seam:** nothing produces a `Finding` from a real verify-layer
outcome. `Finding` references a `packet_hash` (capture) + an `AutomatedVerdict`
`{flag_label, confidence}` — but no module derives that automated verdict from a
`VerifyVerdict` over a captured packet. Every existing test that needs a finding
HAND-FABRICATES one (`tests/test_routing_e2e.py` calls
`queue.flag(... AutomatedVerdict(flag_label="flagged", confidence=...))` with a
synthetic packet). This PR builds the bridge so a finding is PRODUCED by the
analysis layer, making the engine continuous from "contributor runs a unit" to
"a human reviews a real flagged finding and it is routed."

---

## 2. Design (general, mission-neutral)

A finding is emitted when an analysis verdict over a captured packet crosses a
**generic flagging policy**. The policy is the injectable seam that keeps this
mission-neutral: it maps a `VerifyVerdict` → an optional `AutomatedVerdict`
(opaque `flag_label` + `confidence` in [0,1]). It hard-codes NO domain
vocabulary — `flag_label` is an opaque string the policy is configured with, and
the threshold is a generic confidence bound. The only policy shipped is
`ThresholdFlagPolicy(flag_label, min_confidence)`: flag iff the verdict is
ACCEPTED and the accepted output carries a generic numeric `confidence`/`score`
field at or above the bound (configurable field name, default `confidence`).
"Not of interest" → no finding (returns `None`), the fail-quiet default.

`FlagDecision` is the policy's output: `Optional[AutomatedVerdict]` plus the
reason it did/didn't flag (for the audit trail). The bridge driver
`flag_from_verdict(...)` composes: given a captured `packet_hash`, a
`VerifyVerdict`, and a policy, it (a) runs the policy, (b) if it flags, calls the
EXISTING `FindingVetQueue.flag(...)` (which already content-addresses + logs
`FINDING_FLAGGED`), (c) returns the produced `Finding` (or `None`). It
reimplements no hashing, no logging, no queue state — it only DECIDES and
DELEGATES.

Why a policy seam, not a hard threshold inline: a units-of-interest decision is
runtime/cause behaviour, not engine identity — the same general engine runs many
causes each with its own flagging bar (PLAN §3.8). Keeping it an injectable
`FlagPolicy` protocol means a future cause supplies its own bar without touching
the bridge. Mission-neutrality is preserved by shipping only the generic
threshold policy.

---

## 3. File layout

```
src/cairn/analysis/__init__.py        NEW  package docstring + re-exports
                                           (FlagPolicy, ThresholdFlagPolicy,
                                           FlagDecision, flag_from_verdict).
src/cairn/analysis/policy.py          NEW  FlagPolicy protocol; FlagDecision
                                           dataclass; ThresholdFlagPolicy
                                           (generic opaque-label threshold over a
                                           VerifyVerdict; no domain vocabulary).
src/cairn/analysis/bridge.py          NEW  flag_from_verdict(packet_hash, verdict,
                                           *, finding_queue, policy, flagged_by,
                                           cause_id) -> Optional[Finding].
                                           Composes FlagPolicy + FindingVetQueue.flag.

tests/test_analysis_policy.py         NEW
tests/test_analysis_bridge.py         NEW  (incl. the detect→FLAG seam unit tests)
tests/test_analysis_e2e.py            NEW  OUTCOME-ALTITUDE: real run_work_unit +
                                           verify_unit over a real captured packet
                                           → flag_from_verdict → FindingVetQueue
                                           → human ROUTABLE → dispatch → recorded
                                           action; verify_log ok. Fresh ledger,
                                           no pre-arranged state.
```

No edits to existing modules: the bridge is purely additive and composes on the
existing public APIs (`FindingVetQueue.flag`, `VerifyVerdict`, `AutomatedVerdict`).
The existing 276 tests stay green untouched.

---

## 4. The flagging policy (analysis/policy.py)

`FlagPolicy` protocol: `decide(verdict: VerifyVerdict) -> FlagDecision`.

`FlagDecision` (frozen): `flagged: bool`, `automated_verdict: Optional[AutomatedVerdict]`,
`reason: str`. When `flagged` is False, `automated_verdict` is None and `reason`
names why (not accepted / below threshold / field absent).

`ThresholdFlagPolicy(flag_label: str, min_confidence: float, *, score_field="confidence")`:
- if `not verdict.accepted` → `FlagDecision(False, None, "verdict not accepted")`.
- read `verdict.accepted_output[score_field]`; absent / non-numeric →
  `FlagDecision(False, None, "no <score_field> in accepted output")`.
- `score >= min_confidence` → `FlagDecision(True, AutomatedVerdict(flag_label,
  score_clamped_to_[0,1]), "score >= threshold")`; else
  `FlagDecision(False, None, "score below threshold")`.

`flag_label` is opaque (caller-supplied, e.g. `"flagged"`); the policy hard-codes
no domain term. `min_confidence` is a generic bound. This is the entire
mission-neutral surface.

---

## 5. The bridge driver (analysis/bridge.py)

`flag_from_verdict(packet_hash, verdict, *, finding_queue, policy, flagged_by,
cause_id=None) -> Optional[Finding]`:
1. `decision = policy.decide(verdict)`.
2. if `not decision.flagged` → return `None` (fail-quiet: an uninteresting
   analysis produces no finding; nothing logged — symmetrical to the verify
   layer returning a non-accepted verdict without dispatch).
3. else → `return finding_queue.flag(packet_hash=packet_hash,
   automated_verdict=decision.automated_verdict, flagged_by=flagged_by,
   cause_id=cause_id)` — the EXISTING flag path does the content-addressing,
   blob persistence, and `FINDING_FLAGGED` translog entry.

The bridge owns the DECISION; the queue owns the RECORD. No new translog kind, no
new hashing, no new state.

---

## 6. test list

`test_analysis_policy.py`:
- `ThresholdFlagPolicy` flags an ACCEPTED verdict whose output score ≥ threshold;
  the `AutomatedVerdict` carries the configured opaque label + the score.
- does NOT flag a non-accepted verdict (reason names it).
- does NOT flag when the score field is absent / non-numeric (reason names it).
- does NOT flag a below-threshold score.
- a configurable `score_field` other than the default is honoured.
- the score is clamped to [0,1].

`test_analysis_bridge.py`:
- `flag_from_verdict` returns `None` and writes NOTHING to the queue/translog
  when the policy declines (no `FINDING_FLAGGED` entry).
- `flag_from_verdict` emits a real `Finding` via `FindingVetQueue.flag` when the
  policy flags: the finding references the given `packet_hash`, the queue lists it
  PENDING, and a `FINDING_FLAGGED` entry is on the log.
- the emitted finding is human-vettable → ROUTABLE through the EXISTING queue
  (the bridge produces a finding indistinguishable from a hand-built one).

`test_analysis_e2e.py` (OUTCOME-ALTITUDE, fresh ledger, no pre-arranged state):
- real `capture_packet` (gated) produces a packet → real `run_work_unit` +
  `verify_unit` over the benign pilot unit yields an ACCEPTED verdict →
  `flag_from_verdict` emits a finding → human records ROUTABLE via
  `FindingVetQueue` → `dispatch_routable_finding` routes + records the action →
  `verify_log` over the transparency log is ok. This is the FIRST test where the
  finding is PRODUCED by the analysis layer rather than hand-fabricated — it
  proves the two halves are now one continuous loop.
- NOTE (Tier-0 reconciliation): the benign pilot's REAL output is
  `{is_open_license, license_id}` — it carries no numeric score field, so the
  shipped `ThresholdFlagPolicy` (which reads a numeric `score_field`) is exercised
  by `test_analysis_policy.py` / `test_analysis_bridge.py` with score-bearing
  outputs, while the e2e uses a tiny inline `FlagPolicy`-conformant policy over the
  pilot's real boolean output. This is deliberate: it ALSO proves the `FlagPolicy`
  protocol seam is genuinely general (not coupled to the shipped threshold policy
  nor to the pilot's output shape).

Keep the existing 276 green (purely additive; no edits to existing modules).

---

## 7. deferrals (STOP here — later PRs)

- a CLI subcommand wrapping the bridge (this PR is the library seam; a
  `cairn analyze`/flag CLI is a thin later wave).
- cause-scoped automatic flagging inside `run_cause` (the bridge is composable;
  wiring it into the contributor loop is a separate, owner-reviewable decision —
  it changes `run_cause`'s public behaviour, so it is NOT bundled here).
- any domain detection/classification logic (mission-specific; sensitive waves).
- per-cause configurable flag policies persisted on the ledger (the policy is
  in-memory runtime wiring now, mirroring the WorkUnitRegistry decision).
- escalation/action engine, partner sourcing, distribution ramps.

---

## 8. constraints honored

- Composes on verify (`VerifyVerdict`) + capture (`packet_hash`) + vetting
  (`FindingVetQueue.flag` / `AutomatedVerdict`) — forks nothing, edits nothing.
- NOT loam; mission-neutral; benign worked example only; no secrets; no API key;
  no network.
- ODD-lite: every new file maps to a named element above; no speculative code for
  unnamed cases. The policy seam exists because the multi-cause flagging-bar
  decision (§2) names it.
- Fail-closed / fail-quiet: an uninteresting analysis produces NO finding; only a
  policy-flagged verdict emits one, and the EXISTING human Gate-2 still governs
  whether it ever routes.
- Branch + PR only; never main; do not merge (Ren reviews + merges).
