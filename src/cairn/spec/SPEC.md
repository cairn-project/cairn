# Work-Unit + Acceptance-Contract SPEC (v1)

The single load-bearing **stable interface** of the distributed
cause-coordination engine. It is the interface between Layer A (the engine) and
Layer B (a cause): a cause is "just another work unit" expressed in this spec.

The canonical machine-readable artifact is
[`work_unit.schema.json`](./work_unit.schema.json) (JSON Schema, Draft 2020-12).
This document is the human-readable companion. On any disagreement, **the JSON
Schema is authoritative**.

## Design property — the portable payload

The wire carries **declarative intent + contract, never a binary or a
vendor-tuned prompt**. The portable payload is:

```
objective + inputs + output_schema + acceptance_contract
```

Everything model-specific (prompt template, system prompt, tool wiring) is
synthesized **locally by an adapter** for its runtime. That synthesis — the
adapter layer — is a **later phase** and is NOT in this spec. This spec defines
only the unit and how to validate it.

## Fields

| Field | Required | Type | Meaning |
|---|---|---|---|
| `schema_version` | yes | semver string | Spec version this unit was authored against. See **Versioning** below. |
| `task_id` | yes | string | Stable unique id; ties a result back to its unit; dedup / sybil anchor. |
| `cause_id` | yes | string | First-class cause binding. Which coordinated effort this serves. |
| `objective` | yes | string | Natural-language task outcome. Model-agnostic. |
| `inputs` | yes | object | The data to operate on. **Exactly one** of: `{inline: <data>}` OR `{pointer: <ref>, hash: <hash>}` (content-addressed). |
| `output_schema` | yes | object | A JSON Schema describing the required result structure. The runtime-agnostic result contract. |
| `acceptance_contract` | yes | object | `{predicates: [...]}` — machine-checkable predicates a valid result must satisfy. |
| `capability_floor` | yes | object | Minimum capability the unit needs: `context_window` (int tokens), `tools` (string[]), `modalities` (string[]). |
| `redundancy_policy` | yes | object | `target_nresults` (int ≥1), `min_quorum` (int ≥1), `model_diversity` (int ≥0, distinct model families). Consumed by the deferred verify layer. |
| `provenance_requirements` | yes | object | Per-result attestation flags: `model_family`, `signed_result`, `trace` (all bool). Feeds the deferred audit ledger. |
| `deadline` | no | ISO-8601 date-time | Optional absolute deadline. |
| `lease` | no | object | `{duration_seconds: int ≥1}` — claim lease; reclaim-and-reissue on expiry. Claim logic is a later phase. |

### `inputs` — inline xor content-addressed

`inputs` is a JSON-Schema `oneOf`: a unit carries **either** inline data
**or** a content-addressed pointer + hash, never both and never neither.
Content-addressing is how large or shared inputs are referenced without
inlining them; pointer resolution (git/IPFS) is a later phase — the spec only
carries the reference + integrity hash.

### `capability_floor` — the capability tier

A model-agnostic unit can only *require* capabilities the weakest enrolled
runtime has. The unit is **model-agnostic within a capability tier, not
uniformly**. `capability_floor` makes the tier explicit so a
weak runtime that can't meet the floor is routed away rather than silently
poisoning the result pool. Self-declared capability is itself an untrusted claim
— the join-time calibration probe that validates it is a later phase.

## Acceptance contract — predicate kinds

`acceptance_contract.predicates` is a **conjunctive** list: ALL predicates must
pass for the contract to pass. Each predicate is a **pure, machine-checkable
function over a result dict** — no LLM, no network. These are the cheap
client-side filter; the semantic / quorum verify layer
(deferred) sits **above** them.

`field` paths are **dotted** (e.g. `vendor.url`) and resolve into the result.
A numeric path segment indexes into an array (e.g. `citations.0` is the first
citation). Any miss — absent key or out-of-range index — is treated as the
field being absent.

| `kind` | Params | Passes when |
|---|---|---|
| `required_fields` | `fields: [path,...]` | every listed path is present in the result |
| `field_type` | `field`, `json_type` (`string`/`number`/`integer`/`boolean`/`array`/`object`/`null`) | the value at `field` is of `json_type` |
| `value_range` | `field`, `min?`, `max?` | the numeric value at `field` is within `[min, max]` (whichever bounds are given) |
| `enum` | `field`, `allowed: [...]` | the value at `field` is one of `allowed` |
| `non_empty` | `field` | the string/array/object/number at `field` is present and non-empty (refusal-handling: a refusal → empty/absent → fails) |
| `min_items` | `field`, `count` | the array at `field` has ≥ `count` items (citations-required: `citations` ≥ 1) |
| `regex_match` | `field`, `pattern` | the string at `field` fully/partially matches the regex (format check) |

An **unknown** `kind` is a hard error — `evaluate_acceptance` fails closed,
never silently passes.

These predicate kinds cover exactly what the validator
must check: format, required fields, value ranges, citations-required, and
refusal-handling.

## Versioning rule

`schema_version` is **semver**:

- **MAJOR** — a breaking field change (removed/renamed required field, changed
  type). Consumers MUST upgrade. `validate_work_unit` accepts a unit only when
  its `schema_version` MAJOR equals the spec's MAJOR.
- **MINOR** — an additive **optional** field. Older consumers keep working.
- **PATCH** — a documentation or constraint clarification with no field change.

This is the "open, versioned spec" property: anyone can write an
adapter for any future runtime against a pinned MAJOR, and the spec can evolve
additively without breaking deployed adapters.

The current spec version is **1.0.0** (`$id` `.../v1.json`).

## What this spec deliberately does NOT define (deferred)

- the **adapter layer** (how `objective`+`inputs`+`output_schema` is rendered
  into a runtime-native call) — a later phase;
- the **verify layer** that consumes `redundancy_policy` /
  `provenance_requirements` (quorum, model-diversity, LLM-judge, honeypots) —
  a later phase;
- the **ledger / claim** semantics that consume `task_id` / `lease` /
  `deadline` (atomic claim, leases, transparency log) — a later phase.

The spec carries the *fields* those layers need; their *behavior* is deferred to
later phases.
