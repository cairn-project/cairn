# Contributor Privacy & Consent Notice — DRAFT

> **STATUS: DRAFT — pending owner ratification. NOT yet adopted policy.**
>
> This is a **strawman for the maintainer (and, where flagged, counsel) to
> ratify, amend, or reject.** It describes what data a contributor shares with
> Cairn, how it is used, and the terms of their opt-in — and proposes a more
> structured consent shape than the current free-text field. Every judgement call
> is marked **[OWNER DECISION]**; every line needing professional sign-off is
> marked **[COUNSEL]**.
>
> **This is not legal advice and it is not yet a privacy policy.** A real privacy
> notice that binds the project needs counsel review before publication,
> especially if any contributor is in a jurisdiction with statutory data-
> protection requirements (GDPR / UK GDPR / CCPA).

---

## 0. What this covers

A **contributor** lends their own AI capacity to a cause. To do so they record an
explicit, revocable **opt-in** (`ConsentRecord`). This notice states, in plain
terms, what that opt-in involves and what the project does with the data it
generates.

It is grounded in the engine as actually built (verified against
`src/cairn/contribute/`): consent is **explicit, gated, and revocable**, opt-in
to a non-listable cause is **refused**, and every opt-in / revoke is appended to
the same append-only transparency log (`CONSENT_RECORDED` / `CONSENT_REVOKED`).

---

## 1. What data a contributor shares (as built today)

The current `ConsentRecord` (`src/cairn/contribute/model.py`) captures exactly
five fields:

| Field | What it is | Sensitivity |
|---|---|---|
| `node_id` | A caller-supplied string identifying the contributing node. **Unauthenticated free-text** — it is whatever the contributor passes; the engine does not verify or link it to a real identity. | Low *as built* (no real identity required), but a contributor **may** put identifying info here — see §3. |
| `cause_id` | Which cause the contributor opted into. | Low. |
| `agreed_summary` | Human-readable text describing what the node's AI will do for this cause — the informed-consent record. | The consent content itself. |
| `consented_at` | Timestamp of consent. | Low. |
| `active` | Whether the consent is live (`True`) or revoked (`False`). Revoked records are **kept** for the audit trail, not deleted. | Low. |

**What Cairn does *not* collect today (important and honest):** there is no
account system, no email, no authentication, no IP logging, no payment data, no
device fingerprint. A contributor is a free-text `node_id` and a consent record.
The work a node does flows into the ledger as results/verdicts, not as
contributor personal data.

> **[OWNER DECISION 1.A]** Confirm this inventory is complete and accurate, or
> name any additional data a deployment collects (e.g., if a future hosted
> deployment adds accounts, email, or IP logging, this table must grow *before*
> that deployment).

---

## 2. How the data is used

- **`agreed_summary`** is the basis of consent — it documents what the
  contributor agreed their AI would do, so consent is *informed* and *auditable*.
- **All five fields** are appended to the append-only transparency log so that
  consent (and its revocation) is independently verifiable — the same
  tamper-evidence that covers the rest of the engine covers consent.
- The data is **not** sold, shared with third parties, or used for any purpose
  beyond running and auditing the contributor's participation in their chosen
  cause.

> **[OWNER DECISION 2.A]** Ratify the use limitation ("not sold / not shared /
> used only for the cause + audit"), or amend. *Recommended: keep it tight —
> minimal collection + minimal use is a trust property, not just a courtesy.*

---

## 3. The append-only-log privacy tension (honest disclosure — read this)

The transparency log is **append-only and hash-chained**: a `CONSENT_RECORDED`
entry **cannot be edited or deleted** without breaking the chain. This is a
deliberate integrity property — but it has a real privacy consequence:

- **A contributor's `node_id` and `agreed_summary` are permanent on the log.**
  Revoking consent flips `active` to `False` and appends a `CONSENT_REVOKED`
  entry; it does **not** erase the original record.
- If a contributor puts **identifying information** into `node_id` or
  `agreed_summary`, that information is permanent and tamper-evident by design.
- This creates a genuine tension with any **right-to-erasure** regime (e.g. GDPR
  Art. 17): an append-only log and a delete-my-data right are structurally at
  odds. **[COUNSEL]**

**Mitigations to decide between (not yet implemented — proposed):**
- **Guidance-only:** tell contributors plainly "do not put personal information
  in `node_id`; use a pseudonymous handle" — cheap, immediate, no code change.
- **Pseudonymous-by-construction:** the consent surface accepts only an opaque
  handle and never a real identifier; identifying fields are structurally absent.
- **Redaction-at-read:** keep the chain intact but redact personal fields from
  *public* views (the public surfaces are already redacted-by-construction; this
  would extend the discipline to consent records). Erasure-of-meaning without
  erasure-of-entry.

> **[OWNER DECISION 3.A]** Pick a stance on the append-only-vs-erasure tension:
> guidance-only / pseudonymous-by-construction / redaction-at-read / defer with a
> named-deferral note. **[COUNSEL must confirm** whether the chosen stance is
> sufficient for any data-protection regime that applies to the project's actual
> contributor base.**]** *Recommended: guidance-only now + pseudonymous-by-
> construction as the design target, with the erasure question explicitly flagged
> for counsel before any deployment that could attract EU/UK contributors.*

---

## 4. Proposed structured-consent shape (not wired — a design proposal)

Today `agreed_summary` is a single free-text string. Free-text consent is hard to
audit consistently and easy to make vague. The research (red-team item) suggests a
**structured** consent shape would build recruit trust at low cost. This is a
**proposal only — not implemented, not wired into the engine.**

Proposed additional structured fields alongside the existing `agreed_summary`:

| Proposed field | Purpose |
|---|---|
| `scope_of_work` (enum/text) | What the node's AI will and won't do (e.g. "classify license text against a contract"); bounds the work explicitly. |
| `data_seen` (text) | What kind of material the node's AI may be exposed to. **For any sensitive cause this must affirm the never-touch-content invariant** — i.e. the node never sees raw harmful content, only pointers/metadata. |
| `revocable` (bool, default true) | Restates that consent can be withdrawn at any time and how. |
| `policy_version` (string) | Which version of the acceptable-use policy + this notice the contributor consented under, so consent is anchored to a known policy state. |
| `consent_text_ack` (bool) | An explicit acknowledgement that the contributor read this notice. |

> **[OWNER DECISION 4.A]** Should the project adopt a structured consent shape
> (a) now, (b) before the first non-benign cause, or (c) not at all (keep
> free-text)? *Recommended: (b) — free-text is fine for the benign pilot;
> structured consent should land before any sensitive cause, when `data_seen`'s
> never-touch affirmation actually matters.*

> **[OWNER DECISION 4.B]** If adopting structured consent, is this the right
> field set, or should it add/remove fields? This is a design ratification, and
> implementing it is a **separate Bucket-A code task** (schema + opt-in surface +
> test) — not done here.

---

## 5. Contributor rights (proposed terms)

- **Opt-in is explicit and never silent.** No node is enlisted without recording
  a `ConsentRecord`. *(True as built.)*
- **Opt-in is gated.** A contributor cannot opt into a non-approved / non-listable
  cause; the engine refuses it. *(True as built — verified `OPT-IN REFUSED`.)*
- **Consent is revocable at any time.** Revocation flips the record to inactive
  and is itself logged. *(True as built; see §3 for the erasure caveat.)*
- **[PROPOSED] Contributors are told, before opting in, that the consent record
  is permanent on an append-only log** and are advised to use a pseudonymous
  handle (see §3).
- **[PROPOSED] Contributors consent under a named policy version** (§4) so a later
  policy change does not silently re-scope their participation.

> **[OWNER DECISION 5.A]** Ratify the rights list (the first three are already
> true in code; the last two are proposed additions).

---

## THE DECISIONS THE OWNER MUST MAKE (summary — ratification checklist)

1. **[1.A]** Confirm the data inventory is complete (and commit to growing it
   before any deployment that collects more, e.g. accounts/email/IP).
2. **[2.A]** Ratify the use limitation (not sold / not shared / cause + audit
   only).
3. **[3.A]** Pick the append-only-vs-erasure stance (guidance-only /
   pseudonymous-by-construction / redaction-at-read / defer). **[COUNSEL must
   confirm sufficiency for any applicable data-protection regime.]**
4. **[4.A]** Adopt structured consent now / before-first-sensitive-cause /
   never. *Recommended: before-first-sensitive-cause.*
5. **[4.B]** If adopting, ratify the proposed field set (implementation is a
   separate code task).
6. **[5.A]** Ratify the contributor-rights list.
7. **[COUNSEL]** Have counsel review this as a real privacy notice before it is
   published as binding, especially re: data-protection-regime applicability.

---

## Change log

- *DRAFT created — pending owner ratification. Grounded in `src/cairn/contribute/`
  as actually built; structured-consent shape is a proposal, not implemented.*
