# cairn — distributed cause-coordination engine (Layer A)

> *Cuiridh mi clach air do chàrn.*
> — "I'll put a stone on your cairn." A Scottish Gaelic blessing; it means *I'll not forget you.*
>
> A cairn is built one stone at a time, by many hands — to mark the safe way, to
> warn of the danger ahead, and to honor those who came before. Add your stone.

> **Placeholder name.** `cairn` is a working placeholder. The real,
> mission-neutral project name is an **open owner decision** (PLAN.md decision
> #9 — the engine is general and multi-cause, not suicide-specific, so the name
> must not be mission-specific). Renaming touches only the package path and
> import root.

This is the reusable Layer-A engine from the distributed cause-coordination
design (`../PLAN.md`, `../REQUIREMENTS.md`): a decentralized, model-agnostic
distributed-detection-and-analysis force-multiplier that runs N causes on one
protocol. It is **not** built into loam and does not depend on it.

## What's in this repo right now (wave 1 — foundation only)

Wave 1 builds the single load-bearing **stable interface** the whole engine
hangs off: the **work-unit + acceptance-contract spec** (PLAN §3.3, the A↔B
interface). Per the design, "the interface between A and B is the work-unit +
acceptance-contract spec" — so it is built first, before anything that consumes
it.

- `src/cairn/spec/work_unit.schema.json` — the canonical **versioned JSON
  Schema** for a work unit.
- `src/cairn/spec/SPEC.md` — human-readable field-by-field spec + the
  versioning rule.
- `src/cairn/types.py` — pydantic-free dataclasses for the work unit and
  acceptance predicates.
- `src/cairn/validate.py` — `validate_work_unit(unit)`.
- `src/cairn/acceptance.py` — `evaluate_acceptance(result, contract)` and
  the machine-checkable predicate kinds.
- `src/cairn/fixtures/` — 3 example work units.
- `tests/` — schema-validation, acceptance-evaluation, and fixture-parse tests.

## What is explicitly DEFERRED to later waves

This wave ships **only the spec + validation**. It does **not** build:

- the **verify layer** (k-redundancy quorum, model-diversity, LLM-judge,
  honeypots) — PLAN §3.5, phase P1;
- the **execute / adapter runtime** (Claude Code / OpenAI / ollama adapters,
  capability calibration) — PLAN §3.3/§3.4, phase P1;
- the **ledger** (thin git-ledger coordinator, atomic claim, leases,
  transparency log) — PLAN §3.1/§3.6, phase P2;
- distribution storefronts, cause-discovery/vetting, partner sourcing, and the
  escalation/action engine — PLAN §3.7–§3.9, §4, §7, phases P3–P6.

The spec ships the *fields* those layers will consume (`redundancy_policy`,
`provenance_requirements`, `capability_floor`, `task_id`/`deadline`/`lease`),
but none of their logic. See `BUILD-PLAN.md` for the full deferral list.

## Requirements

Python 3.11+. Standard-library-first; the only runtime dependency is
`jsonschema`.

## Setup & test

```sh
python3.13 -m venv .venv          # any python >= 3.11
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```

## Public API (wave 1)

```python
from cairn import validate_work_unit, evaluate_acceptance, load_fixture

unit = load_fixture("benign_pilot")
result = validate_work_unit(unit)
assert result.valid

contract = unit["acceptance_contract"]
acc = evaluate_acceptance({"answer": "...", "citations": ["..."]}, contract)
assert acc.passed
```
