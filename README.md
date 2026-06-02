# cairn — distributed cause-coordination engine (Layer A)

> *Cuiridh mi clach air do chàrn.*
> — "I'll put a stone on your cairn." A Scottish Gaelic blessing; it means *I'll not forget you.*
>
> A cairn is built one stone at a time, by many hands — to mark the safe way, to
> warn of the danger ahead, and to honor those who came before. Add your stone.

> **Name.** `cairn` is the project's **final, owner-ratified name** — chosen to
> be mission-neutral because the engine is general and multi-cause, not
> mission-specific. (This closes what was formerly tracked as PLAN.md open
> decision #9; the name is no longer open.)

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

## What the human gate does — and does NOT — guarantee (read this too)

The engine's safety story rests on a **human sign-off gate** before any cause
becomes listable and before any finding becomes routable. That gate is real and
fail-closed — but be precise about what it does today, because we would rather
you read this than discover it:

- **The "human" is unauthenticated free-text.** `reviewer_id`, `granted_by`,
  `created_by`, `decider`, and `node_id` are caller-supplied strings with **no
  authentication anywhere in the engine**. A recorded "human verdict" proves *a
  string was present with a reason* — not that a real, independent, or qualified
  human acted. Identity-authentication is a **deliberately deferred wave**.
- **There is one gate, and no enforced separation of duties.** Nothing in the
  code prevents the same actor from requesting a cause, "reviewing" it under a
  second name, and dispatching an action. The five-frame gate-check enforces
  that all five frames were *addressed*, not that an independent human addressed
  them substantively.
- **The audit log proves integrity, not truth.** The append-only hash-chained
  transparency log (`cairn verify-log`) proves no entry was edited, removed, or
  reordered. It does **not** prove a finding was correct, a reviewer was real, or
  a target was actually engaged in the conduct. A wrongful action is recorded as
  faithfully as a correct one. The log has **no external anchoring** yet, so an
  operator who holds the file could in principle rewrite the whole chain from
  genesis undetectably to anyone holding only that operator's copy.
- **The attestation seam is HMAC (symmetric).** It proves "someone holding the
  key signed," which for a single operator is "the operator signed its own work"
  — integrity to a key-holder, **not** third-party non-repudiation. Asymmetric
  signing is a deferred wave.
- **The engine is mission-neutral and general.** The conduct a cause targets is
  free-text the requester fills; the engine hard-codes no limit on what conduct
  or whom a cause may target. The only barrier today is the (unauthenticated,
  single-actor-capable) human cause-vetter. The engine is therefore general
  enough to be pointed at a real person — **the current shipped scope is the
  benign OSS-license-classification pilot, which exercises none of that surface,
  but the general engine's misuse surface is real and is named here on purpose.**

These are **owned design boundaries, not discovered defects.** See
[docs/THREAT-MODEL.md](docs/THREAT-MODEL.md) for the full invariant register
(including the explicit `[PLACEHOLDER]` invariants), and "Known, deferred gaps"
below.

## Known, deferred gaps (named, not hidden)

These are known to the maintainer and **deliberately deferred to later,
separately-reviewed waves** — listed so an outside reviewer sees them as already
on the radar rather than as discoveries:

- **Authenticated identity + separation of duties** — every actor is currently
  unauthenticated free-text (THREAT-MODEL INV-Z5). No asymmetric signing yet.
- **Target-protection / misuse-against-a-legitimate-party** — there is no
  code-level mechanism preventing the gates from being driven against an
  innocent party (THREAT-MODEL INV-Z6); only the human vetter stands in the way.
- **External transparency-log anchoring** — no published head hashes / third-party
  witness, so a single operator's rewrite is undetectable to anyone holding only
  that operator's copy (THREAT-MODEL INV-U3).
- **Multi-operator / compromised-operator trust** — the trust model assumes one
  honest operator; recruiting multiple operators is exactly the assumption this
  does not yet cover.
- **Abuse-response: retraction, appeal, and incident recovery** — there is no
  path to reverse or retract a dispatched action, no appeal for a wrongly-targeted
  party, and no key-rotation / log-recovery playbook.
- **Anti-abuse at intake (rate-limiting / coordination-detection)** —
  THREAT-MODEL INV-A3 is a placeholder; nothing yet prevents coordinated mass-flagging.

An **acceptable-cause / prohibited-target policy** — what conduct may be
targeted and what targets are categorically off-limits — is a **governance
decision the owner has not yet made**; see [GOVERNANCE.md](GOVERNANCE.md) for the
flagged-open stub.

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
- **Routing / action spine** — turns a human-signed-off ROUTABLE finding (a
  recorded human verdict — see the gate-guarantee note above for what that does
  and does not assure) into a RECORDED ACTION dispatched to the best-fit recipient
  (locality + domain tags,
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
