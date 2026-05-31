# BUILD-PLAN — routing / action spine

Branch: `feat/routing-spine`. PR-only (main is branch-protected). Composes on the
engine (ledger blobstore + the one append-only transparency log) AND the
vetting/cause/capture layers; forks nothing. Mission-NEUTRAL — recipients and
findings are represented generically (a recipient = id + locality/domain tags + a
deterministic offline channel; a finding carries only its existing mission-neutral
attributes — a `packet_hash` reference + an opaque generic `flag_label`); NO
scam/phishing/sensitive content, NO real external recipients, NO network egress.
The only channel shipped is a deterministic, OFFLINE in-memory channel.

This is the KEYSTONE the prime directive ("practical help = action taken") demands:
it turns a human-verified ROUTABLE finding into a **recorded action** dispatched to
the recipient best fit to act on it, closing detect→verify→human-vet→ACT. The
"action taken" the directive measures is the recorded routing event + the recipient
acknowledgement on the SAME transparency log.

Traces to: the PRIME DIRECTIVE (action taken, locality-aware escalation),
REQUIREMENTS Frame 5 (human-verified — this layer GATES on its ROUTABLE output and
never re-derives it), PLAN §3.6 (content-addressed blobs + the one-log-two-uses
transparency log), the existing `cause` layer (a finding/route belongs to a cause).

---

## 1. The seam this PR builds

The **routing/action spine**: the path from a human-verified ROUTABLE `Finding` to a
**recorded action** delivered to a best-fit recipient, with **locality-aware
escalation** and **no silent drops**. Three composed pieces:

### 1a. `RecipientChannel` seam — how a routed finding reaches a recipient

A narrow interface (a `Protocol`) by which a routed finding is **delivered** to a
recipient and an **acknowledgement** comes back. This is the seam where, in a later
separately-security-reviewed wave, real network channels (registrar/partner/abuse
endpoints) will plug in. THIS wave ships ONLY a deterministic, offline
`InMemoryRecipientChannel` that records the dispatch and returns a synthetic
`DispatchAck` — no network, no real recipient. The seam is the extension point; the
in-memory channel is the only implementation shipped.

```
class RecipientChannel(Protocol):
    name: str
    def deliver(self, dispatch: RoutingDispatch) -> DispatchAck: ...
```

`DispatchAck` is a generic, deterministic acknowledgement: an `accepted` bool, an
opaque `ack_ref` (deterministic — derived from the dispatch material, NOT a random
nonce, so the worked example is reproducible), the `channel` name, and an
`acknowledged_at` timestamp from the ledger clock.

### 1b. Routing policy — `route(finding) -> Recipient` with locality-aware escalation

A `Recipient` is mission-neutral: an `id`, a set of mission-neutral `locality` tags
and `domain` tags, and the channel it is reachable on. A `RecipientRegistry` holds a
set of recipients plus a designated **fallback recipient** (the explicit
escalation target).

`RoutingPolicy.route(finding, attributes) -> RoutingDecision` selects the best-fit
recipient by matching the finding's mission-neutral routing attributes
(`locality` + `domain`, supplied at dispatch time — they are NOT detection logic,
just generic tags) against the registry's recipients:

- **Best-fit match.** A recipient matches iff its `locality` tags AND `domain` tags
  both intersect the finding's requested locality/domain attributes. Among matches,
  the best fit is the one with the **most specific** match (the highest count of
  overlapping locality+domain tags); ties broken deterministically by recipient id
  (lexicographic) so routing is reproducible.
- **Locality-aware escalation (the explicit, recorded rule).** If NO recipient
  matches the finding's locality+domain, the policy **escalates to the registry's
  designated fallback recipient** and records the decision as an
  `ESCALATED_TO_FALLBACK` route reason (vs `MATCHED` for a direct match). A
  `RoutingDecision` therefore ALWAYS yields a recipient — there is no "no recipient"
  branch, so **no routable finding is ever silently dropped**. If a registry has no
  recipients AND no fallback configured, `route` RAISES (a misconfigured registry is
  a hard error, never a silent drop) — this is a named, refused case, not a drop.

The escalation rule in one line: **match on (locality ∩ domain); on no match,
escalate to the registry's explicit fallback recipient and record
`ESCALATED_TO_FALLBACK`; never return nothing.**

### 1c. Dispatch driver — `dispatch_routable_finding(...)`

The orchestrator that produces the recorded action:

1. **Fail-closed human-verified gate.** Reuse `FindingVetQueue.is_routable(
   finding_hash)` / `finding_state(...)` — do NOT re-derive routability. If the
   finding is not ROUTABLE (PENDING or REJECTED), **raise `RoutingRefused`** — a
   non-routable finding is REFUSED, never routed.
2. **Select recipient** via `RoutingPolicy.route(...)` (best-fit or escalation).
3. **Deliver** via the selected recipient's `RecipientChannel.deliver(...)`,
   obtaining a `DispatchAck`.
4. **Record the action** on the SAME append-only transparency log: a
   `KIND_FINDING_ROUTED` entry (the routing event — finding_hash, cause_id,
   recipient_id, route_reason MATCHED/ESCALATED_TO_FALLBACK, channel) followed by a
   `KIND_ROUTE_ACK_RECORDED` entry (the recipient acknowledgement/outcome —
   finding_hash, recipient_id, accepted, ack_ref, channel). The two entries together
   ARE the "action taken". Returns a `RoutingRecord` summarizing both.

The dispatch is content-addressed/persisted over `ledger.blobs` for an auditable
record, mirroring the vetting/capture layers; the timestamp comes from the injected
ledger clock.

---

## 2. File layout

```
src/cairn/routing/__init__.py        NEW  package docstring + re-exports.
src/cairn/routing/recipient.py       NEW  Recipient (id + locality/domain tags +
                                          channel name), RecipientRegistry (set +
                                          designated fallback), RoutingError.
src/cairn/routing/channel.py         NEW  RecipientChannel Protocol seam +
                                          RoutingDispatch + DispatchAck +
                                          InMemoryRecipientChannel (the only,
                                          deterministic offline channel) +
                                          RecordingChannel sink for inspection.
src/cairn/routing/policy.py          NEW  RouteReason enum (MATCHED /
                                          ESCALATED_TO_FALLBACK), RoutingDecision,
                                          RoutingPolicy.route (best-fit + the
                                          explicit locality-aware escalation rule).
src/cairn/routing/dispatch.py        NEW  RoutingRefused, RoutingRecord,
                                          dispatch_routable_finding (the fail-closed
                                          driver: gate on is_routable → route →
                                          deliver → record the two translog events).

src/cairn/ledger/translog.py         EDIT add the new KIND_* (same chain):
                                          KIND_FINDING_ROUTED,
                                          KIND_ROUTE_ACK_RECORDED.
src/cairn/ledger/__init__.py         EDIT export the two new kinds.

tests/test_routing_recipient.py      NEW  recipient registry + fallback config.
tests/test_routing_policy.py         NEW  best-fit match, tie-break, the explicit
                                          escalation-to-fallback rule, misconfig raise.
tests/test_routing_channel.py        NEW  in-memory channel deterministic ack +
                                          recording.
tests/test_routing_dispatch.py       NEW  fail-closed gate (REFUSE non-routable) +
                                          routed-action recording + translog/verify.
tests/test_routing_e2e.py            NEW  OUTCOME-ALTITUDE end-to-end, fresh ledger.
```

No new fixture, no CLI command in this PR (routing is an operator primitive; a
`cairn route` CLI is a later wave — mirrors the capture/vetting library-only shape).

---

## 3. Named acceptance criteria (ODD §2.5 — every line maps to one)

- **AC.ROUTE.1 — recipient registry + explicit fallback.** A `RecipientRegistry`
  holds a set of mission-neutral `Recipient`s (id + locality tags + domain tags +
  channel name) and a designated fallback recipient. The fallback is explicit
  (named at registry construction), retrievable, and distinct from "no recipient".
  A registry with neither recipients nor a fallback is a misconfiguration.

- **AC.ROUTE.2 — best-fit routing match.** `RoutingPolicy.route(finding, attrs)`
  returns a `RoutingDecision(recipient, reason=MATCHED, ...)` selecting the recipient
  whose locality tags AND domain tags both intersect the finding's requested
  locality+domain, choosing the most-specific match (max overlapping-tag count),
  ties broken deterministically by recipient id. Reproducible for identical input.

- **AC.ROUTE.3 — locality-aware escalation (no silent drop).** When NO recipient
  matches the finding's locality+domain, `route` returns
  `RoutingDecision(recipient=<fallback>, reason=ESCALATED_TO_FALLBACK, ...)` — the
  explicit recorded escalation rule. `route` NEVER returns without a recipient. A
  registry with no recipients and no fallback raises `RoutingError` (named refused
  misconfiguration, NOT a silent drop).

- **AC.ROUTE.4 — `RecipientChannel` seam + deterministic offline channel.** The
  `RecipientChannel` Protocol defines `deliver(dispatch) -> DispatchAck`. The shipped
  `InMemoryRecipientChannel` is deterministic + offline: it records every dispatch
  it receives and returns a `DispatchAck` whose `ack_ref` is derived from the
  dispatch material (reproducible, no network, no randomness). No other channel
  ships.

- **AC.ROUTE.5 — fail-closed dispatch on the human-verified gate.**
  `dispatch_routable_finding(...)` reuses `FindingVetQueue.is_routable` /
  `finding_state` and RAISES `RoutingRefused` for a finding that is not ROUTABLE
  (PENDING or REJECTED). A non-routable finding is REFUSED, never routed/delivered/
  recorded. Routability is NOT re-derived here — it is read from the vetting gate.

- **AC.ROUTE.6 — recorded action (the prime-directive unit).** For a ROUTABLE
  finding, `dispatch_routable_finding` selects the recipient (AC.ROUTE.2/3),
  delivers via the channel (AC.ROUTE.4), and records on the SAME transparency log a
  `KIND_FINDING_ROUTED` entry (finding_hash, cause_id, recipient_id, route_reason,
  channel) AND a `KIND_ROUTE_ACK_RECORDED` entry (finding_hash, recipient_id,
  accepted, ack_ref, channel). It returns a `RoutingRecord` summarizing both. These
  two entries ARE the "action taken".

- **AC.ROUTE.7 — transparency.** The new KIND_* follow the existing pattern; every
  routing event + acknowledgement is on the SAME append-only transparency log; the
  unchanged `verify_log` re-derives + verifies the chain over them (it is
  kind-agnostic — verifies the chain, not the vocabulary).

- **AC.ROUTE.8 (OUTCOME-ALTITUDE) — full loop on a fresh ledger.** With NO
  pre-arranged state, drive the REAL entry points end to end:
  (a) capture a benign packet (REAL `capture_packet`) → flag a synthetic finding
      (REAL `FindingVetQueue.flag`) → record a human ROUTABLE verdict → build a
      `RecipientRegistry` (a matching recipient + a fallback) on an
      `InMemoryRecipientChannel` → `dispatch_routable_finding` selects the matching
      recipient, delivers, and the channel records the dispatch; the
      `KIND_FINDING_ROUTED` + `KIND_ROUTE_ACK_RECORDED` entries are on the log; the
      returned `RoutingRecord` names the recipient + the ack; AND
  (b) a SECOND finding whose locality/domain match nothing routes via
      `ESCALATED_TO_FALLBACK` to the fallback recipient (no silent drop), recorded; AND
  (c) a NON-ROUTABLE finding (verdict REJECTED, or no verdict) is REFUSED
      (`RoutingRefused`) — not routed, not delivered, not recorded; AND
  (d) `verify_log` over the produced transparency log is `ok`.
  Verified by `tests/test_routing_e2e.py` invoking the production entry points with
  no pre-arranged state (incl. the refuse-non-routable case).

Every source line/branch/test maps to one of AC.ROUTE.1–8. No defensive code for
unnamed cases.

---

## 4. Fail-closed + no-silent-drop guarantees (structural, not policy)

1. **Fail-closed human-verified gate.** `dispatch_routable_finding` calls
   `FindingVetQueue.is_routable(finding_hash)` as its FIRST action and raises
   `RoutingRefused` if false. There is no dispatch path that bypasses this check;
   delivery + recording happen strictly after it passes. Routability is read from
   the vetting gate, never re-derived.
2. **No silent drop.** `RoutingPolicy.route` has no return path that yields no
   recipient: it returns either a MATCHED recipient or the explicit fallback
   (ESCALATED_TO_FALLBACK). The only non-return is a RAISE on a misconfigured
   registry (no recipients AND no fallback) — a named, loud error, not a drop.
3. **Recorded action.** Every successful dispatch writes BOTH a routing event and an
   acknowledgement to the one transparency log; the action is reconstructable from
   the log (court-grade auditability, Frame 4).
4. **Deterministic + offline.** The only channel is in-memory; the ack_ref is
   derived from the dispatch material; timestamps come from the injected clock —
   the whole spine is reproducible and testable offline.

---

## 5. Deferrals (scope discipline — explicitly OUT)

- **Real external recipient integration / network egress** — Safe Browsing,
  abuse.ch, registrars, partner endpoints, email/HTTP transport. Network-touching;
  a deliberately deferred, separately-security-reviewed later wave. This wave ships
  ONLY the deterministic offline `InMemoryRecipientChannel` behind the
  `RecipientChannel` seam (the seam is where real egress will later plug in).
- **Real recipient directory / partner-of-record resolution** — the registry here is
  an in-memory set of generic recipients with mission-neutral tags; a real
  partner-of-record directory + identity verification is a later wave.
- **Retry / delivery-failure / dead-letter handling** — the in-memory channel always
  acknowledges deterministically; real transport failure semantics belong with the
  real channels (deferred).
- **Multi-recipient fan-out / quorum routing** — one best-fit (or fallback)
  recipient per finding this wave.
- **A `cairn route` CLI** — library-only this wave (mirrors capture/vetting).

---

## 6. Composition (compose, don't reimplement)

- Human-verified gate: REUSE `FindingVetQueue.is_routable` / `finding_state`
  (`vetting/finding_queue.py`); never re-derive routability.
- Finding model: a routed finding is the EXISTING mission-neutral `Finding`
  (`vetting/finding.py`) — packet_hash ref + opaque flag label + cause_id; the e2e
  produces one via the REAL `FindingVetQueue.flag` over a REAL `capture_packet`.
- Cause layer: a finding/route belongs to a cause via the finding's existing
  `cause_id`; the routing record carries it (no new cause surface).
- Transparency log: extend the ONE `TransparencyLog` with `KIND_FINDING_ROUTED` +
  `KIND_ROUTE_ACK_RECORDED`; `verify_log` is unchanged and covers them.
- Blob store + clock: the dispatch record is content-addressed / persisted over
  `ledger.blobs`; timestamps come from `ledger._clock` (injected), mirroring
  `FindingVetQueue` / `capture_packet`.

---

## 7. SECURITY.md / CHANGELOG

- CHANGELOG: add an `[Unreleased]` entry describing the routing/action spine (the
  RecipientChannel seam, the locality-aware-escalation routing policy, the
  fail-closed dispatch driver, the two new transparency kinds).
- SECURITY.md: extend the in-scope list to name the routing/action spine as a new
  trust surface — specifically the `RecipientChannel` seam (the place where, in a
  later wave, real network egress will live) and the fail-closed
  routable-only/no-silent-drop dispatch guarantee, with the explicit note that the
  only channel shipped is the deterministic offline `InMemoryRecipientChannel` and
  real external-recipient egress is a deferred, separately-security-reviewed wave.
