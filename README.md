# cairn — distributed cause-coordination engine (Layer A)

> *Cuiridh mi clach air do chàrn.*
> — "I'll put a stone on your cairn." A Scottish Gaelic blessing; it means *I'll not forget you.*
>
> A cairn is built one stone at a time, by many hands — to mark the safe way, to
> warn of the danger ahead, and to honor those who came before. Add your stone.

> **Placeholder name.** `cairn` is a working placeholder. The real,
> mission-neutral project name is an **open owner decision** (PLAN.md decision
> #9 — the engine is general and multi-cause, not mission-specific, so the name
> must not be mission-specific). Renaming touches only the package path and
> import root.

cairn is the reusable Layer-A engine from the distributed cause-coordination
design (`../PLAN.md`, `../REQUIREMENTS.md`): a decentralized, model-agnostic
distributed-detection-and-analysis force-multiplier that runs N causes on one
protocol. Volunteers lend their own AI to collectively notice harm and route it
to the institutions that can act. It is **mission-neutral** — the protocol runs
many causes; the conduct a cause targets is a per-cause property, not baked into
the engine. It is **not** built into loam and does not depend on it.

## Maturity — read this first

- **Pre-1.0 (`0.x`), unreleased.** No version is tagged or published yet; the
  CHANGELOG sits at `[Unreleased]`. While `0.x`, minor versions may break.
- **Complete and runnable, pilot-stage.** The full Layer-A engine is built and
  exercised by **276 passing tests**. `cairn pilot` runs the benign pilot
  end-to-end on a fresh ledger, and the append-only transparency log it writes
  independently verifies (`cairn verify-log`). This is a working engine, not a
  skeleton.
- **The shipped pilot cause is deliberately benign.** The runnable cause is an
  OSS-license-classification pilot — a mission-neutral exercise of the full
  detect → verify → human-vet → route path with no sensitive logic. Real-world
  capture (headless browser / network egress) and real external-recipient
  delivery are **deliberately deferred, separately-security-reviewed later
  waves**; today's capture and delivery seams ship only offline, deterministic,
  in-memory implementations.
- **License:** MIT. **Python:** 3.11+. Standard-library-first — the only runtime
  dependency is `jsonschema`.

## What's in this repo

The engine composes a single end-to-end loop —
**spec → execute → verify → ledger/transparency → cause → contribute → capture →
vet → publish → route** — every layer built and tested (see the `[Unreleased]`
section of [CHANGELOG.md](CHANGELOG.md) for the authoritative per-layer detail):

- **Spec** — a versioned JSON-Schema **work-unit + acceptance-contract** (the
  runtime-agnostic interface defining a unit of AI work and its machine-checkable
  acceptance). `src/cairn/spec/`, `validate.py`, `acceptance.py`.
- **Execute / adapter layer** — a model-agnostic adapter seam with a
  deterministic mock adapter and a live `claude -p` adapter (spawn-isolated by
  construction). `src/cairn/execute/`.
- **Verify layer** — redundancy + model-diversity quorum, semantic agreement
  (not bit-equality), honeypot/gold-standard scoring, reputation, and a tiebreak
  policy. `src/cairn/verify/`.
- **Ledger + transparency** — a content-addressed blob store, atomic exclusive
  claim with leases, an HMAC attestation seam, and an append-only hash-chained,
  Certificate-Transparency-style log with independent `verify_log` verification.
  `src/cairn/ledger/`.
- **Cause layer** — a mission-neutral first-class `Cause` object (id, status,
  five-frame self-assessment, target-conduct + protected-boundary,
  partner-of-record posture), gated request intake and a *reasoned* decision
  (approval OR rejection-with-reason — no silent rejection), and a gated public
  `list_causes` (approved/live only). `src/cairn/cause/`, `src/cairn/vetting/`.
- **Contributor opt-in + cause-bound execution** — an explicit, gated, revocable
  contributor opt-in (opt-in to a non-listable cause is refused) and a
  cause-scoped run loop driving a cause's units through execute → verify →
  ledger/transparency. `src/cairn/contribute/`.
- **Inert capture abstraction** — the seam by which a trust-gated CAPTURE
  operator freezes a live target into a STATIC, INERT, content-addressed
  examination packet that the open analysis layer judges *without* re-visiting
  the live target. Ships only an offline `StaticDocumentCapturePort` (a local
  fixture; no browser, no URL fetched, no network egress). `src/cairn/capture/`.
- **Human-in-the-loop two-gate vetting** — two distinct fail-closed review gates
  (cause-vetter and finding-vetter); nothing advances without a recorded human
  decision. `src/cairn/vetting/`.
- **Public transparency surfaces** — redacted-by-construction read-only views of
  causes, vetted outcomes, and the hash-chain skeleton, plus public log
  verification reusing `verify_log` verbatim. `src/cairn/public/`.
- **Routing / action spine** — turns a human-verified ROUTABLE finding into a
  RECORDED ACTION dispatched to the best-fit recipient (locality + domain tags,
  with fail-closed escalation so a routable finding is never silently dropped),
  recorded on the same transparency log. Ships only an offline
  `InMemoryRecipientChannel`. `src/cairn/routing/`.

## Deliberately deferred (later, separately-reviewed waves)

The seams exist; their real-world implementations are intentionally not built
here:

- **Real capture** — a headless-browser / IP-masked capture port (today:
  offline local-fixture port only).
- **Real recipient delivery** — network egress to external recipients (Safe
  Browsing / abuse.ch / registrars / partner endpoints); today the
  `RecipientChannel` seam ships only an in-memory channel.
- **Served read API** — an HTTP/HTML rendering of the public-transparency
  surfaces (today: library-level views only).
- **CI/release automation** — see [RELEASING.md](RELEASING.md) (proposed) and
  [CONTRIBUTING.md](CONTRIBUTING.md).

## Get started

- **Run it / install it:** [docs/QUICKSTART.md](docs/QUICKSTART.md) — clone →
  `pip install -e .` → `cairn pilot` → request/approve a cause → `cairn
  contribute` → `cairn public verify-log`.
- **Contribute:** [CONTRIBUTING.md](CONTRIBUTING.md), the
  [Code of Conduct](CODE_OF_CONDUCT.md), and [GOVERNANCE.md](GOVERNANCE.md).
- **Understand the security posture:** [docs/THREAT-MODEL.md](docs/THREAT-MODEL.md)
  and [SECURITY.md](SECURITY.md).
- **Propose a cause:** open a
  [cause request](.github/ISSUE_TEMPLATE/cause_request.md); an approved cause is
  recorded on-ledger and decided through the five-frame gate.

## Requirements

Python 3.11+. Standard-library-first; the only runtime dependency is
`jsonschema`.

## Setup & test

```sh
python3.13 -m venv .venv          # any python >= 3.11
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```

## Public API

```python
from cairn import validate_work_unit, evaluate_acceptance, load_fixture

unit = load_fixture("benign_pilot")
result = validate_work_unit(unit)
assert result.valid

contract = unit["acceptance_contract"]
acc = evaluate_acceptance({"answer": "...", "citations": ["..."]}, contract)
assert acc.passed
```

The top-level `cairn` package also re-exports the execute / adapter seam
(`run_work_unit`, `MockAdapter`, …), the verify / trust layer (`verify_unit`,
`decide_quorum`, …), and the read-only public-transparency surfaces
(`PublicTransparency`, `list_published_causes`, …). See `src/cairn/__init__.py`
for the full exported surface and [docs/QUICKSTART.md](docs/QUICKSTART.md) for
the CLI.
