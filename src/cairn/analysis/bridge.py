"""The analysis→finding bridge — the missing seam (BUILD-PLAN §5).

``flag_from_verdict`` is the single producer of a ``Finding`` from a real
verify-layer outcome. Before this module the engine had two working halves that
never touched: detect/analyze (cause → execute → verify → verdict) and vet/route
(Finding → human Gate-2 → routable → dispatch). The ``Finding`` references a
``packet_hash`` + an ``AutomatedVerdict``, but NOTHING produced that automated
verdict from a verify verdict; every finding was hand-fabricated. This bridge
closes the gap.

It COMPOSES, reimplementing nothing: the DECISION is the injected ``FlagPolicy``;
the RECORD is the existing ``FindingVetQueue.flag`` (which already
content-addresses the finding, persists it over ``ledger.blobs``, and appends the
``FINDING_FLAGGED`` transparency-log entry). The bridge adds no new hashing, no
new translog kind, no new queue state.

Fail-quiet (BUILD-PLAN §5): an analysis the policy declines produces NO finding
and writes NOTHING — symmetrical to the verify layer returning a non-accepted
verdict without dispatch. Only a policy-flagged verdict emits a finding, and the
EXISTING human Gate-2 still governs whether that finding ever routes.
"""

from __future__ import annotations

from typing import Optional

from ..vetting import Finding, FindingVetQueue
from ..verify import VerifyVerdict
from .policy import FlagPolicy


def flag_from_verdict(
    packet_hash: str,
    verdict: VerifyVerdict,
    *,
    finding_queue: FindingVetQueue,
    policy: FlagPolicy,
    flagged_by: str,
    cause_id: Optional[str] = None,
) -> Optional[Finding]:
    """Emit a ``Finding`` for ``packet_hash`` iff ``policy`` flags ``verdict``.

    Args:
      packet_hash: the content key of the captured ``ExaminationPacket`` the
        verdict was produced over (the evidence the finding references).
      verdict: the verify-layer ``VerifyVerdict`` for the analyzed unit.
      finding_queue: the existing ``FindingVetQueue`` (owns the record + log).
      policy: the injected ``FlagPolicy`` (owns the decision; mission-neutral).
      flagged_by: the node/operator id recorded as the flagger (provenance).
      cause_id: the cause this finding belongs to, if any.

    Returns the produced ``Finding`` when the policy flags, else ``None`` (no
    finding produced, nothing written — fail-quiet).
    """
    decision = policy.decide(verdict)
    if not decision.flagged:
        return None

    assert decision.automated_verdict is not None  # flagged => verdict present
    return finding_queue.flag(
        packet_hash=packet_hash,
        automated_verdict=decision.automated_verdict,
        flagged_by=flagged_by,
        cause_id=cause_id,
    )
