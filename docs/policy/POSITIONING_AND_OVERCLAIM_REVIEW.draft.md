# Positioning Reconcile + Overclaim Sweep — DRAFT (proposed edits for owner review)

> **STATUS: DRAFT — proposed edits for owner review. NOT applied.**
>
> This document covers Bucket-B items **B3 (residual overclaim sweep)** and **B4
> (positioning-copy reconcile)**. Every change below is a **proposal surfaced for
> the maintainer's review** — none has been silently applied to the live docs.
> The maintainer decides which to accept; the accepted ones then land as a
> separate ordinary edit.
>
> **Grounding (information-trust ordering):** every proposed softening is grounded
> in **what the engine actually does today**, verified against the assessment of
> `src/` and the running CLI — *not* in the marketing copy. The engine is genuine
> and runs; the sweep is narrow and surgical, not a teardown.

---

## The one consistent overclaim (the headline finding)

The public docs lead with **"decentralized … distributed … force-multiplier"**
and **"volunteers lend their own AI … many hands."** This describes the
**architecture**, which is real — but a stranger reads it as the **running
reality**, which today is a **single-machine, offline, single-operator pilot**:

- The two network-touching seams — real capture and real recipient delivery —
  ship **offline-only by deliberate design** (`StaticDocumentCapturePort` is a
  local fixture; `InMemoryRecipientChannel` is an in-memory sink with no egress).
- There is **no multi-operator deployment** today; the trust model explicitly
  assumes **one honest operator** (README "Known, deferred gaps"; THREAT-MODEL).
- "Volunteers lend their own AI … many hands" describes the *intended* shape; no
  distributed volunteer network is running.

So "distributed / decentralized / many volunteers" is **true in architecture,
not yet true in operation.** The README's own maturity + gate-guarantee blocks
already say this honestly *lower down* — but the **top-of-doc taglines and the
metadata files (CITATION.cff, pyproject, CONTRIBUTING, QUICKSTART) don't carry
the same honesty**, so the *first* thing a reader sees overclaims relative to
what they can run. **This is a consistency problem, not a lie** — the fix is to
make the lead-line match the maturity block, everywhere.

> **F2 — the honest disagreement:** the prior assessment said the overclaim sweep
> was "largely done." That's true for *court-grade* / *human-verified* (those are
> well-qualified — see §C, no change needed). It is **not** true for the
> *distributed / volunteers* framing, which still leads every public surface
> without the "architecture-not-yet-operation" qualifier. That's the residual
> overclaim, and it's the most reviewer-visible one.

---

## A. README — proposed softenings

### A1. Title (README.md:1)
- **Now:** `# cairn — distributed cause-coordination engine (Layer A)`
- **Proposed:** `# cairn — a cause-coordination engine (Layer A)`
  *(or keep "distributed" but the body must immediately qualify it — see A3)*
- **Why:** "distributed" in the title is the first claim a reader meets; the
  engine runs single-machine/offline today. Recommendation: drop "distributed"
  from the *title* and let the body explain the distributed *architecture* with
  the maturity qualifier attached.

### A2. Lead description (README.md:45–49)
- **Now:** "cairn is a **decentralized, model-agnostic
  distributed-detection-and-analysis force-multiplier** that runs N causes on one
  protocol. Volunteers lend their own AI to collectively notice harm and route it
  to the institutions that can act."
- **Proposed:** "cairn is a **model-agnostic cause-coordination engine** that runs
  N causes on one protocol. Its architecture is decentralized and
  distribution-ready — *designed* for many volunteers to lend their own AI to
  collectively notice harm and route it to the institutions that can act —
  **though today it runs as a single-operator, offline pilot** (see Maturity)."
- **Why:** keeps the real architectural claim, adds the operational-reality
  qualifier inline so the lead and the maturity block agree. "force-multiplier"
  is marketing-flavoured; "engine" is what the code is.

### A3. Tagline (README.md:11–15, the bolded "What is cairn?")
- **Now:** "**cairn is a platform for coordinating vetted, transparent causes at
  a scale and consistency people can't sustain alone …**"
- **Proposed:** mostly fine (it's aspirational-but-framed). Suggest adding a
  short clause: "… at a scale and consistency people can't sustain alone
  **(the engine that does this is built and runnable today; the live, multi-
  volunteer deployment is a deliberately deferred phase)**."
- **Why:** the existing honest-boundary block (README:33–40) already does this
  work; A3 just pulls the qualifier up next to the boldest claim. *Optional —
  lower priority than A1/A2.*

---

## B. Metadata files — proposed softenings (these are the ones reviewers diff)

### B1. CITATION.cff (lines 5–6)
- **Now:** "A decentralized, model-agnostic, distributed detection-and-analysis
  engine: volunteers lend their own AI to collectively notice harm …"
- **Proposed:** "A model-agnostic cause-coordination engine with a
  distribution-ready architecture: *designed for* volunteers to lend their own AI
  to collectively notice harm … (single-operator offline pilot today)."
- **Why:** CITATION.cff is what an academic reviewer cites verbatim; it must not
  overstate operational reality.

### B2. pyproject.toml (line 9, `description`)
- **Now:** "Distributed cause-coordination engine (Layer A) — a mission-neutral,
  model-agnostic distributed detection-and-analysis engine …"
- **Proposed:** "Cause-coordination engine (Layer A) — a mission-neutral,
  model-agnostic detection-and-analysis engine with cross-model verification,
  human-in-the-loop vetting, and a tamper-evident transparency log (single-
  operator offline pilot; distribution-ready architecture)."
- **Why:** the PyPI/package description is the most-copied one-liner; remove the
  doubled "distributed."

### B3. CONTRIBUTING.md (lines 3–4)
- **Now:** "Cairn is a decentralized, model-agnostic
  distributed-detection-and-analysis force-multiplier …"
- **Proposed:** "Cairn is a model-agnostic cause-coordination engine (distribution-
  ready architecture; single-operator offline pilot today) …"
- **Why:** same softening, same reason; keeps the contributor framing honest.

### B4. QUICKSTART.md (lines 3–4)
- **Now:** "`cairn` is a decentralized, model-agnostic
  distributed-detection-and-analysis force-multiplier that runs N causes on one
  protocol."
- **Proposed:** "`cairn` is a model-agnostic cause-coordination engine that runs N
  causes on one protocol. It runs as a **single-operator, offline pilot today**;
  the distributed, multi-volunteer deployment is a deliberately deferred phase."
- **Why:** the assessment specifically called for a one-line expectation-set up
  front in QUICKSTART (this overlaps Bucket-A item A6 — flagged so they don't
  collide; whichever lands first should carry this sentence).

---

## C. Already-honest — verified, NO change proposed (the F2 "don't fake a finding")

To avoid manufacturing work, these were checked and are **already well-qualified**
— proposing edits here would be false-positive overclaim-hunting:

- **"court-grade auditable"** — appears only as a *named, explicitly-aspirational
  safety-frame key* and is qualified wherever it's user-facing. CONTRIBUTING and
  the gate-guarantee block both name it aspirational. **No change.**
- **"human-verified" / "human sign-off gate"** — the README's "What the human gate
  does — and does NOT — guarantee" block (README:70–109) is unusually honest
  (names the unauthenticated-free-text limit, the no-separation-of-duties limit,
  integrity-not-truth). **No change — this is a strength, leave it.**
- **"tamper-evident transparency log"** — accurate; the log *is* hash-chained and
  independently verifiable. The README correctly says it proves *integrity, not
  truth* and names the no-external-anchoring limit. **No change.**
- **"mission-neutral"** — accurate and load-bearing; matches the engine. **No
  change.** (The acceptable-use DRAFT governs the *human* layer that
  mission-neutrality leaves open — see `ACCEPTABLE_USE.draft.md`.)

---

## D. Positioning reconcile (B4) — the consistency map

After the softenings above, the public surfaces should all carry the **same**
positioning. The single canonical line to standardise on (proposed):

> **"A mission-neutral, model-agnostic cause-coordination engine with a
> distribution-ready architecture. Built and runnable today as a single-operator,
> offline pilot; the live multi-volunteer, networked deployment is a deliberately
> deferred, independently-reviewed phase."**

Surfaces that should echo it (consistently): README title + lead, CITATION.cff
abstract, pyproject description, CONTRIBUTING opener, QUICKSTART opener.

> **[OWNER DECISION D.1 — the repo-URL reconcile, blocked on the org name]**
> Every metadata file points to `github.com/lukeivers/cairn`, but the stated
> public target is `github.com/cairn-project/cairn`. This is the single most
> reviewer-visible inconsistency. **It is blocked on the owner's
> `lukeivers` vs `cairn-project` org decision** (that decision + the mechanical
> sweep are tracked as the Bucket-A/C URL items, *not* done here). Flagged so the
> positioning reconcile is known to be incomplete until the org name lands.

> **[OWNER DECISION D.2 — mission framing: neutral vs pointed]**
> The positioning copy is deliberately **mission-neutral** today ("the engine is
> general; causes are chosen by people"). The outreach research drafted a
> **pointed** alternative (lead with the online-harms mission) side by side. This
> is a strategic call the owner must make: **keep neutral now / go pointed / go
> neutral-now-revisit-pointed-after-counsel.** *Recommendation from the research:
> neutral now, revisit pointed after the acceptable-use policy (B1) is ratified
> and counsel is engaged — leading pointed before the policy + counsel exist
> invites exactly the scrutiny the project isn't yet ready for.*

---

## THE DECISIONS THE OWNER MUST MAKE (summary)

1. **Approve / reject each proposed softening** in §A and §B (A1, A2, A3, B1–B4).
   *Recommendation: accept A1, A2, B1, B2, B3, B4; A3 optional.* These are the
   residual-overclaim fixes; accepting them makes the lead-line match the
   already-honest maturity block.
2. **Confirm §C "no change" calls** — court-grade / human-verified / tamper-evident
   / mission-neutral are already honest; agree to leave them, or name one you
   want touched.
3. **[D.1]** Repo-org name (`lukeivers` vs `cairn-project`) — blocks the URL
   reconcile across all metadata. (This is the cross-bucket blocker; the sweep
   itself is mechanical once the name is picked.)
4. **[D.2]** Mission framing: neutral now / pointed now / neutral-now-revisit-
   pointed-after-counsel. *Recommended: the third.*

---

## How to apply (once ratified)

These are **proposals, not applied edits.** When the owner approves a subset, the
accepted softenings land as a single ordinary `docs:`/`chore:` commit on a normal
branch — they are doc-only and carry no test impact. The URL reconcile (D.1)
waits on the org-name decision and is a separate mechanical sweep.

---

## Change log

- *DRAFT created — proposed edits surfaced for owner review, none applied.
  Grounded in the engine's actual offline/single-operator reality, not the
  marketing copy.*
