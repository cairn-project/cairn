# Threat Model (starter)

> **Status: starter draft for maintainer review.** This document is written in
> the same neutral *security-invariant* register as [`SECURITY.md`](../SECURITY.md):
> it describes the security **properties, trust boundaries, and invariants that
> must hold** — what must be true and what must not be permitted — rather than
> recipes for abuse. Several sections deliberately leave a `[PLACEHOLDER: …]` where
> a complete treatment would require sensitive, mission-specific detail; those are
> consolidated in [§5](#5-open-areas--to-flesh-out) as the maintainer's follow-ups.
>
> This model covers the engine code in **this** repository at its current phase.
> The network-touching phases named throughout `SECURITY.md` (real headless-browser
> capture, real external-recipient egress) are **not yet in this repository** and
> are each an independently security-reviewed phase; this document notes where their
> trust boundary will sit but does not model their internals.

---

## 1. Scope & assets

Cairn is a cause-coordination engine built to be distributed: it runs many causes
on one protocol, with the aim of coordinating distributed detection-and-analysis
work and turning human-signed-off outcomes into recorded action. (Today it runs
single-operator and offline; the distributed deployment is a deferred phase — see
the maturity framing in `README.md` and `SECURITY.md`.) Throughout this document,
**"human-verified" / "human-signed-off" means a recorded human verdict (with a
reason) exists — NOT that the human was authenticated, independent, or
qualified.** Identity authentication is an explicit deferred placeholder
(INV-Z5); see [`SECURITY.md`](../SECURITY.md) → "What the human gate does — and
does NOT — guarantee today" for the precise boundary. The assets worth
protecting, described in the project's own terms (verified against `src/`):

1. **The cause registry & governance record** (`cairn.cause`, `cairn.contribute`).
   The set of causes, their request→decision history, the five-frame gate-check
   verdicts behind each decision, and the contributor-consent records. The asset
   is the *integrity and completeness* of this record — that what is listed was
   approved, and that every approval/rejection is reasoned and recorded.

2. **The captured evidence bundles** (`cairn.capture`). Each
   `ExaminationPacket` is a frozen, content-addressed, **inert** snapshot of a
   target — static observations only (rendered/DOM text, header maps, registration
   metadata, hashes), with no executable content and no live locator. The asset is
   both the *integrity* of the bundle (content-addressing makes tampering evident)
   and the *inertness guarantee* (the bundle cannot be turned back into a live
   action).

3. **The human vetting state** (`cairn.vetting`). Two queues, each producing a
   single load-bearing fact: a cause's listability, and a finding's routability.
   The asset is the *authority* of that fact — that it derives only from a recorded
   human verdict, never from any other path.

4. **The routing / action spine** (`cairn.routing`). The decision of which
   recipient a routable finding is delivered to, the delivery event, and the
   recorded acknowledgement. The asset is the *fidelity and non-disappearance* of
   the action: a routable finding reaches a recorded recipient or a recorded
   escalation, and the action it triggered is auditable.

5. **The transparency log** (`cairn.ledger.translog`). One append-only,
   hash-chained log carrying every governance, consent, capture, vetting, and
   routing event. The asset is the *tamper-evidence* of the whole history — the
   property that an edited, removed, or reordered entry is detectable by an
   independent monitor with no privileged access.

6. **The public read surfaces** (`cairn.public`). Read-only projections of the
   above for any external observer. The asset is *what they must NOT carry* —
   raw captured content, analysis text, internal provenance, or PII.

---

## 2. Trust boundaries

A trust boundary is a place where data or authority crosses from a less-trusted
side into a more-trusted side, and where an invariant must be enforced on the
crossing. The boundaries in this repository:

| # | Boundary | Untrusted side → trusted side | What must be enforced at the crossing |
|---|----------|-------------------------------|----------------------------------------|
| TB-1 | **Cause request intake** | An anonymous/contributor cause *draft* → the cause registry | A draft enters only as a non-listable `REQUESTED` cause; it acquires listability only by crossing TB-3. |
| TB-2 | **Capture-role grant** | Any node → the privileged CAPTURE role | A node may produce evidence bundles only with an active, recorded, revocable grant; absence of a grant is refusal. |
| TB-3 | **The cause-vetting gate** | A requested cause → a publicly-listable cause | A cause crosses only via a recorded human verdict feeding the existing gated decision; there is no other advance-path. |
| TB-4 | **The finding-vetting gate** | A flagged (machine-judged) finding → a routable finding | A finding crosses only via a recorded human ROUTABLE verdict; the routable fact is derived from that verdict alone. |
| TB-5 | **The routing dispatch** | A routable finding → a delivered, recorded action | Dispatch crosses only for a human-verified routable finding, and never lands *nowhere*. |
| TB-6 | **The analysis seam** | A live target → the open analysis layer | The analyst receives only the frozen inert bundle; "re-visit the live target" must not be an expressible operation. |
| TB-7 | **The public read surface** | Internal ledger state → any external observer | Only redacted, externally-legible projection crosses outward; raw content / provenance / PII must not. |

Two boundaries named in `SECURITY.md` are **deferred trust seams** — present in
the code as a deterministic offline placeholder, with the real network crossing
scheduled for a later, independently reviewed phase:

- The `RecipientChannel` delivery seam (today only the offline
  `InMemoryRecipientChannel`) is where real external egress will eventually live.
- The capture *port* (today only the offline `StaticDocumentCapturePort`) is where
  a real headless-browser / network fetch will eventually live.

The boundary is named now precisely so the invariants below are stated in terms
the future network phase must continue to satisfy.

---

## 3. Security invariants / properties that must hold

The "must not happen" list, grouped by the standard categories and
cross-referencing the invariants `SECURITY.md` already states. Each is a property
the system must preserve; several carry a placeholder where the *specifics* of an
abuse case would require sensitive detail.

### 3.1 Integrity

- **INV-I1 — Listability derives only from an approved decision.** A cause must
  not become publicly listable (or able to accept contributor compute) except
  through a recorded `CAUSE_DECISION` that approves it. *(Reinforces SECURITY.md's
  listing-eligibility statement; enforced by `CauseRegistry.decide_cause` +
  `is_publicly_listable`.)*

- **INV-I2 — No decision without a reason and a complete gate-check.** A cause
  decision must not be recordable with an empty reason, nor on an incomplete
  five-frame gate-check; both approvals and rejections must be recorded with their
  reason. *(Enforced by `decide_cause` + `five_frame_gate_check`.)*

- **INV-I3 — Captured bundles are tamper-evident.** An evidence bundle's content
  address must commit to its full material, such that an edited observation or an
  edited packet is detected on load and rejected. *(Enforced by content-hash
  re-derivation in `Observation.from_dict` / `ExaminationPacket.from_dict`.)*

- **INV-I4 — The transparency log is tamper-evident end-to-end.** An edited,
  removed, or reordered log entry must be detectable by an independent monitor
  that re-derives every hash and chain link from raw on-disk bytes, trusting no
  stored hash. *(Enforced by `verify_log`; reinforces SECURITY.md's
  finding-record durability frame.)*

- **INV-I5 — Routing reflects only the verified finding.** The recorded action
  for a finding must reflect that finding's actual evidence reference and verdict;
  it must not be possible to record an action attributing a different finding's
  evidence or a different verdict. *(Dispatch loads the finding by its content
  address and reuses the vetting verdict; it does not re-derive either.)*

- **INV-I6 — [PLACEHOLDER: integrity of mission-specific finding semantics] — to
  be fleshed out with the maintainer.** Where a cause attaches domain meaning to a
  generic flag label or routing tag, the invariants protecting *that* meaning from
  being forged or misattributed are mission-specific and belong with the cause's
  own policy.

### 3.2 Confidentiality / exposure

- **INV-C1 — Public surfaces carry no raw content.** A public projection must not
  be constructible with raw captured content, observation bytes, analysis text,
  internal decision provenance, or PII — the projection's *shape* (no field accepts
  such data) is the boundary, not a filter that could be bypassed. *(Enforced by
  the redaction-by-construction views in `cairn.public` +
  `FORBIDDEN_PUBLIC_FIELDS`.)*

- **INV-C2 — Evidence references reveal only an opaque address.** A public
  vetted-outcome must reference its evidence by content-address (an opaque hash)
  only, never by a dereferenceable locator or by the captured content itself.
  *(`PublicVettedOutcomeView` carries `packet_hash` only.)*

- **INV-C3 — The redacted log skeleton omits payloads.** The public log view must
  expose only the chain skeleton (index / kind / hashes / time), never entry
  payloads, while remaining independently verifiable from the full on-disk bytes.
  *(`PublicLogEntryView` + `public_verify_log`.)*

- **INV-C4 — [PLACEHOLDER: protection of subject / requester identity] — to be
  fleshed out with the maintainer.** The handling required to prevent a subject of
  a finding, or a cause requester, from being identified or correlated across
  surfaces is mission-sensitive and must be specified per the project's
  population.

### 3.3 Availability

- **INV-A1 — No silent drop of a routable finding.** Every routable finding must
  resolve to a matched recipient OR an explicitly-recorded fallback escalation —
  never nowhere. A misconfigured registry must raise a named, loud error rather
  than drop. *(Reinforces SECURITY.md's routing-integrity "no silent drop"
  property; enforced by `RoutingPolicy.route` + the explicit fallback.)*

- **INV-A2 — Append-only progress.** The transparency log must only ever grow;
  recorded governance, consent, capture, vetting, and routing events must remain
  present and verifiable. Loss or truncation of history must be detectable (it
  breaks the chain). *(Append-only `TransparencyLog` + `verify_log`.)*

- **INV-A3 — [PLACEHOLDER: resource-exhaustion / flooding resistance of the
  intake and queue surfaces] — to be fleshed out with the maintainer.** The
  properties that must hold when intake (cause requests, flags) is driven at high
  volume, and how queue growth is bounded or paced, depend on the deployment and
  are a maintainer follow-up.

### 3.4 Authorization / abuse-of-process

- **INV-Z1 — Capture is privileged and fail-closed.** Producing an evidence
  bundle must be refused for any node without an active capture-role grant; an
  unknown node is treated as ungranted. *(Enforced by `capture_packet` gating on
  `CaptureGate.is_granted`.)*

- **INV-Z2 — No advance-path around either human gate.** There must be no way to
  make a cause listable, or a finding routable, without a recorded human verdict —
  and no way to record a silent rejection (a rejection with no reason). The safety
  is the *absence* of any other path. *(Reinforces SECURITY.md's two-gate frame;
  enforced by `apply_cause_verdict`, `finding_state`/`is_routable`, and
  `require_reason_on_reject`.)*

- **INV-Z3 — Dispatch is fail-closed on the human verdict.** A finding that is
  PENDING or REJECTED must be refused before any recipient selection, delivery, or
  recording occurs; dispatch must reuse the vetting state, never re-derive
  routability. *(Enforced by `dispatch_routable_finding` raising `RoutingRefused`.)*

- **INV-Z4 — Consent is explicit and revocable.** A node must not be enlisted to a
  cause without a recorded active consent, opt-in must be refused for a
  non-listable cause, and revocation must be recorded. *(Enforced by
  `OptInRegistry.opt_in` / `revoke` + the listability check.)*

- **INV-Z5 — [PLACEHOLDER: integrity of reviewer / grantor identity and role
  separation] — to be fleshed out with the maintainer.** The properties that must
  hold so that the recorded "reviewer of record" and "granted_by" actually
  correspond to the authorized human, and the separation-of-duties expectations
  between roles, depend on the deployment's identity/authentication layer (out of
  scope for this repository's logic) and are a maintainer follow-up.

- **INV-Z6 — [PLACEHOLDER: misuse of the engine to target a non-abusive party] —
  to be fleshed out with the maintainer.** The process-integrity properties that
  keep the vetting gates from being driven to act against a legitimate party are
  mission-sensitive (they intersect the cause's own conduct/boundary definitions)
  and must be specified with the maintainer.

### 3.5 Auditability

- **INV-U1 — Every governance-relevant act is on one verifiable chain.** Cause
  requests/decisions, consent grants/revokes, capture grants/revokes and captures,
  both vetting gates' enqueue/assign/verdict events, and every routing event +
  acknowledgement must all be appended to the SAME append-only chain, covered by
  the SAME independent verify. *(All layers append to the one `TransparencyLog`.)*

- **INV-U2 — Decisions are independently re-derivable.** Any observer must be able
  to confirm the chain's integrity, and to see that every advance (listable,
  routable, acted-on) was preceded by its required recorded verdict, without
  privileged access. *(`verify_log` + the public projections.)*

- **INV-U3 — [PLACEHOLDER: long-horizon non-repudiation / external anchoring] — to
  be fleshed out with the maintainer.** Whether and how the head of the chain is
  anchored externally (so the operator itself cannot rewrite history undetected
  across a long horizon) is a property beyond this repository's single-log
  implementation and is a maintainer follow-up.

---

## 4. Existing mitigations (verified against the code)

The invariants above are not aspirational; the current phase already implements
these mitigations (each checked against `src/`):

- **Fail-closed capture role.** `CaptureGate.is_granted` returns False for an
  unknown node; `capture_packet` raises `CaptureRefused` without an active grant.
  Grants/revokes are recorded and revocable. *(INV-Z1.)*

- **Inert evidence by construction.** Observations validate as plain JSON at
  construction (no callables); the packet carries no `url`/`locator`/`endpoint`
  field; the analyst-facing `AnalysisView` exposes no `fetch`/`refetch`/`visit`
  method. "Re-visit the live target" is excluded by the absence of any locator/
  fetch surface, not by policy. *(TB-6, INV-I3.)*

- **Two fail-closed human gates with no advance-path.** `apply_cause_verdict` is
  the only bridge into the cause decision and refuses without a recorded verdict;
  `finding_state`/`is_routable` derive routability solely from a recorded human
  verdict and default to PENDING; `require_reason_on_reject` forbids a reasonless
  rejection. *(TB-3, TB-4, INV-Z2.)*

- **Reasoned, structurally-gated cause decisions.** `decide_cause` refuses an
  empty reason and an incomplete five-frame gate-check; both approval and
  rejection are recorded with their reason. *(INV-I1, INV-I2.)*

- **Fail-closed routing with no silent drop.** `dispatch_routable_finding` refuses
  any non-routable finding before selection/delivery/recording;
  `RoutingPolicy.route` always returns a matched recipient or an explicit fallback,
  and raises loudly on a registry with neither. *(INV-Z3, INV-A1, INV-I5.)*

- **Explicit, revocable, listability-gated consent.** `OptInRegistry.opt_in`
  refuses a non-listable cause and records an active consent; `revoke` records the
  withdrawal. *(INV-Z4.)*

- **Tamper-evident append-only transparency log.** `verify_log` re-derives every
  entry hash and chain link from raw bytes, detecting a flipped byte, an edited
  payload, a removed entry, and a reordered entry; all layers append to this one
  chain. *(INV-I4, INV-A2, INV-U1.)*

- **Read-only public projection, redacted by construction.** The public views have
  no field that can carry raw content, analysis text, internal provenance, or PII;
  `public_verify_log` reuses the engine's verify verbatim over the full on-disk
  bytes. *(TB-7, INV-C1, INV-C2, INV-C3, INV-U2.)*

---

## 5. Open areas / to flesh out

The placeholders above, consolidated as the maintainer's follow-ups. Each names a
neutral area only; the sensitive specifics are intentionally deferred to the
maintainer (the owner-authorized in-parts approach).

| Ref | Area to flesh out |
|-----|-------------------|
| INV-I6 | Integrity of mission-specific finding semantics (forging/misattributing a cause's domain meaning over a generic label/tag). |
| INV-C4 | Protection of subject / requester identity (preventing identification or cross-surface correlation). |
| INV-A3 | Resource-exhaustion / flooding resistance of the intake and queue surfaces. |
| INV-Z5 | Integrity of reviewer/grantor identity and role separation (the deployment identity/auth layer). |
| INV-Z6 | Misuse of the engine to target a non-abusive party (process-integrity of the gates against a legitimate party). |
| INV-U3 | Long-horizon non-repudiation / external anchoring of the transparency-log head. |

Two cross-cutting follow-ups, both already named as deferred network seams in
`SECURITY.md`, will need their own threat treatment when their phase lands:

- **The real capture port** (headless-browser / network fetch) — the live-target
  trust boundary that today is held by the offline `StaticDocumentCapturePort`.
- **The real recipient channel** (external egress) — the network delivery boundary
  that today is held by the offline `InMemoryRecipientChannel`.

When those phases are designed, the invariants in [§3](#3-security-invariants--properties-that-must-hold)
should be re-checked to confirm each still holds across the new network crossing,
and the relevant placeholders revisited with their now-concrete attack surface.
