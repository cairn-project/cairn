# BUILD-PLAN — human-in-the-loop two-gate vetting queue

Branch: `feat/vetting-queue`. PR-only (main is branch-protected). Composes on the
engine (ledger blobstore + the one append-only transparency log) AND the
cause/capture layers; forks nothing. Mission-NEUTRAL — findings are represented
generically (a `packet_hash` reference + an automated verdict + a generic flag
label); NO scam/phishing/sensitive content, NO real detection logic, NO real
recipients. The only worked example flags a SYNTHETIC finding referencing the
benign capture packet.

Traces to: REQUIREMENTS Frame 5 ("human-verified" — the safety frame made
structural), PLAN §3.9 (the gated cause decision this composes onto), §3.6
(content-addressed blobs + the one-log-two-uses transparency log).

---

## 1. The seam this PR builds

The **"human-verified" frame made concrete and structural**: two DISTINCT human
review gates, each **fail-closed** — nothing advances past a gate without a
recorded human verdict. The guarantee is enforced by the **absence of an
advance-path**, not by policy: an un-reviewed item simply has no method that
flips it to its advanced state.

### Gate 1 — Cause-vetting gate

A human cause-vetter reviews a *requested* cause before it can become
approved/listed. This composes on the existing cause request→decision path: it
adds the QUEUE (pending cause-requests awaiting human review), reviewer
assignment, and a recorded human verdict (approve/reject + reason) that **is the
human sign-off feeding the existing gated cause decision**. No cause becomes
publicly listable without a recorded human cause-vetter verdict.

**State machine (a `PendingCauseReview` item):**

```
            enqueue(cause_id)            assign(reviewer)
  (REQUESTED) ───────────────► AWAITING_REVIEW ──────────► UNDER_REVIEW
  cause in registry                  │ assign  │                 │
                                     └─────────┘                 │ record_verdict(approve|reject, reason, reviewer)
                                                                 ▼
                                                  VERDICT_RECORDED  (decision ∈ {APPROVE, REJECT})
```

Fail-closed by construction:
- `apply_cause_verdict(...)` is the ONLY function that calls the existing
  `CauseRegistry.decide_cause`, and it REFUSES unless a `VERDICT_RECORDED`
  human verdict exists for that cause. There is no other path from the queue to
  `decide_cause`. An un-reviewed cause therefore cannot be approved → cannot list
  (`Cause.is_publicly_listable` is already gated on APPROVED/LIVE).
- A reject verdict REQUIRES a non-empty reason (mirrors the existing cause-decision
  no-silent-rejection rule) — enforced at `record_verdict` time, before the queue
  even records it.

**Composition point with the existing cause-decision (the exact seam):** the human
verdict is the input to the *already-existing* `CauseRegistry.decide_cause(...)`
gated decision (`src/cairn/cause/registry.py:120` — the `decide_cause` method).
`apply_cause_verdict` reads the recorded human verdict, builds the five-frame
`GateCheckResult` the existing decision already requires, and calls
`decide_cause(approve=<human decision>, reason=<human reason>, decider=<reviewer>,
gate_result=...)`. We do NOT fork or re-implement the cause decision; we GATE it.

### Gate 2 — Finding-vetting gate

A human finding-vetter reviews a flagged FINDING before it may be marked ROUTABLE
(eligible to be acted on / routed onward). No finding becomes routable without a
recorded human finding-vetter verdict. The actual onward routing to external
recipients is OUT of scope (deferred, network-touching, security-reviewed later
wave); this gate only produces the human-verified ROUTABLE/REJECTED state.

A **`Finding`** is mission-neutral: a content-addressed record carrying
`packet_hash` (a reference to an existing examination packet — compose on the
capture store), an `automated_verdict` (a generic `{flag_label, confidence}`
shape — NO domain detection logic; the label is an opaque generic string like
`"flagged"`), and provenance. It carries no scam/phishing content.

**State machine (a `PendingFindingReview` item):**

```
            enqueue(finding)             assign(reviewer)
  (flagged) ────────────────► AWAITING_REVIEW ──────────► UNDER_REVIEW
  finding stored                    │ assign  │                 │
  (content-addressed)               └─────────┘                 │ record_verdict(routable|reject, reason, reviewer)
                                                                 ▼
                                              VERDICT_RECORDED  (decision ∈ {ROUTABLE, REJECT})
```

Fail-closed by construction:
- A finding's advanced (routable) state is derived SOLELY from a recorded human
  `ROUTABLE` verdict: `finding_state(finding_hash)` returns `ROUTABLE` only if a
  `VERDICT_RECORDED` entry with decision ROUTABLE exists; otherwise `PENDING` (or
  `REJECTED`). There is NO function that sets a finding routable without a verdict.
- A reject verdict REQUIRES a non-empty reason (no silent rejection).

---

## 2. File layout

```
src/cairn/vetting/__init__.py        NEW  package docstring + re-exports.
src/cairn/vetting/review.py          NEW  shared review primitives:
                                          ReviewStatus enum, ReviewDecision enums,
                                          ReviewVerdict (reviewer_id, decision,
                                          reason, recorded_at), VettingError.
src/cairn/vetting/cause_queue.py     NEW  CauseVetQueue: enqueue / list_pending /
                                          assign / record_verdict / get_verdict
                                          + apply_cause_verdict (the fail-closed
                                          bridge into CauseRegistry.decide_cause).
src/cairn/vetting/finding.py         NEW  Finding (packet_hash + automated_verdict
                                          {flag_label, confidence} + provenance),
                                          content-addressed; FindingState enum.
src/cairn/vetting/finding_queue.py   NEW  FindingVetQueue: flag (enqueue) /
                                          list_pending / assign / record_verdict /
                                          finding_state / is_routable.

src/cairn/ledger/translog.py         EDIT add the new KIND_* (same chain):
                                          KIND_CAUSE_VET_ENQUEUED,
                                          KIND_CAUSE_VET_ASSIGNED,
                                          KIND_CAUSE_VET_VERDICT,
                                          KIND_FINDING_FLAGGED,
                                          KIND_FINDING_VET_ASSIGNED,
                                          KIND_FINDING_VET_VERDICT.
src/cairn/ledger/__init__.py         EDIT export the new kinds.

tests/test_vetting_cause_queue.py    NEW  cause-gate: enqueue/assign/verdict +
                                          fail-closed (no apply without verdict) +
                                          no-silent-reject + translog/verify_log.
tests/test_vetting_finding_queue.py  NEW  finding-gate: flag/assign/verdict +
                                          fail-closed (not routable without verdict)
                                          + no-silent-reject + translog/verify_log.
tests/test_vetting_e2e.py            NEW  OUTCOME-ALTITUDE end-to-end, fresh ledger.
```

No new fixture, no CLI command in this PR (the queue is an operator/reviewer
primitive; a `cairn vet` CLI is a later wave). The abstraction is exercised
end-to-end via the library, mirroring the capture wave's library-only shape.

---

## 3. Named acceptance criteria (ODD §2.5 — every line maps to one)

- **AC.VET.1 — cause-vet enqueue.** A REQUESTED cause can be enqueued into the
  cause-vet queue; `list_pending()` returns it; a `CAUSE_VET_ENQUEUED` entry is on
  the transparency log. Enqueuing an already-decided cause is refused.
- **AC.VET.2 — cause-vet reviewer assignment.** A pending item can be assigned to a
  reviewer id (AWAITING_REVIEW → UNDER_REVIEW); a `CAUSE_VET_ASSIGNED` entry is
  logged.
- **AC.VET.3 — cause-vet recorded human verdict.** `record_verdict(cause_id,
  approve|reject, reason, reviewer)` records a `ReviewVerdict` (reviewer id,
  decision, reason, timestamp via the ledger clock); a `CAUSE_VET_VERDICT` entry is
  logged; a REJECT with empty reason is refused (no silent rejection).
- **AC.VET.4 — cause-vet fail-closed bridge.** `apply_cause_verdict(cause_id,
  registry, gate_result)` calls the existing `CauseRegistry.decide_cause` ONLY when
  a recorded human verdict exists for that cause; with NO recorded verdict it
  raises `VettingError` and the cause stays non-listable. The human verdict's
  decision + reason + reviewer are the inputs to `decide_cause`. This is the only
  path from the queue to the cause decision.
- **AC.VET.5 — finding flag/enqueue.** A mission-neutral `Finding` (packet_hash +
  automated_verdict {flag_label, confidence} + provenance) can be flagged into the
  finding-vet queue; it is content-addressed + stored; `list_pending()` returns it;
  a `FINDING_FLAGGED` entry is logged. (Mission-neutrality: the finding carries no
  domain content; `flag_label` is an opaque generic string.)
- **AC.VET.6 — finding-vet reviewer assignment.** A pending finding can be assigned
  to a reviewer id; a `FINDING_VET_ASSIGNED` entry is logged.
- **AC.VET.7 — finding-vet recorded human verdict + ROUTABLE gate.** `record_verdict
  (finding_hash, routable|reject, reason, reviewer)` records a `ReviewVerdict`; a
  `FINDING_VET_VERDICT` entry is logged; a REJECT with empty reason is refused.
  `finding_state(finding_hash)` returns ROUTABLE iff a recorded ROUTABLE verdict
  exists, REJECTED iff a recorded reject verdict exists, else PENDING.
  `is_routable(finding_hash)` is True ONLY after a recorded ROUTABLE verdict
  (fail-closed: PENDING by default, no advance-path without a verdict).
- **AC.VET.8 — transparency.** Every queue event + verdict is on the SAME
  append-only transparency log; the new KIND_* follow the existing pattern; the
  unchanged `verify_log` re-derives + verifies the chain over them.
- **AC.VET.9 (OUTCOME-ALTITUDE) — two-gate end-to-end on a fresh ledger.** With NO
  pre-arranged state, drive the REAL entry points end to end:
  (a) submit a cause request (REAL `CauseRegistry`) → enqueue into the cause-vet
      queue → assert it CANNOT list and `apply_cause_verdict` is REFUSED with no
      verdict → record a human approve verdict → `apply_cause_verdict` → assert the
      cause now lists; AND
  (b) capture a benign packet (REAL `capture_packet`) → flag a synthetic finding
      referencing its `packet_hash` → assert NOT routable with no verdict → record a
      human ROUTABLE verdict → assert `is_routable` is now True; AND
  (c) `verify_log` over the produced log is `ok`.
  Verified by `tests/test_vetting_e2e.py` invoking the production entry points with
  no pre-arranged state.

Every source line/branch/test maps to one of AC.VET.1–9. No defensive code for
unnamed cases.

---

## 4. Fail-closed guarantees (structural, not policy)

1. **Cause gate.** The ONLY call site of `CauseRegistry.decide_cause` inside this
   layer is `apply_cause_verdict`, which first reads the recorded human verdict and
   raises if absent. There is no other queue→decision edge. Combined with the
   existing `is_publicly_listable` gate (APPROVED/LIVE only), an un-reviewed cause
   cannot list.
2. **Finding gate.** `is_routable` is a pure function of the recorded verdict; there
   is no setter that marks a finding routable. Absent a recorded ROUTABLE verdict,
   the state is PENDING. The advanced state literally has no producer other than a
   human verdict.
3. **No silent rejection.** Both `record_verdict` methods refuse a reject decision
   with an empty/whitespace reason, mirroring `CauseRegistry.decide_cause`.
4. **Auditable.** Every event carries reviewer id + decision + reason + a timestamp
   from the ledger's injected clock; everything reconstructable from the log.

---

## 5. Deferrals (scope discipline — explicitly OUT)

- **Onward routing to real external recipients** — network-touching,
  security-reviewed, a later wave. This gate produces only the ROUTABLE/REJECTED
  human-verified state; it does NOT route.
- **Reviewer authn/authz backend + UI** — a reviewer here is just an id + a recorded
  decision. No auth, no identity verification, no UI.
- **Real detection logic / domain finding content** — findings are generic
  (packet_hash + opaque flag label + confidence); no scam/phishing/sensitive logic.
- **Multi-reviewer quorum / escalation on findings** — single recorded human verdict
  per gate in this wave (the engine's cross-model quorum is a separate, earlier
  layer for the *automated* verdict; the human gate here is one human sign-off).
- **A `cairn vet` CLI** — library-only this wave (mirrors the capture wave).

---

## 6. Composition (compose, don't reimplement)

- Cause decision: GATE `CauseRegistry.decide_cause` (`cause/registry.py`), do not
  fork it.
- Packet store: a finding references an existing `packet_hash`; the e2e produces one
  via the REAL `capture_packet` (`capture/store.py`).
- Transparency log: extend the ONE `TransparencyLog` with new KIND_*; `verify_log`
  is unchanged and covers them (it is kind-agnostic — it verifies the chain, not the
  vocabulary).
- Blob store + clock: queue items + findings + verdicts are content-addressed /
  persisted over `ledger.blobs`; timestamps come from `ledger._clock` (injected),
  mirroring `CaptureGate` / `CauseRegistry`.

## 7. SECURITY.md / CHANGELOG

- CHANGELOG: add an `[Unreleased]` entry describing the two-gate vetting queue.
- SECURITY.md: extend the in-scope list to name the two-gate vetting queue as a new
  trust surface (the fail-closed human-verified gates are genuinely a new trust
  boundary worth naming for reporters).
