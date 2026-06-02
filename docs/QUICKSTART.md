# cairn — Quickstart

`cairn` is the reusable Layer-A engine from the distributed
cause-coordination design: a decentralized, model-agnostic
distributed-detection-and-analysis force-multiplier that runs N causes on
one protocol. It is standard-library-first; the only runtime dependency is
`jsonschema`. (`cairn` is the project's final, owner-ratified name.)

This guide covers installing the project, a minimal usage example, and
running the tests. For the field-by-field work-unit spec see
`src/cairn/spec/SPEC.md`; for the full scope and deferral list see the
`BUILD-PLAN*.md` files and `README.md`.

## Requirements

- Python 3.11 or newer.

## Install

From the repository root, create a virtual environment and install the
package in editable mode with its dev extras (pytest):

```sh
python3.13 -m venv .venv          # any python >= 3.11
.venv/bin/pip install -e ".[dev]"
```

This installs the `cairn` package plus the `cairn` console command (defined
in `pyproject.toml` under `[project.scripts]`).

## Minimal usage — the library

The public API is re-exported from the top-level `cairn` package. The core
loop is: load a work unit, validate it against the versioned schema, then
evaluate a candidate result against that unit's acceptance contract.

```python
from cairn import validate_work_unit, evaluate_acceptance, load_fixture

unit = load_fixture("benign_pilot")     # one of the shipped example work units
result = validate_work_unit(unit)
assert result.valid

contract = unit["acceptance_contract"]
acc = evaluate_acceptance({"answer": "...", "citations": ["..."]}, contract)
assert acc.passed
```

`list_fixtures()` enumerates the available example work units. The package
also exports the execute / adapter seam (`run_work_unit`, `MockAdapter`,
`render_payload`, …), the verify / trust layer (`verify_unit`,
`decide_quorum`, …), and the read-only public-transparency surfaces
(`PublicTransparency`, `list_published_causes`, …); see
`src/cairn/__init__.py` for the full exported surface.

## Minimal usage — the CLI

The installed `cairn` command is a thin surface over the library. The
commands are offline and stdlib-only, except `live-smoke` (which spawns a
real model). Run an end-to-end benign pilot on a fresh ledger:

```sh
.venv/bin/cairn pilot                 # runs the pilot, prints a run summary
.venv/bin/cairn pilot --json          # same, as a JSON summary
```

`cairn pilot` writes a ledger to a temp directory (or `--ledger DIR`) and
prints the ledger path. You can then inspect or independently re-verify it:

```sh
.venv/bin/cairn inspect <LEDGER_DIR>              # count tasks/claims/results/verdicts
.venv/bin/cairn verify-log <LEDGER_DIR>/translog.jsonl   # re-verify the transparency log
```

Run `.venv/bin/cairn --help` (and `--help` on any subcommand) for the full
command set, which also includes the cause-layer commands (`causes`,
`cause-request`, `cause-decide`, `contribute`) and the read-only `public`
surfaces (`public causes`, `public outcomes`, `public verify-log`,
`public log`).

> `cairn live-smoke` is the only command that touches a real model — it runs
> the pilot with one node driven by a real Claude via an isolated
> `claude -p` subprocess. Every other command stays fully offline.

## Run the tests

The project uses pytest, configured in `pyproject.toml` (`testpaths =
["tests"]`, `pythonpath = ["src"]`). From the repository root:

```sh
.venv/bin/pytest
```

To run a single test module:

```sh
.venv/bin/pytest tests/test_acceptance.py
```
