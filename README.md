# cairn — a cause-coordination engine built to be distributed (Layer A)

> *Cuiridh mi clach air do chàrn.*
> — "I'll put a stone on your cairn." A Scottish Gaelic blessing; it means *I'll not forget you.*
>
> A cairn is built one stone at a time, by many hands — to mark the safe way, to
> warn of the danger ahead, and to honor those who came before. Add your stone.

## What is cairn?

**cairn is a platform for coordinating vetted, transparent causes at a scale and
consistency people can't sustain alone — AI pointed at work that's genuinely
worth doing, with humans deciding what's worth doing and signing off before
anything acts.**

Most of what's said about AI right now is that it extracts: it takes from
creators, burns resources, and concentrates the gains. cairn is built to be the
opposite. It's a use of AI a person could actually rally behind. Many volunteers
lend their own AI to *collectively notice harm* and route human-verified findings
to the institutions that can act. The AI does the patient, tireless watching and
cross-checking that no group of humans could keep up by hand; people decide
what's worth watching, and a human signs off before anything leaves the system.

Technically, cairn is a **model-agnostic detection-and-analysis engine that runs
many causes on one protocol.** The mission of the **platform** is distinct from
the mission of any **cause** it runs: cairn itself is **mission-neutral** — the
coordination engine, not an opinion about any one target. Each cause defines the
conduct it watches for as its own configuration, and the engine hard-codes none
of it. That is deliberate: the platform earns trust by being a fair, auditable
mechanism, and the causes that run on it are chosen and vetted by people. (This
is also why it's named `cairn` — a general, multi-cause engine, not a name tied
to any one mission.)

**What it's being built to become** is a decentralized, distributed network —
many hands, one protocol. **Where it is today** is a single-operator, offline
pilot; the distributed, multi-volunteer deployment is among the pieces not yet
built (see "Maturity & honest boundaries" for exactly what is and isn't).

## Maturity & honest boundaries

cairn is something to rally behind *because* it's being built carefully and in
the open, not because it's finished. The engine is complete and runnable today;
its safety story rests on a single human sign-off gate whose "human" is currently
an unauthenticated free-text string, and the real-world network pieces are not
built yet. The limits and the deferred work below are **owned design boundaries,
not discovered defects.**

**Status.** Pre-1.0 (`0.x`), unreleased: no version is tagged or published yet,
the CHANGELOG sits at `[Unreleased]`, and while `0.x` minor versions may break.
**License:** MIT. **Python:** 3.11+. Standard-library-first — the only runtime
dependency is `jsonschema`.

**What genuinely works today.** The full Layer-A engine is built and exercised
by a broad passing test suite (`pytest -q` reports the current count) — a working
engine, not a skeleton. `cairn pilot` runs the benign pilot end-to-end on a fresh
ledger, and the append-only transparency log it writes independently verifies
(`cairn verify-log`). The shipped cause is an OSS-license-classification pilot: a
mission-neutral exercise of the full detect → verify → human-vet → route path
with no sensitive logic.

**What the human gate does — and does NOT — guarantee.** A fail-closed human
sign-off gate stands before any cause becomes listable and before any finding
becomes routable. The gate is real, but be precise about its limits today:

- **The "human" is unauthenticated free-text.** `reviewer_id`, `granted_by`,
  `created_by`, `decider`, and `node_id` are caller-supplied strings with **no
  authentication anywhere in the engine**. A recorded "human verdict" proves *a
  string was present with a reason* — not that a real, independent, or qualified
  human acted.
- **There is one gate, and no enforced separation of duties.** Nothing in the
  code prevents the same actor from requesting a cause, "reviewing" it under a
  second name, and dispatching an action. The five-frame gate-check enforces
  that all five frames were *addressed*, not that an independent human addressed
  them substantively.
- **The audit log proves integrity, not truth.** The append-only hash-chained
  transparency log (`cairn verify-log`) proves no entry was edited, removed, or
  reordered. It does **not** prove a finding was correct, a reviewer was real, or
  a target was actually engaged in the conduct — a wrongful action is recorded as
  faithfully as a correct one. The log also has **no external anchoring** yet: an
  operator who holds the file could in principle rewrite the whole chain from
  genesis, and the rewrite would be undetectable to anyone holding only that
  operator's copy.
- **The attestation seam is HMAC (symmetric).** It proves "someone holding the
  key signed," which for a single operator is "the operator signed its own work"
  — integrity to a key-holder, **not** third-party non-repudiation.
- **The engine is mission-neutral and general — so its misuse surface is real.**
  The conduct a cause targets is free-text the requester fills in; the engine
  hard-codes no limit on what conduct or whom a cause may target. The only barrier
  today is the (unauthenticated, single-actor-capable) human cause-vetter, so the
  engine is general enough to be pointed at a real person. The current shipped
  scope — the benign OSS-license-classification pilot — exercises none of that
  surface, but the general engine's misuse surface is named here on purpose.

**Deferred, not hidden.** These are deliberately deferred to separate,
independently-reviewed phases, not abandoned — listed so an outside reviewer sees
them as already on the radar, not as discoveries. The first four are the gate
limits above, named with their threat-model invariant refs:

- **Authenticated identity + separation of duties** (THREAT-MODEL INV-Z5) — no
  asymmetric signing yet.
- **Target-protection / misuse-against-a-legitimate-party** (THREAT-MODEL INV-Z6)
  — no code-level mechanism keeps the gates from being driven against an innocent
  party; only the human vetter stands in the way.
- **External transparency-log anchoring** (THREAT-MODEL INV-U3) — no published
  head hashes / third-party witness.
- **Asymmetric (non-repudiable) attestation** — replaces the symmetric HMAC seam.
- **Multi-operator / compromised-operator trust** — the trust model assumes one
  honest operator; recruiting multiple operators is exactly the assumption this
  does not yet cover.
- **Abuse-response: retraction, appeal, and incident recovery** — there is no
  path to reverse or retract a dispatched action, no appeal for a wrongly-targeted
  party, and no key-rotation / log-recovery playbook.
- **Anti-abuse at intake (rate-limiting / coordination-detection)** —
  THREAT-MODEL INV-A3 is a placeholder; nothing yet prevents coordinated mass-flagging.

The real-world *implementation seams* (live capture, external delivery, served
API, reputation gating) are deferred too and itemized under "Deliberately
deferred" below. See [docs/THREAT-MODEL.md](docs/THREAT-MODEL.md) for the full
invariant register (including the explicit `[PLACEHOLDER]` invariants). An
**acceptable-cause / prohibited-target policy** — what conduct may be targeted
and what targets are categorically off-limits — is a **governance decision the
owner has not yet made**; see [GOVERNANCE.md](GOVERNANCE.md) for the flagged-open
stub.

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
- **Routing / action spine** — turns a human-signed-off ROUTABLE finding into a
  RECORDED ACTION dispatched to the best-fit recipient by locality + domain tags,
  with fail-closed escalation so a routable finding is never silently dropped, and
  records it on the same transparency log. ("Human-signed-off" means a recorded
  human verdict — see the gate-guarantee note above for what that does and does
  not assure.) Ships only an offline `InMemoryRecipientChannel`.
  `src/cairn/routing/`.

## Deliberately deferred (implementation seams)

The seams exist; their real-world implementations are intentionally not built
here (these are the implementation counterparts to the trust/security gaps under
"Maturity & honest boundaries"):

- **Real capture** — a headless-browser / IP-masked capture port (today:
  offline local-fixture port only).
- **Real recipient delivery** — network egress to external recipients (Safe
  Browsing / abuse.ch / registrars / partner endpoints); today the
  `RecipientChannel` seam ships only an in-memory channel.
- **Served read API** — an HTTP/HTML rendering of the public-transparency
  surfaces (today: library-level views only).
- **Reputation-aware gating** — the reputation subsystem earns, persists, and
  surfaces per-node / per-model-family reliability scores, but no gating
  decision consumes them yet: quorum, tiebreak, and claim do not read
  `.score()`. Letting reputation weight acceptance / tiebreak / eligibility is a
  security-sensitive change (it adds a gameable surface). Today reputation is an
  observability signal, not a control input.
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

## Setup & test

Python 3.11+, standard-library-first (the only runtime dependency is
`jsonschema`):

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
acc = evaluate_acceptance({"is_open_license": True, "license_id": "MIT"}, contract)
assert acc.passed
```

The top-level `cairn` package also re-exports the execute / adapter seam
(`run_work_unit`, `MockAdapter`, …), the verify / trust layer (`verify_unit`,
`decide_quorum`, …), and the read-only public-transparency surfaces
(`PublicTransparency`, `list_published_causes`, …). See `src/cairn/__init__.py`
for the full exported surface and [docs/QUICKSTART.md](docs/QUICKSTART.md) for
the CLI.
