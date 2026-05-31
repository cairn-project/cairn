# BUILD-PLAN — inert evidence-bundle (examination-packet) capture abstraction

Branch: `feat/capture-bundle`. PR-only (main is branch-protected). Composes on the
engine (ledger blobstore + transparency log) AND the cause/contribute layers
(opt-in/consent gating posture); forks nothing. Mission-NEUTRAL — the only worked
example captures a STATIC, LOCAL, SYNTHETIC document fixture. NO real browser, NO
real URL fetched, NO network egress, NO scam/phishing/sensitive content.

Traces to: PLAN §3.6 (content-addressed blobs + the one-log-two-uses transparency
log), §3.9b (explicit, gated, recorded consent — mirrored here as the trust-gated
CAPTURE role), §3.5 (the open verify/analysis layer consumes a static artifact).

---

## 1. The seam this PR builds

A **trust-gated CAPTURE operator** turns a live target into a **STATIC, INERT
examination packet**; an **open analysis layer** judges that packet WITHOUT anyone
re-visiting the live target. The load-bearing safety principle, structurally
enforced by the design: *the analyst (and their AI) only ever sees the inert
bundle; nobody browses the live site to analyze it.* Capture happens once, by a
gated operator, into a frozen content-addressed artifact; analysis consumes the
artifact.

Three pieces:

1. **The inert packet** (`ExaminationPacket` + `Observation`) — a frozen,
   content-addressed set of static observations (the kind of thing a capture
   *would* record: a rendered text snapshot, a DOM/text snapshot, response
   headers, certificate/registration metadata, content hashes, capture timestamp
   + provenance). Content-addressed via the existing `ledger.blobs`. Contains
   NOTHING executable and nothing that requires a live re-fetch to interpret.

2. **The trust-gated CAPTURE operator** (`CaptureGate` + `capture_packet`) — a
   privileged, opt-in operation mirroring the contribute-layer opt-in/consent +
   fail-closed gating posture. A node may PRODUCE a packet only after it has been
   granted the capture role; an ungranted node is REFUSED (fail-closed). Each
   capture appends a `PACKET_CAPTURED` entry to the SAME append-only transparency
   log (new `KIND_*`, following the existing pattern). Grant/revoke of the capture
   role are logged too (`CAPTURE_ROLE_GRANTED` / `CAPTURE_ROLE_REVOKED`).

3. **The open analysis loader** (`load_packet_for_analysis` -> `AnalysisView`) —
   anyone (no gate) may load a captured packet BY ITS CONTENT KEY and get an
   `AnalysisView` that exposes ONLY the frozen observations + an opaque
   `target_ref`. The view carries NO live locator (no URL) and NO fetch method, so
   "re-visit the live target" is not expressible from an analysis view. Analysis
   is the ONLY consumer of the frozen artifact.

The CAPTURE implementation in this PR is a **deterministic, offline
`StaticDocumentCapturePort`** that reads a bundled local fixture (a synthetic
document) and emits inert observations. The real headless-browser / IP-masked
capture port is a deliberately deferred, separately-security-reviewed later wave
(see §8). The `CapturePort` protocol is the seam that wave will implement.

---

## 2. File layout

```
src/cairn/capture/__init__.py     NEW  package docstring + re-exports.
src/cairn/capture/packet.py       NEW  Observation + ExaminationPacket + AnalysisView
                                       (the inert artifact + the analyst-facing view).
src/cairn/capture/port.py         NEW  CapturePort protocol + StaticDocumentCapturePort
                                       (deterministic offline fixture-reader).
src/cairn/capture/gate.py         NEW  CaptureGate: grant/revoke/has the capture role,
                                       persisted over ledger.blobs, logged to translog.
src/cairn/capture/store.py        NEW  capture_packet(...) (gated produce -> persist
                                       -> log) + load_packet_for_analysis(...) (open
                                       load -> AnalysisView).

src/cairn/ledger/translog.py      EDIT add KIND_PACKET_CAPTURED,
                                       KIND_CAPTURE_ROLE_GRANTED,
                                       KIND_CAPTURE_ROLE_REVOKED (same chain).
src/cairn/ledger/__init__.py      EDIT export the new kinds.

src/cairn/fixtures/capture_target_benign.json   NEW  the synthetic static document
                                       a capture "renders": title + body text +
                                       synthetic response headers + synthetic
                                       registration metadata. LOCAL; no URL fetched.
pyproject.toml                    EDIT force-include the new fixture in the wheel.

tests/test_capture_packet.py      NEW  inert-by-construction + content-address props.
tests/test_capture_gate.py        NEW  fail-closed grant/revoke + logging.
tests/test_capture_store.py       NEW  gated capture + open load + AnalysisView shape.
tests/test_capture_e2e.py         NEW  OUTCOME-ALTITUDE end-to-end on a fresh ledger.
```

No CLI command is added in this PR (the capture role is an operator primitive, not
a contributor self-serve command yet; a `cairn capture` CLI is a later wave once
the real port exists). The abstraction is exercised end-to-end via the library
entry points `capture_packet` / `load_packet_for_analysis`.

---

## 3. The inert-packet schema (structurally forbids live re-fetch)

`Observation` (frozen dataclass): one static datum a capture recorded.
  - `kind: str` — an observation kind from a fixed vocabulary
    (`RENDERED_TEXT`, `DOM_TEXT`, `RESPONSE_HEADERS`, `REGISTRATION_METADATA`,
    `CONTENT_HASH`). NOT executable; descriptive only.
  - `content: dict` — the captured static datum (already-recorded bytes-as-text /
    header map / metadata map / hash). JSON-serializable; no code, no callables.
  - `content_hash: str` — sha256 of the canonical-JSON of `content` (self-attesting
    integrity of this observation; lets the analyst confirm nothing was altered).

`ExaminationPacket` (frozen dataclass): the whole inert bundle.
  - `target_ref: str` — an OPAQUE label/identifier for what was captured (e.g. a
    fixture id or a content-address). It is NOT a live locator and is NOT a URL;
    it cannot be dereferenced to reach a live target. (The schema deliberately has
    NO `url` / `locator` / `endpoint` field — see the structural argument below.)
  - `cause_id: Optional[str]` — the cause this packet belongs to, if any (reuse the
    cause layer where a bundle belongs to a cause).
  - `observations: tuple[Observation, ...]` — the frozen set of static observations.
  - `captured_at: float` — the capture timestamp (provenance).
  - `captured_by: str` — the capturing operator's node id (provenance).
  - `capture_method: str` — a provenance label for HOW it was captured (here,
    `static-document-fixture`; a real wave stamps its own method).
  - `packet_hash: str` — sha256 of the canonical-JSON of the immutable fields
    (target_ref + cause_id + observations + captured_at + captured_by +
    capture_method). This is the bundle's content address; identical capture input
    yields the identical packet_hash (dedup + tamper-evidence, mirroring §3.6).

`AnalysisView` (frozen dataclass): the analyst-facing projection of a packet.
  - exposes `packet_hash`, `target_ref` (opaque), `cause_id`, `captured_at`,
    `captured_by`, `capture_method`, and `observations` (read-only).
  - exposes a `rendered_text()` / `observations_of_kind(kind)` convenience for
    reading the captured static content.
  - exposes NO live locator and NO `fetch` / `refetch` / `open` / `visit` method.

**Why this structurally forbids "re-visit the live target":** the only inputs an
analyst receives are (a) the `ExaminationPacket` / `AnalysisView`, whose fields are
ALL static recorded data, and (b) NO field on either object is a dereferenceable
live locator — there is no URL, no endpoint, no socket, no fetch callable anywhere
on the analysis path. `target_ref` is an opaque content-address/label by
construction (the capture port never writes a live URL into it; the static-document
port writes the fixture id). To analyze, the analyst can ONLY read the frozen
observations. "Re-visit the live target" is therefore not an expressible operation
on the analysis side — it is excluded by the absence of any locator/fetch surface,
not merely by policy. A test asserts the negative: no attribute of `AnalysisView`
(or `ExaminationPacket`) is callable-as-a-fetch and none names a URL/locator, and
the observation `content` values are plain JSON (no callables).

---

## 4. The trust-gated capture role (fail-closed)

`CaptureGate(ledger)` — mirrors `OptInRegistry`'s posture (persist over
`ledger.blobs`, log to the same translog, fail-closed):
  - `grant(node_id, granted_by, scope_summary) -> CaptureGrant` — records an
    ACTIVE grant of the capture role to `node_id`; persists it; appends
    `CAPTURE_ROLE_GRANTED`. `scope_summary` is the human-readable description of
    what this operator is permitted to capture (informed, like `agreed_summary`).
  - `revoke(node_id) -> CaptureGrant` — flips the grant inactive; appends
    `CAPTURE_ROLE_REVOKED`. Raises if there is nothing to revoke.
  - `is_granted(node_id) -> bool` — True iff an ACTIVE grant exists. Default for an
    unknown node is False (FAIL CLOSED).
  - `get_grant(node_id) -> Optional[CaptureGrant]`.

`CaptureGrant` (frozen dataclass): node_id + granted_by + scope_summary +
granted_at + active; to/from_dict (mirrors `ConsentRecord`).

The asymmetry the objective demands: **producing** a packet is gated (privileged);
**analyzing** a packet is open (no gate). `capture_packet` enforces the gate;
`load_packet_for_analysis` does not.

---

## 5. capture + load flow

`capture_packet(port, *, gate, ledger, node_id, cause_id=None, scope=None)
-> ExaminationPacket`:
  1. **Fail-closed gate**: raise `CaptureRefused` if `not gate.is_granted(node_id)`
     (an ungranted node cannot capture — the privileged-role gate, demand side).
  2. `observations = port.capture()` — the deterministic port reads its local
     fixture and returns inert `Observation`s. (No network; no browser.)
  3. Build the `ExaminationPacket` (stamp `captured_at` from `ledger._clock`,
     `captured_by=node_id`, `capture_method=port.method`, `target_ref=port.target_ref`,
     `cause_id`); compute `packet_hash`.
  4. Persist the packet's canonical-JSON via `ledger.blobs.put_json(...)` (the
     content key equals `packet_hash` by construction — see §3); index it under
     `<root>/packets/<packet_hash>`.
  5. Append a `PACKET_CAPTURED` translog entry (packet_hash + target_ref + cause_id
     + captured_by + capture_method + observation_count). Auditable on the same
     chain as detection + cause governance.
  6. Return the `ExaminationPacket`.

`load_packet_for_analysis(packet_hash, *, ledger) -> AnalysisView`:
  - OPEN (no gate). Reads the packet blob by its content key from `ledger.blobs`,
    reconstructs the `ExaminationPacket`, and returns an `AnalysisView` over it.
  - Raises `PacketNotFound` if the content key is absent.
  - The returned view is the ONLY thing analysis consumes — it never touches a live
    target (there is no live-target surface to touch; §3).

---

## 6. named acceptance criteria (ODD §2.5 — every line maps to one)

- **AC.CAP.1 (inert schema).** `ExaminationPacket` + `Observation` hold only static,
  JSON-serializable data; no field is a callable/locator/URL. `packet_hash` /
  `content_hash` are sha256 content-addresses. *Tested:* `test_capture_packet.py`
  — round-trip to/from_dict; packet_hash stable + equals the blob content key;
  every observation content value is plain JSON; no attribute names a URL/locator.

- **AC.CAP.2 (inert-by-construction / no re-fetch surface).** Neither
  `ExaminationPacket` nor `AnalysisView` exposes any live-fetch surface: no
  attribute is a URL/locator field, and no method fetches/visits/opens a live
  target. *Tested:* `test_capture_packet.py` — assert the negative over the public
  attribute/method surface of both types.

- **AC.CAP.3 (fail-closed capture gate).** `capture_packet` raises `CaptureRefused`
  when the node is not granted; succeeds after `grant`; `revoke` then re-refuses.
  Grant/revoke log `CAPTURE_ROLE_GRANTED` / `CAPTURE_ROLE_REVOKED`; the log still
  passes `verify_log`. *Tested:* `test_capture_gate.py`, `test_capture_store.py`.

- **AC.CAP.4 (capture composes on ledger + translog).** A captured packet is
  content-addressed in `ledger.blobs` (content key == packet_hash) and a
  `PACKET_CAPTURED` entry is appended to the SAME transparency log. *Tested:*
  `test_capture_store.py` — blob present at packet_hash; translog has
  `PACKET_CAPTURED`; `verify_log` ok.

- **AC.CAP.5 (open analysis loads ONLY the packet).** `load_packet_for_analysis`
  needs NO gate, returns an `AnalysisView`, and the analyst can read the captured
  observations + reach a judgement (a deterministic example judge over the rendered
  text) from the view ALONE — with no live-target access available. `PacketNotFound`
  on an unknown key. *Tested:* `test_capture_store.py`, `test_capture_e2e.py`.

- **AC.CAP.6 (OUTCOME-ALTITUDE, real entry point, fresh ledger).** On a FRESH
  `Ledger` with NO pre-arranged state: grant the capture role -> `capture_packet`
  via the `StaticDocumentCapturePort` -> the inert packet is persisted + a
  `PACKET_CAPTURED` entry is logged -> a SECOND actor with ONLY the packet_hash
  calls `load_packet_for_analysis` and judges the packet from the view alone ->
  `verify_log` over the produced log is ok. The analyst code path is handed ONLY
  the packet_hash + the ledger blob store; it is given NO target_ref-as-URL, NO
  port, NO live handle. *Tested:* `test_capture_e2e.py` (drives the real entry
  points end-to-end; this is the outcome-altitude AC).

(Marked outcome-altitude: **AC.CAP.6** — verified by a test invoking the real
`capture_packet` + `load_packet_for_analysis` entry points on a fresh ledger with
no pre-arranged state, exercising capture -> inert bundle persisted + logged ->
analyst loads ONLY the bundle and judges it.)

---

## 7. test list

`test_capture_packet.py` (AC.CAP.1, AC.CAP.2):
- Observation/Packet to/from_dict round-trip; content_hash + packet_hash are
  deterministic sha256s; packet_hash == the blob content key.
- inert-by-construction: no public attribute of `ExaminationPacket`/`AnalysisView`
  names a URL/locator; no public method fetches/visits/refetches; observation
  `content` values are plain JSON (str/bool/int/float/None/list/dict only).

`test_capture_gate.py` (AC.CAP.3):
- ungranted node `is_granted` False (fail closed); grant -> True + logged; revoke
  -> False + logged; the log passes `verify_log`.

`test_capture_store.py` (AC.CAP.3, AC.CAP.4, AC.CAP.5):
- `capture_packet` REFUSED (CaptureRefused) for an ungranted node; SUCCEEDS after
  grant; the packet is content-addressed in `ledger.blobs` at packet_hash;
  `PACKET_CAPTURED` is on the log; `verify_log` ok.
- `load_packet_for_analysis` (no gate) returns an `AnalysisView`; `PacketNotFound`
  on an unknown key; a deterministic example judge reads the view's rendered text
  and reaches a verdict from the view alone.

`test_capture_e2e.py` (AC.CAP.6 — OUTCOME-ALTITUDE):
- fresh ledger, no pre-arranged state: grant -> capture -> the analyst (handed ONLY
  packet_hash + ledger) loads + judges -> `verify_log` ok.

Keep the existing suite green (no change to any existing public behaviour; only
additive `KIND_*` constants + a new package).

---

## 8. deferrals (STOP here — later, separately-security-reviewed PRs)

- **Real headless-browser / real-network / IP-masked capture port** — the
  `CapturePort` protocol is the seam; the ONLY implementation here is the
  deterministic offline `StaticDocumentCapturePort` reading a local fixture. Real
  browser-driving + real egress is a deliberately deferred, separately
  security-reviewed wave. HARD scope boundary.
- A `cairn capture` CLI command (operator primitive; deferred until the real port
  exists).
- Screenshot/image observations as real rendered pixels (here, a synthetic
  `RENDERED_TEXT` stands in; no real renderer).
- Packet retention / GC / redaction policy, multi-packet bundling, federation.
- Any scam/phishing/sensitive capture target (mission-specific; sensitive waves).

---

## 9. constraints honored

- Composes on the engine (`ledger.blobs` content-addressing + `TransparencyLog` +
  `verify_log`) and reuses the cause layer (`cause_id` on a packet) + the
  contribute layer's opt-in/consent gating POSTURE — forks nothing.
- Mission-NEUTRAL: the only worked example captures a synthetic LOCAL document; NO
  real URL fetched, NO real browser, NO network egress, NO sensitive content.
- Inert-by-construction: the packet is frozen static data with no executable
  content and no live-locator/fetch surface; "analyze without re-visiting" is the
  only expressible analysis path (§3).
- Trust-gated capture (fail-closed) vs OPEN analysis — the demanded asymmetry.
- Every new module/branch/test traces to a named AC (§6); ≥1 outcome-altitude AC
  (AC.CAP.6) with a real-entry-point fresh-ledger test.
- Branch + PR only; never main; do not merge.
