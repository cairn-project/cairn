"""flag_from_verdict — the analysis→finding bridge driver.

The bridge owns the DECISION (the injected policy) and delegates the RECORD to the
existing ``FindingVetQueue.flag``. A declined policy produces NO finding and writes
NOTHING; a flagged policy emits a real, human-vettable ``Finding``.
"""

from __future__ import annotations

from cairn.analysis import ThresholdFlagPolicy, flag_from_verdict
from cairn.ledger import FixedClock, Ledger
from cairn.ledger.translog import KIND_FINDING_FLAGGED
from cairn.verify import verify_unit
from cairn.vetting import FindingVetQueue

from ._verify_helpers import make_result, policy

_KEY = b"analysis-bridge-key-not-secret"

# A stable packet_hash stand-in: the bridge only needs the reference string; the
# finding content-addresses around it. (The e2e test uses a REAL captured packet.)
_PACKET = "packet-ref-abc123"


def _ledger(tmp_path):
    return Ledger(tmp_path / "ledger", FixedClock(start=0.0), signing_key=_KEY)


def _accepted_verdict(output):
    cands = [
        make_result(output, node="n1", family="claude"),
        make_result(output, node="n2", family="gpt"),
    ]
    return verify_unit(cands, policy(target_nresults=2, min_quorum=2, model_diversity=1))


def test_declined_policy_produces_no_finding_and_writes_nothing(tmp_path):
    ledger = _ledger(tmp_path)
    queue = FindingVetQueue(ledger)
    v = _accepted_verdict({"label": "cc-by", "confidence": 0.4})

    result = flag_from_verdict(
        _PACKET,
        v,
        finding_queue=queue,
        policy=ThresholdFlagPolicy("flagged", 0.9),  # 0.4 < 0.9 => declined
        flagged_by="node-1",
        cause_id="cause-x",
    )

    assert result is None
    assert queue.list_pending() == []
    kinds = [e.kind for e in ledger.translog.entries()]
    assert KIND_FINDING_FLAGGED not in kinds


def test_flagged_policy_emits_a_real_finding(tmp_path):
    ledger = _ledger(tmp_path)
    queue = FindingVetQueue(ledger)
    v = _accepted_verdict({"label": "cc-by", "confidence": 0.92})

    finding = flag_from_verdict(
        _PACKET,
        v,
        finding_queue=queue,
        policy=ThresholdFlagPolicy("flagged", 0.7),
        flagged_by="node-1",
        cause_id="cause-x",
    )

    assert finding is not None
    assert finding.packet_hash == _PACKET
    assert finding.automated_verdict.flag_label == "flagged"
    assert finding.cause_id == "cause-x"

    # The finding is queued PENDING and a FINDING_FLAGGED entry is on the log.
    pending = queue.list_pending()
    assert [p.finding_hash for p in pending] == [finding.finding_hash]
    kinds = [e.kind for e in ledger.translog.entries()]
    assert kinds.count(KIND_FINDING_FLAGGED) == 1


def test_emitted_finding_is_indistinguishable_and_vettable_to_routable(tmp_path):
    # A finding produced by the bridge flows through the EXISTING human Gate-2 the
    # same as a hand-built one — proving the two halves are now one pipeline.
    ledger = _ledger(tmp_path)
    queue = FindingVetQueue(ledger)
    v = _accepted_verdict({"label": "cc-by", "confidence": 0.95})

    finding = flag_from_verdict(
        _PACKET,
        v,
        finding_queue=queue,
        policy=ThresholdFlagPolicy("flagged", 0.5),
        flagged_by="node-1",
        cause_id="cause-x",
    )
    assert finding is not None

    queue.record_verdict(
        finding.finding_hash,
        routable=True,
        reason="human finding-vetter confirms",
        reviewer_id="finding-vetter",
    )
    assert queue.is_routable(finding.finding_hash)
