# Wave 1 Build Plan — cairn engine foundation (Layer A)

Wave 1 of the distributed cause-coordination engine. Builds **only** the stable
interface + scaffold + tests. Plan-before-code per the build discipline.

Package name `cairn` is the project's **final, owner-ratified name**
(mission-neutral by design — this closes what was formerly PLAN §9 / open
owner decision #9). Nothing hard-codes the name anywhere but the package path
and import root.

Traceability: every file maps to a named PLAN / REQUIREMENTS element. Listed
per-file below. No speculative code for unnamed cases (ODD-lite).

---

## 1. Scope of this wave

IN (this wave):
- Project scaffold: pyproject.toml (src layout), pytest harness, README,
  .gitignore. Python 3.11+. Stdlib-first; `jsonschema` the only runtime dep.
- The **work-unit + acceptance-contract SPEC** — the load-bearing stable
  interface (PLAN §3.3, research 02 A.1). Versioned JSON Schema + human SPEC.md.
- Python types (dataclasses, pydantic-free) for the work unit + acceptance
  predicates.
- `validate_work_unit(unit)` — checks a unit dict against the JSON Schema.
- `evaluate_acceptance(result, acceptance_contract)` — runs the
  machine-checkable predicates against a result.
- 2–3 example work-unit fixtures.
- pytest tests: schema validation (valid + invalid), acceptance evaluation
  (pass + fail), fixtures-parse. All green.

DEFERRED to later waves (explicitly NOT built here):
- **Verify layer** (k-redundancy quorum, model-diversity, LLM-judge, honeypots)
  — PLAN §3.5, phase P1. Wave 1 ships only the *fields* (`redundancy_policy`,
  `provenance_requirements`) that the verify layer will consume; no quorum logic.
- **Execute / adapter runtime** (Claude Code / OpenAI / ollama adapters,
  capability calibration probe) — PLAN §3.3/§3.4, phase P1. Wave 1 ships only
  the `capability_floor` field shape; no adapter, no runtime call, no network.
- **Ledger** (thin git-ledger coordinator, atomic claim, leases, transparency
  log) — PLAN §3.1/§3.6, phase P2. Wave 1 ships `task_id`/`deadline`/`lease`
  fields as data; no claim/CAS/git logic.
- **Distribution storefronts, cause-discovery marketplace, cause-vetting,
  partner sourcing, escalation/action engine** — PLAN §3.7–§3.9, §4, §7,
  phases P3–P6.

The wave-1 boundary is exactly the **A↔B interface** (PLAN §2: "the interface
between A and B is the work-unit + acceptance-contract spec"). Everything that
consumes the spec is a later wave.

---

## 2. File layout

```
engine/
  BUILD-PLAN.md                      this file
  README.md                          project overview, placeholder-name note, run instructions
  pyproject.toml                     src-layout package, py311+, jsonschema dep, pytest config
  .gitignore                         venv / __pycache__ / build artifacts
  src/cairn/
    __init__.py                      package version, public exports
    spec/
      __init__.py
      work_unit.schema.json          versioned JSON Schema for a work unit (the canonical artifact)
      SPEC.md                        human-readable field-by-field spec + versioning rule
    types.py                         dataclasses: WorkUnit, RedundancyPolicy, AcceptanceContract, AcceptancePredicate, ...
    validate.py                      validate_work_unit(unit) -> ValidationResult
    acceptance.py                    evaluate_acceptance(result, acceptance_contract) -> AcceptanceResult; predicate kinds
    fixtures/
      __init__.py                    load_fixture(name) helper + fixture path resolution
      benign_pilot.json              trivial benign-pilot unit (non-sensitive distributed-analysis)
      cause_threaded.json            cause_id threading + capability_floor
      structured_acceptance.json     non-trivial acceptance_contract
  tests/
    __init__.py
    test_schema_validation.py        valid units pass; invalid units (missing/typed fields) fail
    test_acceptance.py               each predicate kind: pass + fail
    test_fixtures_parse.py           every fixture validates against the schema
```

## 3. Work-unit field list (types)

Per PLAN §3.3 / research 02 A.1 — implemented exactly as the design names them,
no invented fields (information-trust):

| field | type | required | notes |
|---|---|---|---|
| `schema_version` | str (semver) | yes | versioning rule below; pins the unit to a spec version |
| `task_id` | str | yes | stable unique id; dedup/sybil anchor |
| `cause_id` | str | yes | first-class cause binding (PLAN §2) |
| `objective` | str | yes | natural-language outcome |
| `inputs` | object | yes | EITHER `inline` data OR content-addressed `pointer` + `hash` (oneOf) |
| `output_schema` | object (JSON Schema) | yes | runtime-agnostic result contract |
| `acceptance_contract` | object | yes | `{ predicates: [ ... ] }` machine-checkable |
| `capability_floor` | object | yes | `context_window` (int tokens), `tools` (str[]), `modalities` (str[]) |
| `redundancy_policy` | object | yes | `target_nresults` (int), `min_quorum` (int), `model_diversity` (bool/int) |
| `provenance_requirements` | object | yes | `model_family` (bool), `signed_result` (bool), `trace` (bool) |
| `deadline` | str (ISO-8601) | no | absolute deadline |
| `lease` | object | no | `{ duration_seconds: int }` reclaim-and-reissue |

`inputs` uses JSON-Schema `oneOf`: `{inline}` xor `{pointer, hash}` — captures
research 02 A.1 "the data to operate on (or a content-addressed pointer + hash)".

### Acceptance predicate kinds (acceptance.py)

research 02 A.1 names the validator must check "format, required fields, value
ranges, citations-required, refusal-handling". Wave-1 predicate kinds, each a
pure machine-checkable function over a result dict — no LLM, no network:

- `required_fields` — `{ fields: [path,...] }` all present (dotted paths).
- `field_type` — `{ field, json_type }` value is the named JSON type.
- `value_range` — `{ field, min?, max? }` numeric bound.
- `enum` — `{ field, allowed: [...] }` value in set.
- `non_empty` — `{ field }` string/array/object non-empty (refusal-handling: a
  refusal yields an empty/absent answer field → fails).
- `min_items` — `{ field, count }` array length floor (citations-required:
  `citations` array must have ≥1).
- `regex_match` — `{ field, pattern }` string matches (format check).

`evaluate_acceptance` returns `{ passed: bool, results: [per-predicate], ... }`.
ALL predicates must pass for the contract to pass (conjunctive). These are the
client-side cheap filter of research 02 A.1 step 4 — the verify-layer quorum
(deferred) sits ABOVE this.

## 4. Validation + acceptance approach

- `validate_work_unit`: load `work_unit.schema.json`, run `jsonschema.Draft202012Validator`,
  collect all errors → `ValidationResult(valid, errors)`. Also confirm
  `schema_version` matches the spec's MAJOR (forward-compat rule below).
- `evaluate_acceptance`: dispatch on each predicate's `kind` to a registered
  pure checker; unknown kind → hard error (fail closed, never silently pass).
  Dotted-path field resolution over the result dict.

## 5. Versioning rule (SPEC.md)

`schema_version` is semver. MAJOR bump = breaking field change (consumers must
upgrade); MINOR = additive optional field; PATCH = doc/constraint clarification.
A unit declares the version it was authored against; `validate_work_unit`
accepts a unit whose MAJOR equals the spec's MAJOR. This is the "open, versioned
spec ... anyone can write an adapter for any future runtime" property (PLAN §3.4
deliverable 1).

## 6. Test list

1. `test_schema_validation.py`
   - valid minimal unit passes
   - valid full unit (all optional fields) passes
   - missing required field (`cause_id`) fails with a useful error
   - wrong type (`target_nresults` a string) fails
   - `inputs` with neither inline nor pointer fails (oneOf)
   - `inputs` with BOTH inline and pointer fails (oneOf)
   - mismatched MAJOR schema_version rejected
2. `test_acceptance.py`
   - one pass + one fail case per predicate kind
   - conjunction: one failing predicate fails the whole contract
   - unknown predicate kind raises
3. `test_fixtures_parse.py`
   - each of the 3 fixtures validates against the schema
   - the structured-acceptance fixture's contract evaluates pass on a good
     result and fail on a bad result

## 7. Constraints honored

- New standalone project; **no import from loam**, no loam coupling.
- No secrets; no network calls anywhere in wave 1 (pure local schema work).
- No git commit (Ren reviews + commits); no public repo (owner-gated).
- Every module traces to a PLAN/REQUIREMENTS element (table §3, layout §2).

---

# Wave 2 Build Plan — execute / adapter layer (Layer A runtime seam)

Wave 2 builds the **EXECUTE / ADAPTER layer** that sits directly on top of the
wave-1 spec: the model-agnostic adapter seam (PLAN §3.3 / research 02 A.2), a
deterministic offline reference adapter, the capability model + a calibration-
probe stub, and the end-to-end execute flow that wires the new adapter to the
existing wave-1 `validate_work_unit` + `evaluate_acceptance`. Plan-before-code
per the build discipline; every file traces to a named PLAN / research element.

## 8. Scope of this wave

IN (this wave):
- **Adapter seam** (`execute/adapter.py`): an abstract `Adapter` base —
  the model-agnostic seam (PLAN §3.3 "the leverage point"; research 02 A.2 step
  2 "render", step 4 "local acceptance checks"). Takes a validated `WorkUnit`,
  declares its own `Capabilities`, and produces a `CandidateResult`. Vendor-
  neutral: a Claude Code / OpenAI / ollama / generic adapter is just a subclass.
- **Portable-payload render** (`execute/render.py`): `render_payload(unit)` →
  a `RenderedPayload` (the runtime-local prompt/call surface) built from the
  unit's `objective + inputs + output_schema + acceptance_contract` ONLY
  (research 02 A.2: that quadruple is "the entire portable payload"). Pure,
  runtime-neutral, no vendor template. Adapters consume this to build their
  native call.
- **CandidateResult type** (`execute/result.py`): the produced `output` +
  provenance placeholders (`adapter_name`, `model_family`, `adapter_version`,
  `produced_at` timestamp-placeholder, `signature` signed-result placeholder).
  Maps the wave-1 `provenance_requirements` flags to per-result attestation
  fields (research 02 A.2 step 5 "attest + sign" — placeholders only; real
  signing is the ledger wave).
- **MockAdapter** (`execute/mock_adapter.py`): a deterministic, no-network
  reference adapter. Synthesizes a schema-shaped result by walking the unit's
  `output_schema` and emitting canned-but-typed values per property (so the
  produced output satisfies the unit's own acceptance_contract for the wave-1
  fixtures). Makes the whole execute flow testable offline. The live-model
  adapters (Claude Code / OpenAI-compatible / ollama) are a FOLLOW-ON
  increment — the seam is shaped to accept them, but NONE are implemented here.
- **Capability model** (`execute/capability.py`): a `Capabilities` declaration
  (`context_window` int, `tools` str[], `modalities` str[], `model_family_tier`
  int) describing what a node offers, and
  `meets_floor(capabilities, capability_floor) -> CapabilityCheck` implementing
  Contract-Net self-selection (PLAN §3.3 F2): a node runs a unit only if it
  meets every floor dimension. Floor is the wave-1 `CapabilityFloor`.
- **Calibration-probe stub** (`execute/calibration.py`): the SHAPE of a join-
  time probe that validates a node's SELF-DECLARED capabilities (research 01
  §5.4 / PLAN §3.3 F2 — "self-declared capability is itself an untrusted
  claim"). An abstract `CalibrationProbe` interface + a trivial
  `TrivialCalibrationProbe` that checks self-declared `Capabilities` are
  internally well-formed (non-negative window, known modalities). Full
  adversarial probing (a real probe work-unit the node must pass) is deferred.
- **Execute flow** (`execute/flow.py`): `run_work_unit(unit_dict, adapter,
  probe=None) -> ExecuteOutcome`. Steps: (1) `validate_work_unit` (wave-1);
  (2) optional `probe.verify(adapter.capabilities)`; (3) `meets_floor` capability
  gate; (4) `adapter.produce(WorkUnit)` → `CandidateResult`; (5)
  `evaluate_acceptance` (wave-1) as the cheap client-side filter; (6) return the
  candidate + acceptance verdict + a status. Composes wave-1 functions; does NOT
  re-implement validation or acceptance.

DEFERRED to later waves (explicitly NOT built here):
- **Live-model adapters** — real Claude Code / OpenAI-compatible / ollama calls.
  The seam is shaped for them; no network code, no API keys, no SDK imports this
  wave. (Cairn's DESIGN permits volunteer-owned API-key + local + agentic
  runtimes — research 02 A.2; only OUR tests stay offline via MockAdapter.)
- **Verify / quorum layer** — k-redundancy, model-diversity, LLM-judge,
  honeypots (PLAN §3.5, phase P1). Wave 2 runs only the per-node client-side
  acceptance filter; the quorum that aggregates N CandidateResults across nodes
  is the NEXT wave. `redundancy_policy` is read-only data here.
- **Real attestation / signing** — `signature` + `produced_at` are placeholders;
  cryptographic signing belongs to the ledger wave (PLAN §3.6).
- **Real calibration probing** — the adversarial probe work-unit a joining node
  must actually execute and pass is deferred; only the interface + a trivial
  well-formedness check ship now.
- **Pull/submit transport** (research 02 A.2 steps 1 + 6), the task queue, the
  ledger, distribution storefronts — later waves.

## 9. File layout (wave 2 additions)

```
src/cairn/execute/
  __init__.py            public exports: Adapter, MockAdapter, Capabilities,
                         CandidateResult, RenderedPayload, meets_floor,
                         CalibrationProbe, run_work_unit, ExecuteOutcome, ...
  adapter.py             abstract Adapter base (the model-agnostic seam)
  render.py              render_payload(unit) -> RenderedPayload (portable payload)
  result.py             CandidateResult + provenance placeholders
  capability.py          Capabilities + meets_floor + CapabilityCheck
  calibration.py         CalibrationProbe interface + TrivialCalibrationProbe stub
  mock_adapter.py        MockAdapter — deterministic schema-shaped output, no net
  flow.py                run_work_unit(...) -> ExecuteOutcome (wires wave-1)
tests/
  test_render.py         portable payload built from the 4-tuple only
  test_capability.py     meets_floor qualifies / rejects per dimension
  test_mock_adapter.py   MockAdapter output is schema-valid + passes acceptance
  test_calibration.py    TrivialCalibrationProbe accepts/rejects well-formedness
  test_execute_flow.py   run_work_unit end-to-end on the 3 fixtures + fail paths
```

## 10. Types (wave 2)

`Capabilities` (frozen dataclass) — what a node offers:
| field | type | notes |
|---|---|---|
| `context_window` | int | tokens the runtime can hold |
| `tools` | list[str] | tool names the runtime exposes |
| `modalities` | list[str] | e.g. `["text"]`, `["text","image"]` |
| `model_family_tier` | int | coarse capability tier (0 = unknown/local-small) |

`CapabilityCheck` (frozen) — `qualifies: bool`, `reasons: list[str]` (one per
failed dimension). `meets_floor` checks: context_window ≥ floor (if floor sets
it), tools ⊇ floor.tools, modalities ⊇ floor.modalities. tier is informational
this wave (floor carries no tier field in wave-1 `CapabilityFloor`).

`RenderedPayload` (frozen) — `objective: str`, `inputs: dict`,
`output_schema: dict`, `acceptance_contract: dict`, plus a derived
`prompt: str` (a neutral textual rendering an adapter MAY use or override).
Built ONLY from the 4-tuple — asserting the portable-payload boundary.

`CandidateResult` (frozen) — `task_id`, `output: dict`, and provenance:
`adapter_name`, `model_family`, `adapter_version`, `produced_at` (ISO string
placeholder), `signature` (Optional[str] placeholder). A `provenance_satisfies(
provenance_requirements)` helper reports which wave-1 flags are met (model_family
present? signed?) for the future verify layer — no enforcement here.

`ExecuteOutcome` (frozen) — `status: str` ("accepted" | "rejected_capability" |
"rejected_validation" | "rejected_calibration" | "accepted_acceptance_failed"),
`candidate: Optional[CandidateResult]`, `acceptance: Optional[AcceptanceResult]`,
`capability_check: Optional[CapabilityCheck]`, `validation: ValidationResult`,
`detail: str`. A unit that produces output failing acceptance is still
"produced" — status `accepted_acceptance_failed` (the candidate exists; the
client-side filter rejected it).

## 11. Adapter contract

```python
class Adapter(ABC):
    name: str
    model_family: str
    version: str
    capabilities: Capabilities
    def produce(self, unit: WorkUnit) -> CandidateResult: ...
```

`produce` receives an already-validated `WorkUnit`, renders the portable payload
(via `render_payload`), performs its runtime-native call (MOCK: deterministic
schema walk), and returns a `CandidateResult` stamped with its provenance. The
seam makes NO vendor assumption — Claude Code / OpenAI / ollama / generic are
future subclasses overriding `produce` (+ a real `capabilities`).

MockAdapter schema walk: for each property in `output_schema.properties`, emit a
typed canned value by JSON type (string → a short deterministic echo derived from
the property name + objective; number → 1.0; integer → 1; boolean → true; array →
a single-element list of the item type; object → recurse). `enum`/`minItems`/
range constraints in the property are honored where present so the produced
output passes the fixture acceptance contracts deterministically.

## 12. Test list (wave 2)

1. `test_render.py` — `render_payload` copies exactly the 4-tuple; the rendered
   `prompt` mentions the objective; no other unit field leaks in.
2. `test_capability.py` — `meets_floor`: a node meeting all dimensions qualifies;
   short context_window rejected; missing tool rejected; missing modality
   rejected; each rejection names the failed dimension.
3. `test_mock_adapter.py` — MockAdapter on each fixture produces output that
   (a) matches the fixture `output_schema` (jsonschema validate) and (b) passes
   the fixture `acceptance_contract` via wave-1 `evaluate_acceptance`.
4. `test_calibration.py` — `TrivialCalibrationProbe` passes well-formed
   capabilities, fails negative context_window / unknown modality.
5. `test_execute_flow.py` — `run_work_unit` end-to-end on benign_pilot,
   cause_threaded, structured_acceptance with a qualified MockAdapter →
   status "accepted", acceptance.passed True; an under-capable adapter →
   "rejected_capability"; an invalid unit dict → "rejected_validation"; an
   adapter that emits a deliberately bad output → "accepted_acceptance_failed".
   All green, offline.

## 13. Constraints honored (wave 2)

- Composes on wave-1 real types (`WorkUnit`, `CapabilityFloor`,
  `AcceptanceContract`) + functions (`validate_work_unit`, `evaluate_acceptance`)
  — does NOT fork them.
- **No import from loam**; no loam coupling.
- **No live network calls / no secrets / no SDK imports** this wave — MockAdapter
  is fully offline; live adapters are a follow-on increment.
- No git commit (Ren reviews + commits).
- Every module traces to a PLAN §3.3/§3.4 or research 02 A.2 / research 01 §5.4
  element (this section).

---

# Wave 3 Build Plan — verify / trust layer (Layer A, PLAN §3.5)

Wave 3 builds the **VERIFY / TRUST layer** that sits directly ABOVE the wave-2
execute layer. Wave 2 produces ONE `CandidateResult` per node per attempt; wave 3
**aggregates N CandidateResults (from N nodes, one work unit) into a trust
verdict**, fully offline and testable. This is PLAN §3.5 "defense in depth"
layers L1–L4 + the L3 reputation hook, minus everything that needs the network
or the ledger.

Traceability: every module maps to a named PLAN §3.5 layer / research element.
No speculative code for unnamed cases (ODD-lite). The cross-node primitives are
deliberately the INVERSE of BOINC homogeneity — model diversity is an
anti-collusion feature, not a bug (PLAN §3.5 L1, research 02 B.1).

---

## 14. Scope of this wave

IN (this wave) — the verify layer over N `CandidateResult`s:

1. **Quorum + redundancy aggregation** (`verify/quorum.py`) — collect candidate
   results for one unit; enforce the unit's `RedundancyPolicy`
   (`target_nresults`, `min_quorum`); decide `ACCEPTED` / `NO_QUORUM` /
   `DISPUTED`. (PLAN §3.5 L1.)
2. **Model-diversity enforcement** (inside quorum aggregation) — an agreeing
   cluster must contain **≥2 distinct `model_family` values** to count as a
   valid quorum (the anti-collusion primitive; PLAN §3.5 L1; inverts BOINC).
   The required diversity is read from `RedundancyPolicy.model_diversity` (wave-1
   field; default 2 when the policy leaves it 0 — see §17 owner-note). A cluster
   that reaches `min_quorum` by size but is single-family is rejected →
   `INSUFFICIENT_DIVERSITY`.
3. **Semantic agreement** (`verify/agreement.py`) — an `AgreementFunction`
   interface that CLUSTERS candidate outputs by *semantic* agreement, NOT bit
   equality (heterogeneous LLM outputs never bit-match — research 02 A.0/B.0):
   - **`ObjectiveAgreement`** — exact / normalized-string / predicate match, for
     deterministic outputs (PLAN §3.5 L2 deterministic path).
   - **`SubjectiveAgreement`** — delegates clustering to a pluggable **`Judge`**
     (`verify/judge.py`). Ships a deterministic offline **`MockJudge`** that
     clusters by a normalized canonical form (so the layer is testable with no
     network). Real LLM-as-judge is a documented FOLLOW-ON seam, not built.
4. **Honeypots / gold-standard** (`verify/honeypot.py`) — PLAN §3.5 L4, *the
   single most important mechanism for the insider threat*. A `Honeypot` carries
   a unit's known-expected answer + the `AgreementFunction` to score against it.
   `score_honeypot` scores EACH node's `CandidateResult` against the known answer
   → per-node pass/fail. A node failing a known-answer unit is flagged
   regardless of peer agreement; the result feeds reputation (§5 below).
5. **Reputation hook** (`verify/reputation.py`) — PLAN §3.5 L3, earned never
   self-asserted. A minimal per-node and per-`model_family` reliability
   accumulator. `InMemoryReputation` updated by (a) agreement-with-consensus and
   (b) honeypot outcomes. Interface (`Reputation`) + in-memory impl; persistence
   is the ledger wave.
6. **Disagreement / tiebreak policy** (`verify/tiebreak.py`) — PLAN §3.5 L1 /
   research 01 §1+§3.2 (Gensyn "tiebreak the disputed unit only"). When a unit is
   `DISPUTED` or `NO_QUORUM` *and* escalation is still within
   `target_nresults` headroom, emit a `TiebreakDecision` to escalate ONE more
   node (a returned decision/policy — NOT a live re-dispatch; transport is wave
   4).
7. **A `verify_unit` aggregation entry point** (`verify/aggregate.py`) — wires
   quorum + diversity + agreement + (optional) honeypot + reputation-update +
   tiebreak into one `VerifyVerdict` for a unit. This is the wave's
   outcome-altitude entry point.

DEFERRED to later waves (explicitly NOT built here):

- **Ledger / transport** (PLAN §3.1/§3.6, wave 4) — atomic claim, leases, signed
  content-addressed result blobs, the transparency log. Wave 3 takes
  already-collected `CandidateResult`s as input; it does NOT pull/submit, does
  NOT persist reputation, does NOT sign.
- **Live LLM-as-judge** (network) — only the `Judge` seam + deterministic
  `MockJudge` ship. Real cross-model judge calls are a follow-on increment.
- **Sybil resistance (L5), collusion-resilient SERENE/CoVFeFE backstop (L6),
  prompt-injection adapter defenses (§3.5 B.3), the trusted-core membership
  mechanism (B.4)** — later / owner-decision-gated; wave 3 builds the honeypot +
  diversity primitives that the trusted core seeds, not the core governance.
- **Tier-gating on model diversity** — wave 2 flagged that `Capabilities` has a
  `model_family_tier` but the wave-1 `CapabilityFloor` has no tier field. Wave 3
  needs only `model_family` (present on `CandidateResult`) for diversity; tier is
  NOT required here. Noted as a possible future wave-1 spec MINOR (§17), not
  implemented.

## 15. File layout (wave 3 additions)

```
src/cairn/verify/
  __init__.py        # public surface for the verify layer
  agreement.py       # AgreementFunction, ObjectiveAgreement, SubjectiveAgreement, Cluster
  judge.py           # Judge (ABC), MockJudge (deterministic offline clusterer)
  quorum.py          # QuorumPolicy result: ACCEPTED/NO_QUORUM/DISPUTED + diversity gate
  honeypot.py        # Honeypot, score_honeypot, HoneypotScore
  reputation.py      # Reputation (ABC), InMemoryReputation, ReputationDelta
  tiebreak.py        # TiebreakDecision, decide_tiebreak
  aggregate.py       # verify_unit -> VerifyVerdict (wires everything)
tests/
  test_agreement.py
  test_judge.py
  test_quorum.py
  test_honeypot.py
  test_reputation.py
  test_tiebreak.py
  test_verify_aggregate.py   # outcome-altitude end-to-end
```

## 16. Types (wave 3)

- **`Cluster`** (agreement.py) — `key: str` (the canonical agreement key),
  `members: list[CandidateResult]`, `model_families: set[str]`. The unit of
  "these N results agree."
- **`AgreementFunction`** (ABC) — `cluster(results) -> list[Cluster]`. Partitions
  candidate results into agreement clusters. Two concrete impls:
  - `ObjectiveAgreement(key_fn=None, field=None, normalize=True)` — canonical key
    from a result field (default: the whole `output`), exact/normalized.
  - `SubjectiveAgreement(judge)` — delegates to a `Judge`.
- **`Judge`** (ABC, judge.py) — `agreement_key(result) -> str`. The seam a real
  LLM-as-judge implements (network). `MockJudge(normalize_fn=None)` — deterministic
  offline: lowercases + collapses whitespace + sorts dict keys to a canonical
  JSON string, so semantically-equal-but-not-bit-equal outputs cluster together.
- **`QuorumStatus`** = `ACCEPTED | NO_QUORUM | DISPUTED | INSUFFICIENT_DIVERSITY`.
- **`QuorumResult`** (quorum.py) — `status`, `winning_cluster: Optional[Cluster]`,
  `clusters: list[Cluster]`, `nresults`, `detail`.
- **`HoneypotScore`** (honeypot.py) — `node_id`, `passed: bool`, `detail`.
- **`Honeypot`** — `expected_output`, `agreement: AgreementFunction`; method
  `score(results) -> list[HoneypotScore]`.
- **`ReputationDelta`** — `subject` (node_id or `family:<x>`), `event`
  (`AGREE|DISAGREE|HONEYPOT_PASS|HONEYPOT_FAIL`), `weight`.
- **`Reputation`** (ABC) — `score(subject) -> float`, `apply(delta)`. 
  `InMemoryReputation` — bounded accumulator in `[0.0, 1.0]`, starts at a
  neutral prior (0.5), honeypot-fail penalized harder than a single disagree
  (L4 > L1). New identity ⇒ no entry ⇒ neutral prior (the Sybil reset is the
  ledger wave; the prior is set here).
- **`TiebreakDecision`** (tiebreak.py) — `escalate: bool`, `reason`,
  `extra_nodes: int`, `unit_task_id`.
- **`VerifyVerdict`** (aggregate.py) — the wave's top-level outcome:
  `status: QuorumStatus`, `quorum: QuorumResult`, `honeypot_scores`,
  `reputation_updates: list[ReputationDelta]`, `tiebreak: TiebreakDecision`,
  `accepted_output: Optional[dict]`.

## 17. Owner-decision notes (surfaced, not silently resolved)

1. **`model_diversity` default.** The wave-1 `RedundancyPolicy.model_diversity`
   defaults to `0` (fixtures carry 0). PLAN §3.5 L1 mandates **≥2 distinct model
   families** for a valid quorum. Wave 3 treats `model_diversity <= 1` as "policy
   unset" and applies the **safe default of 2** for diversity enforcement, so the
   anti-collusion primitive is on by default rather than silently disabled. This
   is the F2-honest reading of the design (a single-family consensus must not
   pass). If the owner wants diversity OFF for a specific benign cause, that is an
   explicit `model_diversity = 1` — surfaced for ratification, not assumed.
2. **Future wave-1 MINOR (noted, not built):** if diversity should be
   *tier-aware* (e.g. two distinct families but both tier-0 local-small models
   are weaker than one tier-2), the wave-1 `CapabilityFloor` would need a
   `model_family_tier` floor field. Out of scope for wave 3; logged here.

## 18. Test list (wave 3)

1. `test_agreement.py` — `ObjectiveAgreement` clusters bit-identical and
   normalized-equal outputs together, splits genuinely-different outputs;
   `SubjectiveAgreement` + `MockJudge` clusters semantically-equal-but-not-bit-
   equal outputs into one cluster.
2. `test_judge.py` — `MockJudge.agreement_key` is deterministic, order-insensitive
   over dict keys, whitespace/case-insensitive; distinct meanings ⇒ distinct keys.
3. `test_quorum.py` — quorum REACHED (≥min_quorum, ≥2 families) → ACCEPTED;
   below min_quorum → NO_QUORUM; two competing clusters → DISPUTED;
   single-family cluster that meets size → INSUFFICIENT_DIVERSITY (the
   model-diversity rejection).
4. `test_honeypot.py` — a node whose result matches the known answer passes; a
   node whose result diverges fails — *even when it agrees with a (bad) peer
   majority* (L4 catches collusion that L1 misses).
5. `test_reputation.py` — `InMemoryReputation` rises on AGREE + HONEYPOT_PASS,
   falls on DISAGREE, falls hardest on HONEYPOT_FAIL; per-node and per-family
   subjects tracked independently; bounded to [0,1]; unknown subject ⇒ neutral
   prior.
6. `test_tiebreak.py` — DISPUTED with headroom ⇒ escalate=True, extra_nodes=1;
   ACCEPTED ⇒ escalate=False; DISPUTED with no headroom (already at
   target_nresults ceiling) ⇒ escalate=False with reason.
7. `test_verify_aggregate.py` (**outcome-altitude**) — `verify_unit` invoked with
   N freshly-produced `CandidateResult`s (no pre-arranged verdict state):
   - happy path: 3 results, 2 families agree → VerifyVerdict ACCEPTED,
     accepted_output set, reputation deltas emitted, no tiebreak.
   - single-family agreement → INSUFFICIENT_DIVERSITY, tiebreak escalate=True.
   - honeypot unit with one bad node → that node honeypot-fails + reputation
     penalized.
   All green, offline.

## 19. Anti-collusion honesty (F2 — PLAN §3.5 B.4)

The design CONCEDES that no purely decentralized mechanism fully solves a
colluding-majority adversary. Wave 3 ships the mitigations, not a solution:

- **Covered:** a single model family cannot form a quorum (diversity gate); a
  node that fails gold-standard units is caught regardless of peer agreement
  (honeypot L4) and down-weighted (reputation L3).
- **NOT covered (named gap):** if ≥2 *distinct* model families collude (or share
  a training-data bias — research 02 cites ensembles *amplifying* shared bias,
  arXiv 2502.20758) AND the colluding set never draws a honeypot, the diversity
  gate is satisfied by adversaries and quorum can be captured. The honest
  backstops are the **trusted-core honeypot seeding density** (more honeypots ⇒
  higher capture probability of a colluding set) and the L6 SERENE/CoVFeFE
  research-grade verifier — both later/owner-gated. Wave 3 does not paper over
  this; it builds the honeypot SEAM dense enough that the trusted core can raise
  honeypot frequency for high-stakes causes.

## 20. Constraints honored (wave 3)

- Composes on wave-1/2 real types (`CandidateResult`, `model_family`,
  `RedundancyPolicy`, `AcceptanceContract`, `evaluate_acceptance`) — does NOT
  fork them.
- **No import from loam**; no loam coupling.
- **No live network / no LLM calls / no secrets** — `MockJudge` is fully offline;
  real LLM-as-judge is a follow-on seam.
- No git commit (Ren reviews + commits).
- Every module traces to a PLAN §3.5 layer (L1–L4) / research 01 §1 / research 02
  B.1 element (this section).

---

# Wave 4 Build Plan — LEDGER + TRANSPARENCY layer (Layer A, PLAN §3.1 + §3.6)

Wave 4 builds the **thin coordinator** + the **tamper-evident transparency log**,
fully OFFLINE on the local filesystem (no network — git-style/filesystem only).
This is the only central element of the topology and is deliberately THIN: it
ORDERS claims + STORES blobs; it does NOT decide truth (the wave-3 verify layer
does). Plan-before-code per the build discipline.

Traceability: every wave-4 file maps to a named PLAN §3.1 / §3.6 or REQUIREMENTS
Frame-4 / cause-vetting-governance element. No speculative code (ODD-lite).

## 21. Scope of this wave

IN (this wave):
- **Thin filesystem ledger** (PLAN §3.1) — content-addressed object store +
  `tasks/`, `claims/`, `results/` index dirs. Stores + orders; never decides truth.
- **Content-addressed blob store** (PLAN §3.6) — sha256-keyed immutable blobs;
  round-trippable; same content ⇒ same key (dedup).
- **Atomic exclusive claim** (PLAN §3.1) — the ONE real mutual-exclusion point,
  bought via an atomic `O_EXCL` create (the filesystem analog of a git-ref CAS).
  Double-claim is structurally impossible.
- **Claim leases with expiry** (PLAN §3.1 churn handling) — a claim carries an
  expiry; an expired claim reopens the unit. Time comes from an **injected clock**
  (no wall-clock hardcoding) so lease tests are deterministic.
- **Provenance attestation** (PLAN §3.6) — upgrades wave-2's placeholder
  `signature` into a real `Attestation` record (hash of output + adapter/model_family
  + a SIGNING SEAM with a local HMAC impl). Real keypair mgmt is later.
- **Append-only CT-style transparency log** (PLAN §3.6 + REQUIREMENTS Frame 4 +
  cause-vetting governance) — a hash-CHAINED append-only log; each entry commits to
  the prior entry's hash (tamper-evident). `verify_log()` recomputes the chain and
  DETECTS any retroactive edit/removal/reorder. ONE log, TWO uses (detection
  auditability AND cause-governance no-silent-rejection) — made explicit.
- **Reputation persistence** (PLAN §3.5 L3 persistence hook) — a ledger-backed
  `Reputation` that persists wave-3 deltas as an append log and replays them to
  rebuild scores; keeps the wave-3 `Reputation` interface unchanged.
- **pytest tests** — all green, offline.

OUT (deferred to later waves — explicit non-goals):
- Live-model adapters (Claude Code / OpenAI / ollama) — wave 2 seam stays mock.
- Distribution storefronts / onboarding ramps (PLAN §3.7).
- Cause discovery + cause-vetting GOVERNANCE engine (PLAN §3.9) — this wave ships
  the transparency-LOG mechanism the governance engine will write to, NOT the
  approval/rejection workflow itself.
- The escalation + action engine (PLAN §4).
- Real cryptographic keypair management / A2A signed agent cards — the signing
  SEAM ships with a local HMAC impl; real key management is later.
- libp2p/CRDT topology (PLAN §3.2 runner-up) — wave 4 implements Rec A only.
- Network transport / mirroring / git push-pull — filesystem-local only.

## 22. File layout (wave 4 additions)

```
src/cairn/ledger/
  __init__.py        # public surface: Ledger, BlobStore, ClaimError, lease types,
                     #                 TransparencyLog, verify_log, Attestation,
                     #                 sign_attestation, Clock, LedgerReputation
  clock.py           # Clock protocol + SystemClock + FixedClock (injected time)
  blobstore.py       # content-addressed sha256 blob store (PLAN §3.6)
  claim.py           # atomic O_EXCL exclusive claim + lease/expiry (PLAN §3.1)
  attestation.py     # Attestation record + HMAC signing seam (PLAN §3.6)
  translog.py        # hash-chained append-only CT-style log + verify_log (§3.6)
  reputation_store.py# LedgerReputation — wave-3 Reputation, ledger-persisted (§3.5 L3)
  ledger.py          # Ledger facade wiring tasks/ claims/ results/ over the above
```

Each file maps to a named element:
- `clock.py` ⇒ PLAN §3.1 "claim leases with expiry" (injected clock; no Date.now).
- `blobstore.py` ⇒ PLAN §3.6 "content-addressed task+result blobs".
- `claim.py` ⇒ PLAN §3.1 "Claim — EXCLUSIVE via atomic ref CAS" + lease churn.
- `attestation.py` ⇒ PLAN §3.6 "provenance_requirements attestation per result" +
  research 02 A.2 step 5 "attest + sign".
- `translog.py` ⇒ PLAN §3.6 "append-only transparency log" + REQUIREMENTS Frame 4
  + cause-vetting "tamper-evident, no-silent-rejection".
- `reputation_store.py` ⇒ PLAN §3.5 L3 "persistence belong to the ledger wave".
- `ledger.py` ⇒ PLAN §3.1 thin-coordinator topology (the `tasks/`/`claims/`/`results/`
  repo facade).

## 23. Types + interfaces (wave 4)

- `Clock` (Protocol): `now() -> float` (epoch seconds). `SystemClock` uses
  `time.time()`; `FixedClock(t)` is advanceable (`advance(dt)`) for deterministic
  lease tests. Time is ALWAYS injected — no module calls the wall clock directly
  except `SystemClock`.

- `BlobStore(root)`:
  - `put(data: bytes) -> str` — write content-addressed; key = `sha256(data)` hex;
    idempotent (same content ⇒ same key, write-once).
  - `get(key: str) -> bytes` — read by key; raises `KeyError` if absent.
  - `put_json(obj) -> str` / `get_json(key)` — canonical-JSON (sort_keys) convenience.
  - `has(key) -> bool`.

- `claim.py`:
  - `ClaimError(Exception)` — raised when a unit is already actively claimed.
  - `Claim` (frozen): `task_id, node_id, claimed_at, lease_seconds, claim_id`.
    `expires_at = claimed_at + lease_seconds`; `is_expired(now)`.
  - `ClaimRegistry(root, clock)`:
    - `claim(task_id, node_id, lease_seconds) -> Claim` — atomic `O_EXCL` create of
      `claims/<task_id>`; if the file exists AND its lease is unexpired ⇒ `ClaimError`;
      if it exists but is EXPIRED ⇒ atomically replace (claim reopens). The
      create-exclusive is the mutual-exclusion primitive; double-claim is impossible.
    - `active_claim(task_id) -> Claim | None` — current unexpired claim, else None
      (an expired claim reads as None ⇒ the unit is reopened).
    - `release(task_id, claim_id)` — owner releases early.

- `attestation.py`:
  - `Attestation` (frozen): `task_id, output_hash, adapter_name, model_family,
    adapter_version, produced_at, signature`. `output_hash = sha256(canonical-json
    output)`.
  - `sign_attestation(att_without_sig, *, key: bytes) -> Attestation` — HMAC-SHA256
    over the canonical attestation bytes; SEAM for real keypair signing later.
  - `verify_attestation(att, *, key) -> bool` — recompute + constant-time compare.
  - `attest_candidate(result: CandidateResult, *, key) -> Attestation` — builds the
    real attestation from a wave-2 `CandidateResult`, upgrading its placeholder
    `signature`. Composes on the wave-2 type; does NOT fork it.

- `translog.py` (CT pattern — Merkle/hash-chain):
  - `LogEntry` (frozen): `index, kind, payload (dict), prev_hash, entry_hash,
    recorded_at`. `entry_hash = sha256(index || kind || canonical(payload) ||
    prev_hash || recorded_at)`; genesis `prev_hash = "0"*64`.
  - `TransparencyLog(path, clock)`:
    - `append(kind, payload) -> LogEntry` — append-only; chains to the prior head.
    - `entries() -> list[LogEntry]`, `head_hash() -> str`.
  - `verify_log(path) -> LogVerification` — independent monitor: recompute every
    entry hash + chain link from raw bytes; ANY mismatch (flipped byte, edited
    payload, removed/reordered entry) ⇒ `ok=False` with the failing index. This is
    the LOAD-BEARING tamper-detection guarantee.
  - **Dual-use kinds (made explicit):** `RESULT_RECORDED` / `VERDICT_RECORDED`
    (Frame-4 detection auditability) AND `CAUSE_REQUEST` / `CAUSE_DECISION`
    (cause-governance no-silent-rejection). Same log, same chain, same `verify_log`.

- `reputation_store.py`:
  - `LedgerReputation(Reputation)` — implements the wave-3 `Reputation` ABC
    (`score`, `apply`). Persists each `ReputationDelta` as an append-only JSONL
    record under the ledger; `apply` folds in-memory (reusing the wave-3 bounding
    math) AND appends durably; a fresh instance `replay()`s the log to rebuild
    scores. Same neutral prior, same [0,1] bounds, same event weights as wave 3.

- `ledger.py`:
  - `Ledger(root, clock, *, signing_key)` — the thin facade. Wires `BlobStore`
    (`objects/`), `ClaimRegistry` (`claims/`), `tasks/` + `results/` index dirs,
    `TransparencyLog` (`translog.jsonl`), `LedgerReputation`. Methods:
    `define_task(unit_dict) -> task_id` (content-address the unit, index under
    `tasks/`); `claim_task(task_id, node_id, lease_seconds)`; `store_result(
    candidate, *, attest=True) -> result_key` (blob + attestation + log a
    `RESULT_RECORDED` entry); `record_verdict(verdict)` (log a `VERDICT_RECORDED`
    entry). Truth-deciding stays in wave-3 `verify_unit`; the ledger only records.

## 24. Tamper-evidence approach (the load-bearing guarantee)

CT-style hash-chained Merkle log. Each entry's `entry_hash` commits to the prior
`prev_hash`, so the head hash transitively commits to the ENTIRE history. A
monitor re-derives every hash from the raw on-disk bytes with NO trust in the
stored hashes: a flipped byte in any payload changes that entry's recomputed
hash, breaking its own self-hash AND every subsequent link; a removed or
reordered entry breaks the `prev_hash` chain. `verify_log()` returns the first
failing index. The guarantee is "tampering is DETECTABLE by an independent
monitor," not "tampering is prevented" — matching REQUIREMENTS' "demonstrate
they're lying" standard (§cause-vetting). The transparency property is only real
because the monitor catches tampering — test 4 below is the load-bearing test.

## 25. Test list (wave 4)

`tests/test_ledger_blobstore.py`
1. content-addressed round-trip: `put(data)` then `get(key)` returns the same
   bytes; same content ⇒ same key (dedup); `put_json/get_json` round-trip.

`tests/test_ledger_claim.py`
2. atomic claim rejects double-claim: first `claim` succeeds; a second concurrent
   `claim` of the same task (unexpired) raises `ClaimError`.
3. **lease expiry reopens a unit** (injected `FixedClock`): claim with a short
   lease; before expiry `active_claim` is the claim and re-claim raises; advance
   the clock past expiry ⇒ `active_claim` is None AND a new node can claim.

`tests/test_ledger_translog.py`
4. **tamper DETECTION (load-bearing):** append several entries, `verify_log` ⇒ ok;
   flip ONE byte in the on-disk log ⇒ `verify_log` ⇒ NOT ok, with the failing
   index; also test a REMOVED entry and a REORDERED entry both fail.
   Plus: append + independent verify of an untampered log ⇒ ok; dual-use entry
   kinds (a CAUSE_DECISION and a RESULT_RECORDED in one chain) both verify.

`tests/test_ledger_attestation.py`
5. `attest_candidate` builds a real attestation over a wave-2 `CandidateResult`;
   `verify_attestation` passes for an untampered attestation and FAILS when the
   output hash is altered (signing seam works).

`tests/test_ledger_reputation_store.py`
6. `LedgerReputation` persists deltas and a fresh instance `replay()`s to the same
   scores; matches the wave-3 `InMemoryReputation` math on the same delta sequence.

`tests/test_ledger_e2e.py` (**outcome-altitude**)
7. end-to-end on the ledger, no pre-arranged state: `define_task(unit)` →
   `claim_task` → run wave-2 `run_work_unit` with a `MockAdapter` (×N) →
   `store_result` each (blob + attestation + RESULT_RECORDED log entry) → wave-3
   `verify_unit` over the candidates → `record_verdict` → `verify_log` ⇒ ok, and
   the log contains the result + verdict entries. All offline.

## 26. F2 — named limitations (PLAN §3.1 / §3.6 honesty)

- **Thin ledger = liveness-only SPOF (conceded, mirrorable).** The ledger is the
  one central element; if the forge is down, NEW claims/appends stall. This is a
  LIVENESS SPOF only, NOT an integrity one: integrity rests on the hash chain +
  content-addressing, which any mirror can independently verify. PLAN §3.1 already
  concedes this and calls for mirroring; wave 4 keeps the store a plain directory
  precisely so it is trivially mirrorable (copy = mirror). Mirroring/replication
  transport is deferred (network is out of scope this wave).
- **Tamper-evidence DETECTS, does not PREVENT.** A forge operator with write
  access can still rewrite the log; the guarantee is that an independent monitor
  holding any prior head hash will DETECT the divergence (split-view). Gossip of
  head hashes between monitors (full CT split-view detection) is deferred — wave 4
  ships single-monitor `verify_log`; cross-monitor gossip is a later increment.
- **HMAC signing is a symmetric SEAM, not real PKI.** `sign_attestation` uses a
  local HMAC key — it proves integrity to a holder of the key, not third-party
  non-repudiation. Real asymmetric keypairs / A2A signed agent cards are later;
  the function signature is the stable seam.

## 27. Owner-decision notes (surfaced, not silently resolved)

No wave-4 decision blocks the build — all are method (builder's call) or already
ruled in PLAN/REQUIREMENTS. Surfaced for visibility:
- The liveness-SPOF + mirroring posture is taken straight from PLAN §3.1; no new
  decision needed.
- Asymmetric-vs-symmetric signing is a deferred decision (real keypair mgmt is a
  named later wave) — wave 4 ships the seam so the choice stays open.

## 28. Constraints honored (wave 4)

- Composes on wave-1/2/3 real types (`WorkUnit`, `CandidateResult`, `verify_unit`,
  `VerifyVerdict`, `Reputation`/`ReputationDelta`) — does NOT fork them.
- **No import from loam**; no loam coupling.
- **No network / no secrets** — filesystem-local; HMAC key is a test-supplied
  parameter, never a checked-in secret.
- **Injected clock** everywhere lease time matters — no wall-clock hardcoding;
  lease tests are deterministic via `FixedClock`.
- Python stdlib only (`hashlib`, `hmac`, `os`, `json`, `time`) — no heavy deps.
- No git commit (Ren reviews + commits).
- Every module traces to a PLAN §3.1 / §3.6 or REQUIREMENTS Frame-4 / cause-vetting
  element (this section + §22).

---

# Wave 5 Build Plan — runnable system: benign pilot cause + end-to-end runner + CLI

Wave 5 makes the wave-1..4 BACKBONE **runnable + inspectable as a system**. It
adds NO new trust/ledger primitive — it WIRES the real backbone end-to-end over a
concrete, benign, deterministic pilot cause, exposes it through a thin `cairn`
CLI, and proves the whole chain (claim → execute → store → verify → record →
independently re-verify the log) runs offline and green.

Traceability: every wave-5 file maps to a named element below (ODD-lite). No
speculative code for unnamed cases.

## 29. Scope of this wave

IN (this wave):
- A **benign pilot cause** — a concrete, NON-SENSITIVE distributed-analysis task
  expressed as real wave-1 work units with machine-checkable acceptance
  contracts: **open-source-license classification** over a handful of bundled
  public-domain-style text snippets (license blurbs). For each snippet a node
  must emit `{is_open_license: bool, license_id: string}`. Deterministically
  checkable; benign; uses the real work-unit schema + acceptance predicates.
- A **deterministic pilot adapter** (`PilotNodeAdapter`) that computes the
  CORRECT answer from the unit's `inputs` via a small offline rule table — so
  honeypot scoring is meaningful (a gold answer to match) and N nodes of DISTINCT
  `model_family` AGREE on the right answer (diversity quorum satisfiable). A
  `wrong=True` mode emits a deliberately wrong-but-schema-valid answer (the bad
  node the honeypot catches). This is a NEW `Adapter` subclass — it does NOT fork
  or modify `MockAdapter` (compose-don't-reimplement; MockAdapter stays the
  schema-echo reference, untouched).
- The **end-to-end runner** `run_pilot(...)` — drives the REAL backbone:
  `Ledger.define_task` each unit → `claim_task` per node → `run_work_unit`
  (PilotNodeAdapter, distinct families) → `store_result` → `verify_unit` (with a
  `Honeypot` on the seeded unit) → `record_verdict` → everything on the real
  `TransparencyLog`. Returns a structured `PilotRunSummary`.
- A **thin CLI** (`cairn` console entry, `src/cairn/cli.py`): `cairn pilot`,
  `cairn verify-log PATH`, `cairn inspect LEDGER`. Library-only logic; the CLI
  parses args, calls the library, prints.
- pytest tests: e2e on a fresh ledger reaching ACCEPTED with diversity met; the
  honeypot catches the bad node; `verify-log` passes on the produced log and
  fails (nonzero) on a tampered copy; CLI commands exit 0 + emit expected output;
  one OUTCOME-ALTITUDE test invoking the real CLI / `run_pilot` with no
  pre-arranged state. All green, offline.

OUT (deferred — explicit):
- Live-model adapters (real network model calls). PilotNodeAdapter is the
  sanctioned deterministic offline stand-in; the only model stand-in remains the
  Adapter seam.
- Distribution storefronts / packaging-for-distribution.
- Cause-discovery / cause-vetting GOVERNANCE workflow (the LOG kinds exist from
  wave 4; the approval engine does not).
- The escalation / action engine.
- Network transport / mirroring (filesystem-local only).

## 30. File layout (wave 5 additions)

```
src/cairn/
  pilot/
    __init__.py        # exports: PILOT_CAUSE_ID, build_pilot_units, PilotNodeAdapter,
                       #          Honeypot wiring, run_pilot, PilotRunSummary
    cause.py           # the benign cause: snippet fixtures -> wave-1 work-unit dicts
                       #   + the per-unit gold answers + the honeypot unit id
    adapter.py         # PilotNodeAdapter (deterministic correct/wrong answers; §29)
    runner.py          # run_pilot(...) -> PilotRunSummary (drives the real backbone)
  fixtures/
    pilot_license_snippets.json   # bundled benign input snippets (no network)
  cli.py               # thin `cairn` CLI: pilot / verify-log / inspect
tests/
  test_pilot_cause.py      # units validate; gold answers pass their own acceptance
  test_pilot_runner.py     # run_pilot e2e: ACCEPTED + diversity; honeypot catches bad node
  test_cli.py              # CLI exit 0 + output; verify-log OK + tamper-fails; OUTCOME-ALTITUDE
```

`pyproject.toml`: add `[project.scripts] cairn = "cairn.cli:main"` and
force-include `pilot_license_snippets.json` (mirrors the existing fixture
force-includes so `importlib.resources` finds it in a built wheel).

## 31. The pilot cause (cause.py)

- `PILOT_CAUSE_ID = "pilot.oss-license-classification"`.
- Snippets bundled as `fixtures/pilot_license_snippets.json`: a list of
  `{snippet_id, dataset_title, license_text, source_url, expected_is_open,
  expected_license_id}`. ~4 benign entries (MIT / Apache-2.0 / a proprietary
  "all rights reserved" negative / GPL-3.0). Public-domain-style blurbs, no
  network, no PII.
- `build_pilot_units(snippets)` → one wave-1 work-unit dict per snippet, reusing
  the EXACT shape of `fixtures/benign_pilot.json` (schema_version 1.0.0,
  output_schema `{is_open_license, license_id}`, the same acceptance predicates),
  with `redundancy_policy = {target_nresults: 2, min_quorum: 2, model_diversity:
  2}` so the diversity gate is explicitly ON and satisfiable by 2 distinct
  families. `task_id = f"{PILOT_CAUSE_ID}::{snippet_id}"`.
- `gold_answer(snippet)` → the correct `{is_open_license, license_id}` output for
  a snippet (drawn from its `expected_*` fields). Used both to build the
  `Honeypot` for the seeded unit AND to verify (in tests) that the gold answer
  passes the unit's own acceptance contract (units are well-formed).
- `HONEYPOT_SNIPPET_ID` — names which unit is the gold-standard seed whose
  `Honeypot` scores every node against `gold_answer`.

## 32. The pilot adapter (adapter.py)

`PilotNodeAdapter(Adapter)` — deterministic, offline, NO network/model:
- `__init__(model_family, *, wrong=False, capabilities=None)` — distinct
  `model_family` per node so the diversity quorum is satisfiable; `wrong=True`
  flips the answer (the bad node).
- `name = model_family` (per-node identity for honeypot `node_id` / reputation).
- `capabilities` defaults to a tier meeting the pilot floor (`context_window
  4096`, `modalities ["text"]`).
- `produce(unit)` → reads `unit.inputs["inline"]["license_text"]`, applies the
  same deterministic rule the gold answer uses (a small keyword table:
  MIT/Apache/GPL/BSD → open + id; "all rights reserved"/"proprietary" → not
  open), returns a `CandidateResult` shaped to the output_schema. `wrong=True`
  inverts `is_open_license` and blanks/garbles `license_id` so it (a) still
  validates the output_schema types but (b) DIVERGES from the gold standard →
  caught by the honeypot, and may fail consensus. Provenance fields stamped
  (deterministic `produced_at` placeholder; `model_family` set).
- Compose-don't-reimplement: subclasses the real `Adapter`, reuses
  `CandidateResult` + `render_payload`; does NOT touch `MockAdapter`.

## 33. The end-to-end runner (runner.py)

`run_pilot(ledger, *, node_families, bad_family=None) -> PilotRunSummary`:
1. `units = build_pilot_units(load bundled snippets)`.
2. For each unit: `ledger.define_task(unit)`.
3. For each unit, simulate N nodes (one `PilotNodeAdapter` per family in
   `node_families`; if `bad_family` is in the set AND the unit is the honeypot
   unit, that node runs `wrong=True`): `ledger.claim_task` (distinct node_id per
   node; second+ nodes use short leases / the claim is per-node-id so we model
   N independent claimers — see note) → `run_work_unit(unit, adapter)` → collect
   `outcome.candidate` (re-stamped with the node_id as `adapter_name`).
4. `ledger.store_result(cand)` for every candidate (blob + attestation +
   RESULT_RECORDED).
5. `verify_unit(candidates, policy, honeypot=<Honeypot for the honeypot unit>,
   reputation=ledger.reputation, unit_task_id=task_id)` per unit.
6. `ledger.record_verdict(task_id, verdict)`.
7. Build `PilotRunSummary`: per-unit `{task_id, status, accepted,
   model_families_in_quorum, honeypot_catches:[node_id...]}`, reputation deltas
   summary (subject → final score for known subjects), total honeypot catches,
   and `log_head = ledger.translog.head_hash()`.

Claim note: the wave-4 claim registry is EXCLUSIVE per task_id — one holder at a
time. The pilot models N nodes each independently EXECUTING the same unit
(redundancy is the POINT of the verify layer), which is the realistic shape:
nodes claim, execute, the claim expires/releases, the next claims. To keep the
runner deterministic and offline we `claim_task` then `release` (or advance the
injected clock past a short lease) between nodes so each node legitimately holds
the exclusive claim while it executes — exercising the REAL atomic-claim +
lease-expiry path rather than bypassing it. The runner takes the `Ledger`
(carrying its injected `Clock`) so time is controllable.

`PilotRunSummary` is a frozen dataclass with a `to_dict()` for CLI JSON printing
and a `pretty()` for the human summary.

## 34. The CLI (cli.py)

Thin argparse (stdlib — no new dep). `main(argv=None) -> int`:
- `cairn pilot [--ledger DIR] [--json]` — fresh `Ledger` (temp dir if `--ledger`
  omitted) with a `SystemClock` (or `FixedClock` for determinism — use
  `FixedClock` so output is reproducible), run `run_pilot`, print the summary +
  the transparency-log head. Exit 0 on a clean run.
- `cairn verify-log PATH` — call `verify_log(PATH)`; on `ok` print `OK length=<n>
  head=<hash>` and exit 0; else print the first failing index + reason and exit
  1.
- `cairn inspect LEDGER` — count tasks / claims / results / verdict-log entries
  under a ledger dir and print them; exit 0.
- No business logic in the CLI — it parses args + calls library functions +
  prints + maps to an exit code.

## 35. Test list (wave 5)

- `test_pilot_cause.py`:
  - every pilot unit validates against the wave-1 schema (`validate_work_unit`).
  - each unit's `gold_answer` passes that unit's OWN acceptance contract
    (`evaluate_acceptance`) — the cause is well-formed.
  - `PilotNodeAdapter` (honest) produces the gold answer for each unit;
    `wrong=True` produces a schema-valid but gold-divergent answer.
- `test_pilot_runner.py` (OUTCOME-ALTITUDE candidate):
  - `run_pilot` on a FRESH ledger with ≥2 distinct honest families → every unit
    `accepted` with `model_families_in_quorum ≥ 2` (diversity satisfied).
  - with a `bad_family` honest-elsewhere but `wrong` on the honeypot unit → that
    node appears in the honeypot unit's `honeypot_catches`; total catches ≥ 1.
  - the produced `translog.jsonl` passes `verify_log`; RESULT_RECORDED count ==
    total stored candidates; VERDICT_RECORDED count == #units.
- `test_cli.py`:
  - OUTCOME-ALTITUDE: `subprocess`-invoke the real `cairn` entry (`python -m
    cairn.cli pilot --ledger <tmp>` or the installed console script) with NO
    pre-arranged state → exit 0, output contains the head hash + an ACCEPTED line.
  - `cairn verify-log <produced log>` exits 0 + prints `OK`; a tampered copy
    exits nonzero + names a failing index.
  - `cairn inspect <ledger>` exits 0 + prints task/result/verdict counts.

## 36. Owner-decision notes (surfaced, not silently resolved)

- **Pilot cause choice = OSS-license classification** (method, builder's call):
  benign, deterministic, machine-checkable, reuses the exact `benign_pilot.json`
  output shape already in the repo. No sensitive-mission content. If the owner
  wants a different benign cause the cause.py table swaps without touching the
  runner/CLI. — Not blocking; surfaced for visibility.
- **Per-node claim modeling** (method): the runner claim→release→claim per node
  to exercise the REAL exclusive-claim path while modeling N redundant executors.
  Alternative (give each node its own task_id) would NOT exercise redundancy on
  one unit, which is the verify layer's whole point — rejected. — Not blocking.

## 37. Constraints honored (wave 5)

- WIRES the real wave-1..4 backbone (`Ledger`, `run_work_unit`, `MockAdapter`
  seam, `verify_unit`, `Honeypot`, `TransparencyLog`/`verify_log`) — does NOT
  reimplement or fork any of it; the ledger/verify are the REAL ones (no mocks);
  `PilotNodeAdapter` is the only stand-in and only stands in for the model call,
  via the sanctioned `Adapter` seam.
- **No import from loam**; no loam coupling. NOT loam.
- **No network / no secrets** — bundled fixtures, filesystem-local ledger, HMAC
  key is a runner/CLI-supplied parameter (a fixed non-secret test key), never a
  checked-in production secret.
- **Injected clock** — the runner takes the `Ledger`'s `Clock`; lease/claim time
  is controllable; CLI uses `FixedClock` for reproducible output.
- Python stdlib only (`argparse`, `json`, `tempfile`, `subprocess` in tests) —
  no new runtime dep.
- No git commit (Ren reviews + commits).
- Every wave-5 module traces to an element in §30–§34.

---

# Wave 6 Build Plan — first LIVE Claude adapter (real model in the loop)

Wave 6 ships the FIRST live-model adapter: a concrete `Adapter` that does a real
Cairn work unit by calling a real Claude model via the subscription `claude -p`
CLI (owner-approved, TG 13097). Proven ONLY on the benign OSS-license pilot — no
forums, no real people, no sensitive inputs. Everything offline stays
deterministic; exactly ONE real live smoke runs at the end.

Traceability: composes on the wave-2 `Adapter` seam (§adapter.py) + `render_payload`
(§render.py) + `CandidateResult` (§result.py), and the wave-5 pilot
(`build_pilot_units`, `PilotNodeAdapter`, `run_pilot`). Adds NO new spec, NO new
trust primitive — one new adapter subclass + a live-smoke path + tests.

## 38. Scope of this wave

IN:
- `ClaudeCliAdapter` (`src/cairn/execute/claude_adapter.py`): an `Adapter`
  subclass that renders the portable payload, builds a JSON-only prompt, calls
  `claude -p` through an ISOLATED subprocess, parses JSON from the response
  (tolerant of code fences / surrounding prose), and returns a `CandidateResult`
  with `model_family="claude"` + real provenance. Fail-closed on bad output /
  nonzero exit / timeout.
- A thin internal isolated `claude -p` wrapper (`_claude_print`) carrying the
  spawn-isolation flags; INJECTABLE so the offline suite never calls real claude.
- A live-smoke path: `cairn live-smoke` CLI subcommand + a `live_smoke()` library
  function that runs the benign pilot's units with a live `ClaudeCliAdapter` node
  while keeping the REAL verify / ledger / translog.
- Offline tests (mocked subprocess) + ONE real live smoke after the suite is green.

OUT (deferred — explicit):
- Other live adapters (OpenAI / ollama / generic-OpenAI-compatible).
- Distribution storefronts, cause-discovery / vetting governance, the
  escalation / action engine, network transport.
- Real cryptographic signing (still the ledger-wave placeholder).
- A real adversarial calibration probe of the live adapter's capabilities.

## 39. Spawn-isolation approach (TOP safety constraint)

The single non-negotiable: a `claude -p` spawn MUST NOT load the parent's
plugins — specifically the Telegram MCP plugin, which an un-isolated spawn loads
and SIGTERM-steals the single bot slot, dropping the owner's live Telegram
channel (PROVEN root cause 2026-05-29; `feedback_spawned_claude_must_isolate_
telegram_plugin`). Cairn is standalone — it does NOT import loam's
`claude_print_client`; it writes its OWN minimal isolated wrapper with the SAME
discipline.

Isolation is baked into the argv the adapter builds:
- `--strict-mcp-config` — "only use MCP servers from --mcp-config, ignoring all
  other MCP configurations" (verified `claude --help`). With...
- `--mcp-config <empty.json>` — a temp file containing `{"mcpServers": {}}` (an
  empty-servers object). Strict + empty ⇒ NO MCP servers / plugins load.
- `-p / --print` (one-shot, exit) + `--output-format json` (so we can read the
  real model id from the result envelope for provenance) + `--model sonnet`
  (default tier; cheap; no API key — subscription machinery).

The live PreToolUse guard (`~/.claude/hooks/claude_spawn_isolation_guard.py`)
only inspects Bash commands at command position; it does NOT see a `claude`
launched by a Python `subprocess`. So for the subprocess path the defense is the
isolation baked into the adapter code (exactly as the guard's own docstring
notes for the litrpg ClaudePrintClient). A REGRESSION TEST asserts the built argv
contains `--strict-mcp-config` AND the empty-`--mcp-config` form — the durable
guarantee that the isolation flags are present by construction.

## 40. Subprocess seam (testability)

`ClaudeCliAdapter.__init__(..., transcript_fn=None)`. `transcript_fn` is a
`Callable[[str], str]` (prompt -> raw model text). When `None`, the adapter uses
the real `_claude_print` (isolated spawn). Offline tests inject a fake
`transcript_fn` returning canned transcripts (well-formed JSON, fenced JSON, junk,
or raising to model a nonzero-exit/timeout) so the suite is deterministic and
never spawns real claude. The real `_claude_print(prompt) -> str`:
- writes the empty mcp-config to a temp file,
- builds the isolated argv (§39),
- `subprocess.run(argv, input=prompt, capture_output=True, text=True,
  timeout=...)`,
- on nonzero exit / `TimeoutExpired` / empty stdout → raises `ClaudeCliError`
  (the adapter catches it and fails closed),
- on success parses the `--output-format json` envelope to extract the result
  text + the model id (best-effort; falls back to raw stdout).

`_build_claude_argv(...)` is a pure helper returning the argv list — the unit the
regression test inspects.

## 41. Prompt strategy

The adapter builds a prompt from `render_payload(unit)`:
- the neutral `payload.prompt` (objective + inputs + output schema), PLUS
- a strict instruction: "Return ONLY a single JSON object conforming to the
  schema. No prose, no markdown fences, no explanation." (We still parse
  tolerantly in case the model adds fences/prose anyway — fail-open on parsing,
  fail-closed on acceptance.)

JSON extraction (`_extract_json`): try `json.loads` on the whole string; else
strip a ```json ... ``` or ``` ... ``` fence; else find the first `{` ... matching
last `}` and parse that. On every-strategy failure → return a sentinel empty
`{}` output, which the acceptance contract rejects (fail-closed) — never raise.

## 42. Live-smoke path

`live_smoke(ledger, *, transcript_fn=None, families=...) -> PilotRunSummary`:
runs the benign pilot units over the REAL ledger / verify / translog, with one
node driven by `ClaudeCliAdapter` (the live model) and (to satisfy the diversity
quorum of 2) one Mock-ish honest node of a DISTINCT family (`PilotNodeAdapter`
family `"reference"`). We do NOT fake a second Claude identity — the second node
is a genuinely-distinct deterministic reference family, and we document that a
real second model family is the production path. `transcript_fn` defaults to the
real isolated spawn; tests inject a fake.

NOTE surfaced: the pilot unit's `model_diversity=2` quorum needs ≥2 DISTINCT
families. The live smoke supplies `claude` (live) + `reference` (deterministic) so
the quorum is satisfiable; a single real family alone would NOT meet diversity.
This is documented, not faked.

CLI: `cairn live-smoke [--ledger DIR] [--json] [--timeout S]` runs `live_smoke`
with the REAL spawn and prints the summary. It is the ONLY path that touches real
claude; `cairn pilot` stays fully offline/deterministic.

## 43. Test list (offline, mocked subprocess — all green BEFORE the live smoke)

`test_claude_adapter.py`:
- parses a well-formed bare-JSON transcript → `CandidateResult` with the parsed
  output + `model_family="claude"`.
- tolerates a ```json fenced transcript → same parsed output.
- tolerates surrounding prose around a JSON object → parsed output.
- FAIL-CLOSED: a junk (non-JSON) transcript → empty `{}` output that FAILS the
  pilot acceptance contract (no crash).
- FAIL-CLOSED: `transcript_fn` raising `ClaudeCliError` (models nonzero exit /
  timeout) → empty output, no crash.
- ISOLATION REGRESSION: `_build_claude_argv(...)` output CONTAINS
  `--strict-mcp-config` AND `--mcp-config` pointing at a written empty-servers
  config (assert the file content is `{"mcpServers": {}}`).
- provenance: `produced_at` comes from an injected clock (deterministic), not the
  wall clock.

`test_live_smoke.py`:
- OFFLINE pilot via `live_smoke(..., transcript_fn=<fake returning correct JSON>)`
  reaches ACCEPTED on all units over the REAL ledger / verify / translog; the
  produced translog passes `verify_log`; quorum families include `claude`.

## 44. One real live smoke (after offline green)

Run `cairn live-smoke` (or `live_smoke` directly) ONCE against the REAL isolated
`claude -p`. Report the real model output + whether it flowed through
verify/ledger/translog. If the isolation guard blocks OR there is ANY doubt the
spawn is isolated → STOP and surface for Ren to run; do not force it. Capture the
result or blocker in the final message.

## 45. Constraints honored (wave 6)

- Composes on the real `Adapter` seam + `render_payload` + `CandidateResult` +
  the wave-5 pilot/verify/ledger — reimplements none of it.
- NOT loam — no loam import; Cairn's own minimal isolated wrapper.
- Spawn isolation by construction + an argv-contains-isolation-flags regression
  test.
- Fail-closed on bad model output / nonzero exit / timeout (acceptance rejects;
  never crashes / waves through).
- Offline suite deterministic (subprocess mocked); exactly ONE real spawn (the
  live smoke).
- Benign inputs only; no secrets; no API key (subscription `claude -p`).
- No git commit (Ren reviews + commits).
