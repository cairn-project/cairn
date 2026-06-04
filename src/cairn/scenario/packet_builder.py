"""Evidence-packet builder + the review-dump artefacts (assembly only).

Assembles the human-readable review artefacts for ONE flagged finding from the
REAL inputs: the captured (inert) evidence, the AI's analysis + the verify
verdict, the resolved REAL public reporting org (+ how it was found), and a DRAFT
submission the human would review before any real send. Pure assembly — no I/O,
no network, no model.

Every artefact carries the demonstration banner. The draft is explicitly framed
as a draft for review, never an outgoing message.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .org_finder import ResolvedOrg
from .seed import DEFECT_DESCRIPTIONS

#: The banner stamped on every dumped artefact + printed on every run.
REVIEW_BANNER = "FOR REVIEW — NOT SENT — demonstration scenario, not a live cause"


@dataclass(frozen=True)
class ReviewArtefacts:
    """The three review-dump artefacts for one finding (in-memory; pre-write)."""

    finding_hash: str
    packet_md: str
    packet_json: dict[str, Any]
    provenance_txt: str


def _evidence_lines(record: dict[str, Any], analysis: dict[str, Any]) -> list[str]:
    meta = record["registration_metadata"]
    lines = [
        f"- Dataset record: {record['dataset_title']} (catalogue record id: {record['record_id']})",
        f"- Steward: {record['steward_label']}",
        f"- Recorded download status: {meta.get('download_status')}",
        f"- Recorded license field: {meta.get('license_field')!r}",
    ]
    kind = analysis.get("defect_kind", "none")
    lines.append(f"- Observation: {DEFECT_DESCRIPTIONS.get(kind, kind)}")
    return lines


def build_review_artefacts(
    *,
    finding_hash: str,
    packet_hash: str,
    record: dict[str, Any],
    analysis: dict[str, Any],
    verdict_status: str,
    quorum_families: list[str],
    honeypot_passed: bool | None,
    resolved_org: ResolvedOrg | None,
    cause_id: str,
    provenance: dict[str, str],
    log_head: str,
) -> ReviewArtefacts:
    """Assemble the ``packet.md`` / ``packet.json`` / ``provenance.txt`` artefacts.

    ``resolved_org`` is ``None`` when the org finder failed closed; the packet then
    records "no public contact resolved; do not proceed" instead of a recipient,
    and carries no draft submission.
    """
    if resolved_org is not None:
        recipient_block = [
            "## Resolved reporting organization (REAL, public, non-person)",
            "",
            f"- Organization: {resolved_org.org_name}",
            f"- Public contact: {resolved_org.contact}",
            f"- How it was found: {resolved_org.source}",
        ]
        draft = (
            f"To: {resolved_org.contact} ({resolved_org.org_name})\n"
            f"Subject: Possible data-quality issue in catalogue record "
            f"'{record['record_id']}'\n\n"
            f"Hello,\n\n"
            f"This is a draft quality-report (FOR REVIEW — NOT SENT) about a public "
            f"open-data catalogue record, the dataset listing "
            f"'{record['dataset_title']}'. A routine check of the record's public "
            f"metadata suggests "
            f"{DEFECT_DESCRIPTIONS.get(analysis.get('defect_kind', 'none'))}. "
            f"This concerns the dataset listing only — not any individual. Could the "
            f"steward confirm and, if appropriate, correct the catalogue entry?\n\n"
            f"Thank you."
        )
        draft_block = ["## Draft submission (FOR REVIEW — NOT SENT)", "", "```", draft, "```"]
        recipient_json: dict[str, Any] = {
            "org_name": resolved_org.org_name,
            "contact": resolved_org.contact,
            "source": resolved_org.source,
            "is_public_org": resolved_org.is_public_org,
        }
        draft_json: str | None = draft
    else:
        recipient_block = [
            "## Resolved reporting organization",
            "",
            "- **No public contact resolved; do not proceed.** The reporting-org "
            "finder failed closed for this record (no verified public org inbox). "
            "A human must resolve a public contact before any action is considered.",
        ]
        draft_block = [
            "## Draft submission",
            "",
            "- (omitted — no recipient resolved; the finder fails closed rather "
            "than guess a recipient.)",
        ]
        recipient_json = {}
        draft_json = None

    hp = "n/a" if honeypot_passed is None else ("passed" if honeypot_passed else "FAILED")
    md_lines = [
        f"# {REVIEW_BANNER}",
        "",
        f"Cause: `{cause_id}` (a demonstration cause, not a live cause).",
        f"Finding: `{finding_hash}`  ·  Evidence packet: `{packet_hash}`",
        "",
        "## Captured evidence (inert; no live target was re-visited)",
        "",
        *_evidence_lines(record, analysis),
        "",
        "## AI analysis + verify verdict (REAL)",
        "",
        f"- Analysis output: `{json.dumps(analysis, sort_keys=True)}`",
        f"- Verify status: {verdict_status}",
        f"- Quorum model families: {', '.join(quorum_families) or '-'}",
        f"- Honeypot: {hp}",
        "",
        *recipient_block,
        "",
        *draft_block,
        "",
        "## Human review gate",
        "",
        "- This finding is **PENDING** in the real human-vetting gate (Gate 2) and "
        "is **not routable** until a human records a verdict.",
        "- Nothing has been sent. The scenario terminates at "
        "'human-vetted + dumped'; it has no egress code path.",
        "",
        f"_{REVIEW_BANNER}_",
    ]
    packet_md = "\n".join(md_lines) + "\n"

    packet_json = {
        "banner": REVIEW_BANNER,
        "cause_id": cause_id,
        "finding_hash": finding_hash,
        "packet_hash": packet_hash,
        "record_id": record["record_id"],
        "analysis": analysis,
        "verdict_status": verdict_status,
        "quorum_families": quorum_families,
        "honeypot_passed": honeypot_passed,
        "recipient": recipient_json,
        "draft_submission": draft_json,
        "is_demonstration": True,
        "sent": False,
    }

    prov_lines = [
        REVIEW_BANNER,
        "",
        "Real-vs-simulated ledger for THIS run:",
        f"  detection   : {provenance.get('detection', 'SIMULATED (seeded)')}",
        f"  analysis    : {provenance.get('analysis', 'REAL')}",
        f"  org-lookup  : {provenance.get('org_lookup', 'REAL (verified seed registry)')}",
        f"  vetting     : {provenance.get('vetting', 'REAL human Gate-2')}",
        f"  delivery    : {provenance.get('delivery', 'NONE — no egress code path')}",
        "",
        f"transparency-log head: {log_head}",
        "(independently checkable via `cairn verify-log <ledger>/translog.jsonl`)",
    ]
    provenance_txt = "\n".join(prov_lines) + "\n"

    return ReviewArtefacts(
        finding_hash=finding_hash,
        packet_md=packet_md,
        packet_json=packet_json,
        provenance_txt=provenance_txt,
    )
