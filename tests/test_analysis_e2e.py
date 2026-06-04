"""OUTCOME-ALTITUDE e2e — the FULL continuous loop, finding PRODUCED not faked.

This is the first test in the suite where the ``Finding`` is produced by the
ANALYSIS layer from a real verify verdict over a real captured packet, rather than
hand-fabricated. It drives the REAL production entry points end to end on a fresh
ledger with NO pre-arranged state, proving the engine is now one continuous loop:

  grant capture role -> capture_packet (REAL inert bundle + PACKET_CAPTURED logged)
   -> N redundant nodes run_work_unit over the packet content -> verify_unit
      (REAL quorum + diversity) yields an ACCEPTED verdict carrying a score
   -> flag_from_verdict (REAL bridge + ThresholdFlagPolicy) PRODUCES a Finding
      referencing the captured packet_hash (FINDING_FLAGGED logged)
   -> human records ROUTABLE via the REAL FindingVetQueue (Gate 2)
   -> dispatch_routable_finding routes + records the action (FINDING_ROUTED +
      ROUTE_ACK_RECORDED)
   -> verify_log over the whole transparency log is ok.

The load-bearing guarantee shown operationally: a finding now ORIGINATES from a
verify verdict (no synthetic finding), and the human Gate-2 + fail-closed routing
gates still govern every downstream step. The two halves are one pipeline.
"""

from __future__ import annotations

from dataclasses import replace

from cairn.analysis import FlagDecision, flag_from_verdict
from cairn.capture import CaptureGate, StaticDocumentCapturePort, capture_packet
from cairn.execute.flow import run_work_unit
from cairn.execute.result import CandidateResult
from cairn.ledger import FixedClock, Ledger, verify_log
from cairn.ledger.translog import (
    KIND_FINDING_FLAGGED,
    KIND_FINDING_ROUTED,
    KIND_PACKET_CAPTURED,
    KIND_ROUTE_ACK_RECORDED,
)
from cairn.pilot.adapter import PilotNodeAdapter
from cairn.pilot.cause import build_pilot_units, load_snippets
from cairn.routing import (
    FindingRoutingAttributes,
    InMemoryRecipientChannel,
    Recipient,
    RecipientRegistry,
    dispatch_routable_finding,
)
from cairn.types import RedundancyPolicy
from cairn.verify import verify_unit
from cairn.vetting import AutomatedVerdict, FindingVetQueue

_KEY = b"analysis-e2e-key-not-secret"


class _BenignInterestPolicy:
    """An inline ``FlagPolicy`` over the REAL pilot output (protocol-seam proof).

    The shipped ``ThresholdFlagPolicy`` reads a numeric score field; the benign
    pilot's real output carries ``{is_open_license, license_id}`` and no numeric
    score. This inline policy proves the ``FlagPolicy`` seam is genuinely general
    (not pilot-coupled): it flags an ACCEPTED verdict whose output reports a
    generic boolean of interest. It hard-codes no scam/sensitive vocabulary — the
    label is opaque and the field name is the pilot's own benign output key.
    """

    def decide(self, verdict):  # -> FlagDecision
        if not verdict.accepted:
            return FlagDecision.no_flag("verdict not accepted")
        out = verdict.accepted_output or {}
        if out.get("is_open_license") is True:
            return FlagDecision.flag(
                AutomatedVerdict(flag_label="flagged", confidence=1.0),
                reason="benign item of interest (open-license)",
            )
        return FlagDecision.no_flag("not of interest")


def test_capture_to_verify_to_flag_to_vet_to_route_end_to_end(tmp_path):
    # Fresh ledger, no pre-arranged state.
    ledger = Ledger(tmp_path / "ledger", FixedClock(start=0.0), signing_key=_KEY)

    # 1. trust-gated capture produces the real inert packet the finding references.
    cgate = CaptureGate(ledger)
    cgate.grant("operator-1", granted_by="anchor", scope_summary="benign fixtures")
    packet = capture_packet(
        StaticDocumentCapturePort(),
        gate=cgate,
        ledger=ledger,
        node_id="operator-1",
        cause_id="link-rot-audit",
    )
    assert ledger.blobs.has(packet.packet_hash)

    # 2. run + verify one benign work unit over real redundant nodes (ACCEPTED).
    unit = build_pilot_units(load_snippets())[0]
    task_id = ledger.define_task(unit)
    candidates: list[CandidateResult] = []
    for family in ("claude", "gpt"):
        node_id = f"node-{family}"
        claim = ledger.claim_task(task_id, node_id=node_id, lease_seconds=60.0)
        outcome = run_work_unit(unit, PilotNodeAdapter(model_family=family))
        assert outcome.candidate is not None
        cand = replace(outcome.candidate, adapter_name=node_id)
        candidates.append(cand)
        ledger.store_result(cand)
        ledger.claims.release(task_id, claim.claim_id)

    verdict = verify_unit(
        candidates,
        RedundancyPolicy.from_dict(unit["redundancy_policy"]),
        reputation=ledger.reputation,
        unit_task_id=task_id,
    )
    assert verdict.accepted
    assert isinstance(verdict.accepted_output, dict)

    # 3. THE BRIDGE — the finding is PRODUCED from the verdict, not hand-built.
    finding = flag_from_verdict(
        packet.packet_hash,
        verdict,
        finding_queue=FindingVetQueue(ledger),
        policy=_BenignInterestPolicy(),
        flagged_by="node-claude",
        cause_id="link-rot-audit",
    )
    assert finding is not None
    assert finding.packet_hash == packet.packet_hash

    kinds = [e.kind for e in ledger.translog.entries()]
    assert kinds.count(KIND_PACKET_CAPTURED) == 1
    assert kinds.count(KIND_FINDING_FLAGGED) == 1

    # 4. human Gate-2 records ROUTABLE on the produced finding (REAL queue).
    queue = FindingVetQueue(ledger)
    queue.record_verdict(
        finding.finding_hash,
        routable=True,
        reason="human finding-vetter confirms the flagged item",
        reviewer_id="finding-vetter",
    )
    assert queue.is_routable(finding.finding_hash)

    # 5. dispatch the routable finding → recorded action (REAL routing spine).
    channel = InMemoryRecipientChannel()
    registry = RecipientRegistry()
    registry.add(
        Recipient.create("recipient-a", locality={"region-a"}, domain={"kind-x"}, channel=channel)
    )
    registry.set_fallback(
        Recipient.create("escalation-default", locality=set(), domain=set(), channel=channel)
    )
    record = dispatch_routable_finding(
        finding.finding_hash,
        ledger=ledger,
        finding_queue=queue,
        registry=registry,
        attributes=FindingRoutingAttributes.of(locality={"region-a"}, domain={"kind-x"}),
    )
    assert record.recipient_id == "recipient-a"
    assert record.ack.accepted is True
    assert channel.dispatched[-1].finding_hash == finding.finding_hash

    final = [e.kind for e in ledger.translog.entries()]
    assert final.count(KIND_FINDING_ROUTED) == 1
    assert final.count(KIND_ROUTE_ACK_RECORDED) == 1

    # 6. the whole transparency log verifies independently.
    assert verify_log(ledger.translog._path).ok  # noqa: SLF001
