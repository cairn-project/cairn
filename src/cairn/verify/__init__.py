"""cairn.verify — the VERIFY / TRUST layer (wave 3, PLAN §3.5).

Sits ABOVE the wave-2 execute layer: wave 2 produces ONE ``CandidateResult`` per
node; this layer aggregates N of them (from N nodes, one work unit) into a trust
verdict, fully offline. Defense in depth (PLAN §3.5):

  L1  quorum + redundancy + MODEL-DIVERSITY gate    (quorum.py)
  L2  semantic agreement (objective + judge seam)   (agreement.py, judge.py)
  L3  earned reputation accumulator                 (reputation.py)
  L4  honeypots / gold-standard scoring             (honeypot.py)
      Gensyn-style tiebreak-the-disputed-unit       (tiebreak.py)
      verify_unit aggregation entry point           (aggregate.py)

DEFERRED (later waves): ledger/transport (atomic claim, leases, signing, the
transparency log — wave 4), LIVE LLM-as-judge (network; only the seam + offline
MockJudge ship here), Sybil resistance (L5), the SERENE/CoVFeFE collusion-
resilient backstop (L6), prompt-injection adapter defenses (§3.5 B.3), and the
trusted-core membership governance (§3.5 B.4).
"""

from __future__ import annotations

from .agreement import (
    AgreementFunction,
    Cluster,
    ObjectiveAgreement,
    SubjectiveAgreement,
)
from .aggregate import VerifyVerdict, verify_unit
from .honeypot import Honeypot, HoneypotScore
from .judge import Judge, MockJudge
from .quorum import (
    DEFAULT_MODEL_DIVERSITY,
    STATUS_ACCEPTED,
    STATUS_DISPUTED,
    STATUS_INSUFFICIENT_DIVERSITY,
    STATUS_NO_QUORUM,
    QuorumResult,
    decide_quorum,
    required_diversity,
)
from .reputation import (
    EVENT_AGREE,
    EVENT_DISAGREE,
    EVENT_HONEYPOT_FAIL,
    EVENT_HONEYPOT_PASS,
    NEUTRAL_PRIOR,
    InMemoryReputation,
    Reputation,
    ReputationDelta,
    family_subject,
)
from .tiebreak import TiebreakDecision, decide_tiebreak

__all__ = [
    # agreement (L2)
    "AgreementFunction",
    "ObjectiveAgreement",
    "SubjectiveAgreement",
    "Cluster",
    # judge seam (L2)
    "Judge",
    "MockJudge",
    # quorum + diversity (L1)
    "decide_quorum",
    "required_diversity",
    "QuorumResult",
    "DEFAULT_MODEL_DIVERSITY",
    "STATUS_ACCEPTED",
    "STATUS_NO_QUORUM",
    "STATUS_DISPUTED",
    "STATUS_INSUFFICIENT_DIVERSITY",
    # honeypot (L4)
    "Honeypot",
    "HoneypotScore",
    # reputation (L3)
    "Reputation",
    "InMemoryReputation",
    "ReputationDelta",
    "family_subject",
    "NEUTRAL_PRIOR",
    "EVENT_AGREE",
    "EVENT_DISAGREE",
    "EVENT_HONEYPOT_PASS",
    "EVENT_HONEYPOT_FAIL",
    # tiebreak
    "TiebreakDecision",
    "decide_tiebreak",
    # aggregate entry point
    "verify_unit",
    "VerifyVerdict",
]
