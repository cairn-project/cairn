"""run_scenario — the value-demo orchestrator (dump-for-review, NEVER send).

Drives the REAL engine end-to-end over the benign open-data-feed-quality topic and
**dumps** a human-review packet per finding instead of sending anything:

  seed records (inert; some w/ a planted defect)          [SIMULATED detection]
    → capture_packet (REAL inert-packet capture path)
    → analysis: ClaudeCliAdapter (REAL claude -p, default) + reference node
                 (offline path uses two deterministic reference nodes)
    → verify_unit (REAL quorum + honeypot)
    → flag_from_verdict + ThresholdFlagPolicy (REAL bridge)  [fail-quiet]
    → FindingVetQueue.flag → PENDING                          [REAL Gate-2]
    → ReportingOrgFinder.resolve (REAL public org lookup; fail-closed)
    → build + write the banner-labeled review dump
    → STOP. Nothing is sent. There is no egress code path.

``review_scenario`` records the human Gate-2 verdict through the REAL
``FindingVetQueue.record_verdict`` (a finding becomes ROUTABLE only via a recorded
human ROUTABLE verdict). ``list_scenario`` lists scenario findings + their state.

Even a ROUTABLE finding is NOT delivered here: onward delivery is the deferred,
separately-security-reviewed real-channel phase. The scenario's terminal state is
"human-vetted + dumped", never "delivered".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..analysis.bridge import flag_from_verdict
from ..analysis.policy import ThresholdFlagPolicy
from ..capture.gate import CaptureGate
from ..capture.packet import ExaminationPacket, Observation
from ..execute.claude_adapter import ClaudeCliAdapter, ClockFn, TranscriptFn
from ..execute.flow import run_work_unit
from ..execute.result import CandidateResult
from ..ledger.ledger import Ledger
from ..ledger.translog import KIND_PACKET_CAPTURED
from ..types import RedundancyPolicy
from ..verify.aggregate import VerifyVerdict, verify_unit
from ..verify.honeypot import Honeypot
from ..vetting.finding import FindingState
from ..vetting.finding_queue import FindingVetQueue
from ..vetting.review import VettingError
from .dump import write_review_dump
from .node import ScenarioReferenceNode
from .org_finder import ReportingOrgFinder
from .packet_builder import build_review_artefacts
from .seed import (
    DEFECT_FLAG_THRESHOLD,
    HONEYPOT_RECORD_ID,
    SCENARIO_CAUSE_ID,
    SCENARIO_FLAG_LABEL,
    SCORE_FIELD,
    build_scenario_unit,
    gold_answer,
    load_seed_records,
    record_observations,
)

_LEASE_SECONDS = 60.0
_LIVE_FAMILY = "claude"
_REFERENCE_FAMILY = "reference"
_FLAGGED_BY = "scenario-runner"
_CAPTURE_NODE = "scenario-capture"


@dataclass(frozen=True)
class ScenarioFindingResult:
    """One scenario finding's outcome (PENDING after the run; dumped)."""

    record_id: str
    finding_hash: str
    packet_hash: str
    state: str
    org_resolved: bool
    recipient_contact: str | None
    dump_dir: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "finding_hash": self.finding_hash,
            "packet_hash": self.packet_hash,
            "state": self.state,
            "org_resolved": self.org_resolved,
            "recipient_contact": self.recipient_contact,
            "dump_dir": self.dump_dir,
        }


@dataclass(frozen=True)
class ScenarioRunSummary:
    """Structured summary of a full scenario run (dump-for-review, never sent)."""

    cause_id: str
    findings: list[ScenarioFindingResult]
    records_analyzed: int
    log_head: str
    review_dir: str
    sent: bool = False
    offline: bool = True
    no_defect_records: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cause_id": self.cause_id,
            "findings": [f.to_dict() for f in self.findings],
            "records_analyzed": self.records_analyzed,
            "no_defect_records": self.no_defect_records,
            "log_head": self.log_head,
            "review_dir": self.review_dir,
            "offline": self.offline,
            "sent": self.sent,
        }

    def pretty(self) -> str:
        from .packet_builder import REVIEW_BANNER

        lines = [
            REVIEW_BANNER,
            "",
            f"scenario cause: {self.cause_id}  (mode: {'offline' if self.offline else 'live'})",
            f"records analyzed: {self.records_analyzed}  |  findings dumped: "
            f"{len(self.findings)}  |  sent: {self.sent}",
            "",
        ]
        for f in self.findings:
            org = f.recipient_contact or "(no public contact resolved — fail-closed)"
            lines.append(f"  finding {f.finding_hash[:12]}  [{f.state}]  record={f.record_id}")
            lines.append(f"      reporting org: {org}")
            lines.append(f"      review dump:   {f.dump_dir}")
        if self.no_defect_records:
            lines.append("")
            lines.append(
                f"  no-defect records (no finding, fail-quiet): {', '.join(self.no_defect_records)}"
            )
        lines.append("")
        lines.append(f"transparency log head: {self.log_head}")
        lines.append("Nothing was sent. Terminal state: human-vetted + dumped.")
        return "\n".join(lines)


def _capture_record(
    record: dict[str, Any], *, gate: CaptureGate, ledger: Ledger
) -> ExaminationPacket:
    """Freeze a seed record into an inert packet via the REAL capture path.

    Reuses ``ExaminationPacket`` + the content-addressed blob store + the
    PACKET_CAPTURED transparency entry. The observations are inert (no locator, no
    fetch surface). The capture node holds a granted CAPTURE role (fail-closed).
    """
    if not gate.is_granted(_CAPTURE_NODE):
        raise VettingError(  # pragma: no cover - guarded by run_scenario granting first
            f"capture node {_CAPTURE_NODE!r} is not granted the CAPTURE role"
        )
    observations: tuple[Observation, ...] = record_observations(record)
    packet = ExaminationPacket.create(
        target_ref=record["target_ref"],
        observations=observations,
        captured_at=ledger.clock.now(),
        captured_by=_CAPTURE_NODE,
        capture_method="scenario-seed-fixture",
        cause_id=SCENARIO_CAUSE_ID,
    )
    blob_key = ledger.blobs.put_json(packet.material_dict())
    assert blob_key == packet.packet_hash
    ledger.translog.append(
        KIND_PACKET_CAPTURED,
        {
            "packet_hash": packet.packet_hash,
            "target_ref": packet.target_ref,
            "cause_id": SCENARIO_CAUSE_ID,
            "captured_by": _CAPTURE_NODE,
            "capture_method": packet.capture_method,
            "observation_count": len(observations),
        },
    )
    return packet


def run_scenario(
    ledger: Ledger,
    *,
    review_dir: str | Path,
    offline: bool = True,
    transcript_fn: TranscriptFn | None = None,
    clock_fn: ClockFn | None = None,
    model: str = "sonnet",
    timeout: float = 120.0,
    org_finder: ReportingOrgFinder | None = None,
) -> ScenarioRunSummary:
    """Run the value-demo end-to-end and DUMP a review packet per finding.

    Args:
      ledger: a real, fresh ``Ledger`` (carries its injected ``Clock``).
      review_dir: where the per-finding review dumps are written.
      offline: when True (the hermetic default), analysis uses two deterministic
        ``ScenarioReferenceNode`` families (no model, no network). When False, one
        node is the live ``ClaudeCliAdapter`` (REAL isolated ``claude -p``); the
        other stays the deterministic reference node so the diversity quorum is
        satisfiable.
      transcript_fn: injected fake transcript producer for the live path in tests
        (keeps the suite deterministic without spawning a model).
      clock_fn: provenance clock for the live candidate.
      model / timeout: live-call model tier + per-call subprocess timeout.
      org_finder: the reporting-org finder (defaults to the verified seed registry).

    Returns a ``ScenarioRunSummary``. Findings are left PENDING in the REAL human
    gate; NOTHING is sent (there is no egress code path).
    """
    review_path = Path(review_dir)
    review_path.mkdir(parents=True, exist_ok=True)
    finder = org_finder if org_finder is not None else ReportingOrgFinder()
    queue = FindingVetQueue(ledger)
    policy = ThresholdFlagPolicy(
        SCENARIO_FLAG_LABEL, DEFECT_FLAG_THRESHOLD, score_field=SCORE_FIELD
    )

    # Grant the scenario capture node the CAPTURE role (REAL fail-closed gate).
    gate = CaptureGate(ledger)
    gate.grant(
        _CAPTURE_NODE,
        granted_by="scenario",
        scope_summary="scenario seed open-data records",
    )

    # The two analysis nodes. Offline: two deterministic reference families. Live:
    # the real claude node + the deterministic reference node (distinct families).
    reference_node = ScenarioReferenceNode(model_family=_REFERENCE_FAMILY)
    if offline:
        live_node: Any = ScenarioReferenceNode(model_family=_LIVE_FAMILY)
    else:
        live_node = ClaudeCliAdapter(
            transcript_fn=transcript_fn, clock_fn=clock_fn, model=model, timeout=timeout
        )
    nodes = [
        (_LIVE_FAMILY, f"node-{_LIVE_FAMILY}", live_node),
        (_REFERENCE_FAMILY, f"node-{_REFERENCE_FAMILY}", reference_node),
    ]

    records = load_seed_records()
    findings: list[ScenarioFindingResult] = []
    no_defect: list[str] = []

    for record in records:
        packet = _capture_record(record, gate=gate, ledger=ledger)
        unit_dict = build_scenario_unit(record)
        task_id = ledger.define_task(unit_dict)

        candidates: list[CandidateResult] = []
        for _family, node_id, adapter in nodes:
            claim = ledger.claim_task(task_id, node_id=node_id, lease_seconds=_LEASE_SECONDS)
            outcome = run_work_unit(unit_dict, adapter)
            assert outcome.candidate is not None  # live adapter fails closed, not None
            from dataclasses import replace

            cand = replace(outcome.candidate, adapter_name=node_id)
            candidates.append(cand)
            ledger.store_result(cand)
            ledger.claims.release(task_id, claim.claim_id)

        red_policy = RedundancyPolicy.from_dict(unit_dict["redundancy_policy"])
        is_hp = record["record_id"] == HONEYPOT_RECORD_ID
        honeypot = Honeypot(expected_output=gold_answer(record)) if is_hp else None
        verdict: VerifyVerdict = verify_unit(
            candidates,
            red_policy,
            honeypot=honeypot,
            reputation=ledger.reputation,
            unit_task_id=task_id,
        )
        ledger.record_verdict(task_id, verdict)

        # REAL bridge: only a policy-flagged (high-confidence-defect) verdict emits
        # a finding; a no-defect record produces nothing (fail-quiet).
        finding = flag_from_verdict(
            packet.packet_hash,
            verdict,
            finding_queue=queue,
            policy=policy,
            flagged_by=_FLAGGED_BY,
            cause_id=SCENARIO_CAUSE_ID,
        )
        if finding is None:
            no_defect.append(record["record_id"])
            continue

        analysis = verdict.accepted_output or {}
        quorum_families = (
            sorted(verdict.quorum.winning_cluster.model_families)
            if verdict.quorum.winning_cluster is not None
            else []
        )
        honeypot_passed: bool | None = None
        if verdict.honeypot_scores:
            honeypot_passed = all(s.passed for s in verdict.honeypot_scores)

        resolved = finder.resolve(record)
        recipient_contact = resolved.contact if resolved is not None else None

        artefacts = build_review_artefacts(
            finding_hash=finding.finding_hash,
            packet_hash=packet.packet_hash,
            record=record,
            analysis=analysis,
            verdict_status=verdict.status,
            quorum_families=quorum_families,
            honeypot_passed=honeypot_passed,
            resolved_org=resolved,
            cause_id=SCENARIO_CAUSE_ID,
            provenance={
                "detection": "SIMULATED (seeded inert records, no network)",
                "analysis": "REAL (offline reference nodes)"
                if offline
                else "REAL (live claude -p + reference node)",
                "org_lookup": "REAL (verified public seed registry)",
                "vetting": "REAL human Gate-2 (finding left PENDING)",
                "delivery": "NONE — no egress code path; dump only",
            },
            log_head=ledger.translog.head_hash(),
        )
        out_dir = write_review_dump(review_path, artefacts)

        state = queue.finding_state(finding.finding_hash)
        findings.append(
            ScenarioFindingResult(
                record_id=record["record_id"],
                finding_hash=finding.finding_hash,
                packet_hash=packet.packet_hash,
                state=state.value,
                org_resolved=resolved is not None,
                recipient_contact=recipient_contact,
                dump_dir=str(out_dir),
            )
        )

    return ScenarioRunSummary(
        cause_id=SCENARIO_CAUSE_ID,
        findings=findings,
        records_analyzed=len(records),
        log_head=ledger.translog.head_hash(),
        review_dir=str(review_path),
        sent=False,
        offline=offline,
        no_defect_records=no_defect,
    )


@dataclass(frozen=True)
class ScenarioReviewResult:
    """The outcome of recording a human Gate-2 verdict on a scenario finding."""

    finding_hash: str
    state: str
    decision: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_hash": self.finding_hash,
            "state": self.state,
            "decision": self.decision,
            "reason": self.reason,
        }


# The scenario's own run/list output prints TRUNCATED finding hashes (12 and 16
# chars) for human readability; review must accept what its sibling commands
# print. Resolution rules (fail-closed): a full-length hash is passed through
# UNCHANGED (never prefix-matched, so a full hash can never be silently rewritten
# to a different finding); anything shorter must be >= _MIN_PREFIX_LEN chars and
# match exactly ONE queued finding — no match and ambiguous both REFUSE. The
# verdict recorded on the ledger always carries the resolved FULL hash, and the
# ``FindingVetQueue`` gate itself still operates on full hashes only.
_FULL_HASH_LEN = 64
_MIN_PREFIX_LEN = 8


def resolve_finding_prefix(candidates: list[str], hash_or_prefix: str) -> str:
    """Resolve ``hash_or_prefix`` against the queued finding hashes (fail-closed)."""
    if len(hash_or_prefix) >= _FULL_HASH_LEN:
        return hash_or_prefix
    if len(hash_or_prefix) < _MIN_PREFIX_LEN:
        raise VettingError(
            f"finding-hash prefix {hash_or_prefix!r} is too short: "
            f"use at least {_MIN_PREFIX_LEN} characters or the full hash"
        )
    matches = sorted({c for c in candidates if c.startswith(hash_or_prefix)})
    if not matches:
        raise VettingError(f"finding {hash_or_prefix} is not in the finding-vet queue")
    if len(matches) > 1:
        shown = ", ".join(m[:16] for m in matches)
        raise VettingError(
            f"finding-hash prefix {hash_or_prefix} is ambiguous (matches: {shown}): "
            "use more characters or the full hash"
        )
    return matches[0]


def review_scenario(
    ledger: Ledger,
    finding_hash: str,
    *,
    routable: bool,
    reason: str,
    reviewer_id: str,
) -> ScenarioReviewResult:
    """Record the HUMAN Gate-2 verdict through the REAL ``FindingVetQueue``.

    ``finding_hash`` may be the full 64-char hash or an unambiguous prefix
    (>= 8 chars) of one queued finding — the truncated hashes printed by
    ``scenario run`` / ``scenario list`` work as-is. A finding becomes ROUTABLE
    only via a recorded human ROUTABLE verdict; a ``routable=False`` (reject)
    with an empty reason is REFUSED by the real queue (no silent rejection).
    STILL nothing is sent — a ROUTABLE verdict only changes the gate state;
    onward delivery is the deferred real-channel phase.
    """
    queue = FindingVetQueue(ledger)
    queued = [it.finding_hash for it in queue.list_pending() + queue.list_reviewed()]
    finding_hash = resolve_finding_prefix(queued, finding_hash)
    item = queue.record_verdict(finding_hash, routable, reason, reviewer_id)
    state = queue.finding_state(finding_hash)
    assert item.verdict is not None
    return ScenarioReviewResult(
        finding_hash=finding_hash,
        state=state.value,
        decision=item.verdict.decision,
        reason=item.verdict.reason,
    )


@dataclass(frozen=True)
class ScenarioListing:
    """A listed scenario finding + its current human-gate state."""

    finding_hash: str
    state: str

    def to_dict(self) -> dict[str, Any]:
        return {"finding_hash": self.finding_hash, "state": self.state}


def list_scenario(ledger: Ledger) -> list[ScenarioListing]:
    """List scenario findings (across all queue items) + their gate state."""
    queue = FindingVetQueue(ledger)
    out: list[ScenarioListing] = []
    for item in queue.list_pending() + queue.list_reviewed():
        state: FindingState = queue.finding_state(item.finding_hash)
        out.append(ScenarioListing(finding_hash=item.finding_hash, state=state.value))
    return out
