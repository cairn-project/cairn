# BUILD-PLAN — public transparency read-surfaces

Branch: `feat/public-transparency`. PR-only (main is branch-protected at
`3bf4013`). Composes on the EXISTING engine (the one append-only transparency
log + its `verify_log`), the cause registry's gated public list, and the
finding-vetting verdict state. Forks nothing; adds NO write paths.

Traces to: REQUIREMENTS Frame 4 ("court-grade / auditable / maximally
transparent") + PLAN §3.6 (one log, two uses; independent monitor) + §3.9
(gated public cause list). This wave makes the "anyone can independently verify
Cairn's integrity WITHOUT privileged access" frame concrete as a READ-ONLY
projection.

---

## 1. The seam this PR builds

A cohesive **public-read module** (`cairn.public`) + a **`cairn public ...`**
CLI surface: the externally-legible, read-only projection that lets anyone (a
recruit, journalist, partner institution, skeptic) see what Cairn is doing and
independently verify its integrity, with NO privileged access. It is a pure
PROJECTION over already-public state: it adds no write path, no mutation, no new
trust surface.

Three read-surfaces, each composing on an existing gate/state:

1. **Published causes** — the public cause list (approved/live only), reusing
   the EXISTING listing gate `CauseRegistry.list_causes(status_filter=None)`
   (`src/cairn/cause/registry.py:151`), which returns only causes where
   `Cause.is_publicly_listable` is true (status ∈ {APPROVED, LIVE},
   `model.py:131`). Each is projected to a `PublicCauseView` exposing only the
   public summary: cause_id, name, description, status, the 5-frame
   self-assessment, partner-of-record posture, and non-sensitive counts.

2. **Vetted outcomes** — a public view of human-verified findings (the
   ROUTABLE/REJECTED outcomes from the finding-vetting gate). Projected to a
   `PublicVettedOutcomeView` exposing only REDACTED metadata: the `packet_hash`
   REFERENCE (a content hash, not content), the generic opaque `flag_label`, the
   `verdict` (routable/reject), the `reviewer_of_record` id, and the verdict
   timestamp. **Redaction by construction** (see §3).

3. **Public log verification** — the EXISTING independent `verify_log`
   (`src/cairn/ledger/translog.py:181`) exposed as a public-facing operation,
   plus a redacted, append-only public VIEW of the transparency log: per entry,
   only `index`, `kind`, `entry_hash`, `prev_hash`, `recorded_at` (the hash-chain
   linkage + timing) — NOT the entry payload. Anyone can confirm the log is
   internally consistent + untampered without privileged access.

---

## 2. Composition (reuse, do not reimplement)

- **Published causes** reuse `CauseRegistry.list_causes()` with the default
  (no-filter) public gate — the SAME gate already used by the `cairn causes`
  CLI. The public module NEVER re-derives listability; it calls the gate.
- **Vetted outcomes** reuse the finding-vetting verdict state. The finding's
  human-verified state comes from `FindingVetQueue.finding_state()` /
  `get_verdict()` (`src/cairn/vetting/finding_queue.py:204` / `:233`). To
  enumerate completed reviews the queue currently exposes only `list_pending()`
  (the inverse). Minimal addition: a READ-ONLY `list_reviewed()` on
  `FindingVetQueue` returning the verdict-recorded items (the public projection
  is built from those). This is a pure read (no mutation) — it mirrors the
  existing `list_pending()` read.
- **Public log verify** reuses `verify_log(path)` verbatim and
  `TransparencyLog.entries()` for the redacted entry view. The public verify is
  literally `verify_log` over the ledger's translog path; we add NO new
  verification logic.

The public module holds a read-only handle to a `Ledger` (for the translog path
+ blobstore the registries already use), a `CauseRegistry`, and a
`FindingVetQueue` — all constructed over the same ledger. It calls only their
read methods.

---

## 3. Redaction by construction (safety-load-bearing)

The redaction guarantee is **structural, not filtered-at-call-time**: the public
projection dataclasses (`PublicCauseView`, `PublicVettedOutcomeView`,
`PublicLogEntryView`) simply HAVE NO FIELD that can carry raw captured content or
PII. Safety comes from the projection's shape, not from a redaction step that
could be bypassed.

Concretely:
- `PublicVettedOutcomeView` carries `packet_hash` (a sha256 REFERENCE — opaque,
  reveals no content), `flag_label` (an opaque generic string by construction —
  `finding.py` hard-codes no domain vocabulary), `verdict`, `reviewer_of_record`,
  `decided_at`. There is NO field for the packet's content, the observation
  bytes, the analysis text, the captured target, or any requester/subject PII.
  The view cannot be constructed with such data because no parameter accepts it.
- `PublicLogEntryView` carries `index`, `kind`, `entry_hash`, `prev_hash`,
  `recorded_at` — the hash-chain skeleton + timing. It has NO `payload` field, so
  the (potentially identifying) entry payloads are not exposed; the chain is
  still independently verifiable because `verify_log` reads the FULL on-disk
  bytes itself (the public view is for human inspection of the skeleton, the
  verify is the integrity proof).
- `PublicCauseView` exposes only the already-public cause summary fields. It
  deliberately OMITS `decision_reason`, `decided_by`, and `created_by` — the
  public surface is the cause itself, not the internal decision/requester
  provenance. (Those remain available through the privileged registry; the public
  projection just has no field for them.)

This boundary is asserted in tests by enumerating the view dataclass fields and
asserting the forbidden field names are ABSENT (a structural assertion, not a
value check).

---

## 4. Named acceptance criteria (ODD §2.5 — every line maps to one)

- **AC.PUB.1 — published-causes projection reuses the listing gate.**
  `list_published_causes()` returns exactly the causes
  `CauseRegistry.list_causes(status_filter=None)` returns (approved/live only),
  each as a `PublicCauseView`. A requested/rejected/paused cause NEVER appears.
  Test: submit + approve one cause, submit a second (left requested), reject a
  third → only the approved one is published.

- **AC.PUB.2 — public-cause view exposes only the public summary fields.**
  `PublicCauseView` has fields {cause_id, name, description, status, five_frame,
  partner_of_record_posture, counts} and NO decision_reason / decided_by /
  created_by / target_conduct / protected_boundary internal fields beyond the
  public summary. Test: structural field-set assertion.

- **AC.PUB.3 — vetted-outcomes projection reuses the finding-vet verdict state.**
  `list_vetted_outcomes()` returns one `PublicVettedOutcomeView` per
  verdict-recorded finding, with `verdict` reflecting
  `FindingVetQueue.finding_state()` (routable/rejected). A pending (un-reviewed)
  finding NEVER appears. Test: flag two findings, record a ROUTABLE verdict on
  one + a REJECT on another, leave a third pending → exactly the two reviewed
  appear with the right verdicts; the pending one is absent.

- **AC.PUB.4 — vetted-outcome view is redacted by construction.**
  `PublicVettedOutcomeView` exposes only {packet_hash, flag_label, verdict,
  reviewer_of_record, decided_at} and has NO field carrying raw packet content /
  observation bytes / analysis text / PII. Test: structural field-set assertion
  (forbidden field names ABSENT; the dataclass cannot be constructed with raw
  content because no such parameter exists).

- **AC.PUB.5 — public log verify composes on `verify_log`.**
  `public_verify_log()` returns the SAME `LogVerification` that
  `verify_log(ledger.translog._path)` returns (ok / length / head_hash /
  failed_index / reason). Test: on an untampered ledger it returns ok=True with
  the right length.

- **AC.PUB.6 — redacted public log view exposes only the chain skeleton.**
  `list_public_log()` returns one `PublicLogEntryView` per entry with fields
  {index, kind, entry_hash, prev_hash, recorded_at} and NO `payload` field.
  Test: structural field-set assertion + count equals `len(entries)`.

- **AC.PUB.7 — `cairn public` CLI surface.** Subcommands
  `public causes` / `public outcomes` / `public verify-log` / `public log`
  each call the corresponding read function over a `--ledger` dir and print
  (human + `--json`). Read-only; exit 0 on success, exit 1 when public verify
  reports a tampered log. Test: drive each subcommand via `main([...])` over a
  populated ledger.

- **AC.PUB.8 (OUTCOME-ALTITUDE) — end-to-end public surfaces on a fresh ledger.**
  Driving the REAL public-read entry points end-to-end on a fresh ledger with no
  pre-arranged in-memory state: publish a cause (request → human-vetted approve)
  + record a human-vetted finding (flag → ROUTABLE verdict) → the public surfaces
  show EXACTLY the redacted public projection (the published cause; the routable
  vetted outcome with only redacted fields; the redacted log skeleton) and
  nothing privileged; `public_verify_log()` returns ok=True; THEN tamper one
  on-disk log entry → `public_verify_log()` returns ok=False with the failing
  index. Marked `outcome-altitude: true`. This is the load-bearing test: it
  drives the production entry points, asserts the redaction boundary on real
  data, AND asserts tamper-detection.

---

## 5. Read-only / scope discipline

- NO write paths added. The only new method on an existing class is
  `FindingVetQueue.list_reviewed()` — a pure READ mirroring `list_pending()`.
  Everything else is in the new `cairn.public` module + CLI, all read.
- The public module constructs registries over an existing ledger and calls only
  their read methods. It records NOTHING on the log, mutates NO cause/finding.
- If a setter is required anywhere → STOP (out of scope). None is.

## 6. Deferrals (explicitly OUT)

- Onward routing of a routable finding to real external recipients
  (network-touching; already deferred upstream — unchanged here).
- Any web/HTTP read API or HTML rendering of the public surfaces (this wave is
  the library + CLI projection; a served read API is a later wave).
- Authn/identity for "who is reading" (the public surfaces are public — no auth
  by design).
- Pagination / streaming for very large logs (the redacted view materializes the
  list; fine for the offline pilot scale).

## 7. Test plan

New `tests/test_public_transparency.py` covering AC.PUB.1–8, plus a
`tests/test_cli_public.py` for AC.PUB.7 CLI wiring. Deterministic, offline,
`FixedClock`, synthetic benign data only. Full suite green in a clean
Python 3.13 venv.
