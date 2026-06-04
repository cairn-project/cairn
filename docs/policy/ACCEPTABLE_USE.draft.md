# Acceptable-Cause / Prohibited-Target Policy — DRAFT

> **STATUS: DRAFT — pending owner ratification. NOT yet adopted policy.**
>
> This document is a **strawman for the maintainer (and, where flagged, qualified
> counsel and a trust-and-safety professional) to ratify, amend, or reject.** It
> is written to the *edge of the decisions* and no further: every place that
> requires a human judgement call is marked **[OWNER DECISION]** or **[COUNSEL]**.
> Until the maintainer ratifies it and removes this banner, the
> acceptable-cause / prohibited-target policy referenced by
> [GOVERNANCE.md](../../GOVERNANCE.md) remains **OPEN** and no non-benign cause
> should be approved.
>
> **This is not legal advice.** Every legal characterisation below is
> issue-spotting to prepare the maintainer and qualified advisors. None of it is
> settled advice that can be relied on without a qualified attorney and a
> trust-and-safety professional. The lines marked **[COUNSEL]** are the ones that
> genuinely require professional sign-off before they bind anything.

---

## 0. Why this policy exists (the gap it closes)

Cairn is **mission-neutral by design**: the engine hard-codes no opinion about
what a cause targets. The conduct a cause watches for is free-text the requester
fills, and the only barrier today is a single (unauthenticated, single-actor-
capable) human cause-vetter — see the
[README gate-guarantee note](../../README.md) and
[GOVERNANCE.md](../../GOVERNANCE.md).

Mission-neutrality is a *trust property of the engine*. It is **not** a licence
for the project to coordinate arbitrary causes. A general engine pointed at the
wrong target is exactly how a safety tool becomes a harassment, surveillance, or
persecution tool. This policy is the written bar a cause must clear before any
human vetter may approve it — the governance layer that mission-neutrality
deliberately leaves to people rather than to code.

**Relationship to the engine:** this policy governs *which causes the project
will run*; it does not change the engine's behaviour. The engine stays
mission-neutral; this document constrains the humans who operate it.

---

## 1. In-scope cause categories (narrow, on purpose)

A cause is a **candidate** for approval only if it falls within one of these
categories. Being in-scope is necessary, not sufficient — every cause must also
clear the §4 acceptance bar and avoid every §2 prohibition.

The starter set below is adapted from the project's online-harms research; the
maintainer must ratify the final list.

1. **CSAM presence — location/pointer detection only.** Detect *where* likely
   child-sexual-abuse material is, route a pointer + context to an authorized
   assessor (a platform's own reporting pipeline, NCMEC's CyberTipline, or an
   IWF/INHOPE-equivalent). **Never handle, view, store, hash-from-original, or
   transmit the content itself.** [COUNSEL — see §3.1]
2. **Child grooming / enticement patterns — passive behavioural detection.**
   Surface a behavioural pattern to a platform or NCMEC; **never engage the
   target, never pose as a child, never run a sting.** [COUNSEL — see §3.2]
3. **Suicide-method *vendor / forum* operations.** Detect the commercial or
   criminal *seller-side* pattern and route it to platforms + law enforcement.
   **No individual-facing intervention** — Cairn is not a crisis service.
   [COUNSEL + clinical advisor — see §3.3]
4. **[OWNER DECISION — candidate, advisor-gated] Credible imminent
   physical-harm threats** (mass-violence / terror), routed to authorities. This
   one is a *candidate* in the research strawman, explicitly flagged as needing
   advisor sign-off before inclusion. Decide: include now, defer, or drop.

> **[OWNER DECISION 1.A]** Ratify the in-scope list. For each of categories 1–4:
> **in / deferred / out**. The recommendation from the research is 1–3 in,
> 4 deferred-until-advisor.

> **[OWNER DECISION 1.B]** Should the *launch* scope be even narrower than the
> ratified policy scope? The currently shipped, runnable cause is the **benign
> OSS-license-classification pilot**, which touches none of categories 1–4. A
> defensible posture is: ratify the full policy now, but state that **no
> category-1–4 cause will be approved until the §4 acceptance bar's preconditions
> exist** (an authorized recipient who will accept the signal, plus counsel and a
> T&S advisor on the design — see §3 and §5). Decide: launch scope = benign-pilot
> only, or benign-pilot + a named first real category.

---

## 2. Categorically out-of-bounds (permanent — not a tunable setting)

These are **permanent prohibitions**. A cause that touches any of them is
declined regardless of code quality, requester, or stated good intent. They are
written as a hard contract precisely so they cannot be quietly relaxed later.

- **Any political, religious, ethnic, national-origin, sexual-orientation,
  gender-identity, or other protected-class "targeting."** This is the
  scope-creep path that turns a safety tool into an instrument of persecution. A
  permanent prohibition, never a setting.
- **Lawful-but-disfavoured speech, dissent, or "undesirable" groups.** Cairn is
  not a censorship engine. (Human-rights baseline: the Santa Clara Principles.)
- **Any *content handling* of CSAM** — view, store, transmit, or hash-from-
  original. Per-se illegal for a private party even with detection intent.
  [COUNSEL — §3.1]
- **Any *active engagement* with targets** — posing as a child, running stings,
  DMing individuals. Pollutes prosecutions and reproduces documented
  vigilante-failure modes. [COUNSEL — §3.2]
- **Any *individual crisis intervention*** without a credentialed clinical
  partner. Duty-of-care and harm-increase risk. [COUNSEL + clinical advisor —
  §3.3]
- **Any *public* accusation or naming of a target.** Defamation exposure plus
  mob / vigilante action. Reports go privately to authorized bodies only.
- **Self-serve / uncredentialed "report this person" surfaces.** This is the
  harassment-weaponization vector — no surface that lets an arbitrary user get a
  named person reported.

> **[OWNER DECISION 2.A]** Ratify the out-of-bounds list verbatim, or amend.
> The research treats every item here as load-bearing; weakening any one of them
> is a substantive safety decision, not an editorial one.

> **[OWNER DECISION 2.B]** Change-control: should *adding* an in-scope category
> require sign-off from the (not-yet-existing) advisory board, and *removing* an
> out-of-bounds item require the same plus counsel? Recommended: yes to both,
> recorded in this doc's change log.

---

## 3. The legal lines (issue-spotting → counsel; NOT advice)

> Everything in this section is for issue-spotting with a qualified attorney and
> a trust-and-safety professional. **None of it is advice the maintainer can rely
> on.** These are the specific lines that need professional sign-off before any
> category-1–4 cause is approved.

### 3.1 CSAM — the load-bearing rule [COUNSEL]
Handling CSAM (possess / receive / transmit / hash-from-original / view) is, in
practice, a **strict-liability federal crime for a private party even with
detection intent** — "I was trying to catch it" is not a recognised defence. The
organisations that lawfully assess this content (NCMEC, IWF) hold *specific
statutory authority* the project does not and cannot improvise. **The only
lawful and sane architecture is detect-the-location, route-a-pointer-to-an-
authorized-body, and stop — no human, no volunteer, and no model on Cairn's side
ever touches the content.** This same invariant is *also* what protects every
model in the pipeline from the worst material. **[COUNSEL must confirm the
precise mens rea, whether any narrow exception could apply, and exactly what
Cairn may lawfully store as a "pointer." Do not assume any exception applies.]**

### 3.2 Grooming / enticement — passive-only [COUNSEL]
The detection-vs-entrapment/vigilantism line is where this work gets innocent
people falsely accused or gets prosecutions thrown out. Private "predator-hunter"
stings routinely backfire (chain-of-custody problems, two-party-consent recording
violations, entrapment exposure when anyone on Cairn's side *initiates or
escalates* contact). **Structural rule: Cairn is a passive detector + reporter,
never an active participant.** **[COUNSEL must confirm the passive/active line
and the recording-law exposure for whatever Cairn observes.]**

### 3.3 Suicide-method vendors — vendor-side only [COUNSEL + clinical advisor]
Flagging a *vendor / forum* (a commercial or criminal actor selling lethal
methods) to platforms + law enforcement is the in-scope action. **Intervening
with a vulnerable *individual* is clinical crisis-response work the project is
not equipped for** and a botched automated intervention could increase harm and
create liability. **Structural rule: report the vendor-side pattern; never DM
at-risk individuals.** Any individual-facing element is a separate, later,
expert-gated workstream designed *with* crisis professionals. **[COUNSEL +
clinical advisor required before any individual-facing element exists.]**

### 3.4 Cross-cutting exposure [COUNSEL]
Named here so it is visible, not discovered: **defamation / false-light** (every
accusation is a factual claim about a person — guard: never publish, report
privately only); **false-reporting / swatting-adjacent liability** (a negligent
pipeline that floods authorities with false reports is a legal and ethical
catastrophe — guard: human-in-the-loop before any law-enforcement-bound report,
optimise for report *quality* not volume); **surveillance / privacy / wiretap law**
(scraping + monitoring implicates two-party-consent statutes, ECPA, CFAA, state
privacy/biometric law — scope of what Cairn may lawfully observe and retain is a
primary legal question); **Section 230** (does not shield the underlying federal
crimes Cairn targets, and its protection for *Cairn itself* depends on Cairn's
exact role); **jurisdiction** (harms are global, reporting destinations are
national). **[Every line in this paragraph requires counsel before any live,
non-benign cause.]**

---

## 4. The acceptance bar — what a cause must clear before a vetter may approve it

A candidate cause is acceptable **only if all of the following hold**. This is
the bar a human cause-vetter checks against; it composes with, but is stricter
than, the engine's existing five-frame gate (`works` / `doesnt_target_good_people`
/ `legal` / `court_grade_auditable` / `human_verified`).

1. It targets an **illegal harm** with a **legally-authorized recipient** who
   will actually action the signal. (No recipient → no cause.)
2. It can be served by **passive detection + routing** with **no content-
   handling, no engagement, and no intervention**.
3. It passes a **human-rights / misuse review** against the known attack vectors
   (false-reports-as-harassment, false positives, vigilante action, model
   manipulation, surveillance overreach, scope creep, authority-laundering,
   over-volume-harms-the-system).
4. It touches **none** of the §2 prohibitions.
5. It has a **measurable false-positive discipline** — Cairn's output is
   *prioritized, confidence-scored signal*, never a verdict.

> **[OWNER DECISION 4.A]** Ratify the five-part bar, or amend. Note that bar (1)
> ("an authorized recipient who will actually action the signal") is the one that
> *gates real launch* — today there is no such accepted-feeder relationship, so
> under this bar no category-1–3 cause is yet approvable. That is the honest
> state, and it is by design (see §5).

---

## 5. Who decides a cause is acceptable, and against what bar

> **[OWNER DECISION 5.A — the central governance call]**

The research strawman proposes the decision body should be an **independent
advisory board** (legal counsel + a T&S professional + a child-safety-org
representative + a civil-liberties / human-rights voice + ideally an
ex-law-enforcement / NCMEC-adjacent person) — **not the maintainer alone.**

This is in direct tension with the current GOVERNANCE.md, which states the
project is **single-maintainer** with "final authority over the project's
direction." That tension is real and the maintainer must resolve it explicitly:

- **Option A — single-maintainer for now, board-gated for non-benign causes.**
  The maintainer ratifies this policy and approves only the benign pilot alone;
  *any* category-1–4 cause is blocked until an advisory board exists to co-decide
  it. Keeps GOVERNANCE.md honest (single maintainer today) while making the board
  a hard precondition for the dangerous surface.
- **Option B — board required before any real cause, full stop.** No
  category-1–4 cause is approvable until the board is stood up. Most
  conservative; matches the field's own gate (vetting + governance + audit).
- **Option C — maintainer-alone decides, documented.** Fastest, and the
  research explicitly argues *against* it for this domain ("nobody will — or
  should — trust some guy" in the most legally-radioactive corner of
  trust-and-safety). Named here only for completeness; not recommended.

> **[OWNER DECISION 5.A]** Pick A / B / C (or define a fourth). Recommendation
> from the research: effectively A — single-maintainer governance for the benign
> pilot, with an advisory board as a hard precondition before any sensitive
> cause, because a solo unknown builder is not credible in this field without
> governance + audit, and shouldn't be.

> **[OWNER DECISION 5.B]** Does the maintainer commit to the staged credibility
> path before any sensitive cause runs: (0) counsel + one T&S advisor audit the
> never-touch design *before* building sensitive parts; (1) one narrow harm with
> an authorized recipient, proven on report *quality*; (2) advisory board +
> published framework + independent error-rate audit; (3) only then an
> institutional partnership? This is a sequencing commitment, not a code change.

---

## 6. The invariants (always true, no exceptions)

These hold for every cause the project will ever run. They are the non-negotiable
floor under §1–§5.

1. **Never-touch-the-content.** No human, volunteer, or model on Cairn's side
   accesses suspected CSAM (or equivalent per-se-illegal content). Pointers +
   context only; assessment is the authorized body's job. *This is also the
   model-welfare invariant — the same design move protects every model in the
   pipeline from the worst material.*
2. **Route-to-authorities, never act.** Cairn produces *prioritized signal for
   authorized recipients*; it never enforces, publishes, engages, or intervenes.
3. **Human-in-the-loop before consequence.** No automated path from a Cairn flag
   to a real-world consequence against a person without authorized human
   verification.
4. **Signal, not verdict.** Cairn's output is always a confidence-scored lead,
   never a determination of guilt.

> **[OWNER DECISION 6.A]** Ratify the four invariants as the permanent floor.
> The research treats these as non-negotiable; amending one is a foundational
> safety decision.

---

## THE DECISIONS THE OWNER MUST MAKE (summary — this is the ratification checklist)

1. **[1.A]** Ratify the in-scope category list (1–4: in / deferred / out each).
   *Recommended: 1–3 in, 4 deferred-until-advisor.*
2. **[1.B]** Launch scope: benign-pilot-only, or benign-pilot + one named first
   real category. *Recommended: benign-pilot-only until §4 preconditions exist.*
3. **[2.A]** Ratify the out-of-bounds list verbatim, or amend.
4. **[2.B]** Change-control: board sign-off to add a category / board + counsel
   to remove a prohibition? *Recommended: yes to both.*
5. **[4.A]** Ratify the five-part acceptance bar, or amend. (Note bar 1 gates
   real launch — no authorized recipient yet exists.)
6. **[5.A]** *The central call:* who decides a cause is acceptable —
   single-maintainer-for-benign-only + board-gated-for-sensitive (A) / board
   required before any real cause (B) / maintainer-alone (C, not recommended)?
7. **[5.B]** Commit to the staged credibility path (counsel-audit → narrow tool →
   board + audit → partnership) before any sensitive cause? Y/N.
8. **[6.A]** Ratify the four invariants as the permanent floor.
9. **[COUNSEL gates]** Engage qualified counsel (+ a T&S advisor, + a clinical
   advisor for category 3) to sign off every line marked **[COUNSEL]** in §3
   before *any* category-1–4 cause is approved. The strawman flags *where*
   counsel is needed; it does not and cannot supply legal certainty.

---

## Change log

- *DRAFT created — pending owner ratification. Adapted from the project's
  online-harms research strawman to the repo's mission-neutral framing.*
